from __future__ import annotations

"""
Canary-Qwen 2.5B dual-pass engine (ASR + refinement).

Mocks are disallowed at runtime. If dependencies or downloads fail, the engine
raises a DependencyError so the CLI can fail loudly with guidance.
"""

import logging
from pathlib import Path
from typing import Any, Mapping

from vociferous.domain.model import (
    EngineConfig,
    EngineMetadata,
    TranscriptSegment,
    TranscriptionEngine,
    TranscriptionOptions,
)
from vociferous.domain.exceptions import DependencyError
from vociferous.engines.model_registry import normalize_model_name

logger = logging.getLogger(__name__)
DEFAULT_REFINE_PROMPT = (
    "Refine the following transcript by:\n"
    "1. Correcting grammar and punctuation\n"
    "2. Fixing capitalization\n"
    "3. Removing filler words and false starts\n"
    "4. Improving fluency while preserving meaning\n"
    "5. Maintaining the speaker's intent\n\n"
    "Do not add or remove information. Only improve clarity and correctness."
)


class CanaryQwenEngine(TranscriptionEngine):
    """Dual-pass Canary wrapper with batch `transcribe_file` and `refine_text`."""

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        self.model_name = normalize_model_name("canary_qwen", config.model_name)
        self.device = config.device
        self.precision = config.compute_type
        self._model: Any | None = None
        self._audio_tag: str = "<|audioplaceholder|>"
        self._lazy_model()

    @property
    def metadata(self) -> EngineMetadata:  # pragma: no cover - simple data accessor
        return EngineMetadata(
            model_name=self.model_name,
            device=self.device,
            precision=self.precision,
        )

    # Batch interface ----------------------------------------------------
    def transcribe_file(self, audio_path: Path, options: TranscriptionOptions | None = None) -> list[TranscriptSegment]:
        """Transcribe a single audio file. For multiple files, use transcribe_files_batch."""
        import torch
        
        if self._model is None:
            raise DependencyError(
                "Canary-Qwen model not loaded; install NeMo trunk: pip install \"nemo_toolkit[asr,tts] @ git+https://github.com/NVIDIA/NeMo.git\""
            )

        pcm_bytes = self._load_audio_bytes(audio_path)
        duration_s = self._estimate_duration(pcm_bytes)
        language = options.language if options and options.language else "en"

        prompts = [
            [
                {
                    "role": "user",
                    "content": f"Transcribe the following: {self._audio_tag}",
                    "audio": [str(audio_path)],
                }
            ]
        ]

        # Use inference_mode for faster inference (disables autograd)
        with torch.inference_mode():
            answer_ids = self._model.generate(
                prompts=prompts,
                max_new_tokens=self._resolve_asr_tokens(options),
            )
        transcript_text = self._model.tokenizer.ids_to_text(answer_ids[0].cpu())

        segment = TranscriptSegment(
            id="segment-0",
            start=0.0,
            end=duration_s,
            raw_text=transcript_text,
            language=language,
            confidence=0.0,
        )
        return [segment]

    def transcribe_files_batch(
        self, 
        audio_paths: list[Path], 
        options: TranscriptionOptions | None = None
    ) -> list[list[TranscriptSegment]]:
        """Transcribe multiple audio files in a single batched inference call.
        
        This is significantly faster than calling transcribe_file() repeatedly
        because it leverages GPU parallelism and avoids per-call overhead.
        
        Args:
            audio_paths: List of audio file paths to transcribe
            options: Transcription options (applied to all files)
            
        Returns:
            List of segment lists, one per input audio file
        """
        import torch
        
        if not audio_paths:
            return []
            
        if self._model is None:
            raise DependencyError(
                "Canary-Qwen model not loaded; install NeMo trunk: pip install \"nemo_toolkit[asr,tts] @ git+https://github.com/NVIDIA/NeMo.git\""
            )

        language = options.language if options and options.language else "en"
        
        # Build batch of prompts - one conversation per audio file
        prompts = [
            [
                {
                    "role": "user",
                    "content": f"Transcribe the following: {self._audio_tag}",
                    "audio": [str(audio_path)],
                }
            ]
            for audio_path in audio_paths
        ]
        
        # Get durations for each file
        durations = [
            self._estimate_duration(self._load_audio_bytes(path))
            for path in audio_paths
        ]
        
        # Single batched inference call with inference_mode for speed
        logger.info(f"Batch transcribing {len(audio_paths)} audio files in single inference call")
        with torch.inference_mode():
            answer_ids_batch = self._model.generate(
                prompts=prompts,
                max_new_tokens=self._resolve_asr_tokens(options),
            )
        
        # Parse results
        results: list[list[TranscriptSegment]] = []
        for idx, (answer_ids, duration_s, audio_path) in enumerate(
            zip(answer_ids_batch, durations, audio_paths)
        ):
            transcript_text = self._model.tokenizer.ids_to_text(answer_ids.cpu())
            segment = TranscriptSegment(
                id=f"segment-{idx}",
                start=0.0,
                end=duration_s,
                raw_text=transcript_text,
                language=language,
                confidence=0.0,
            )
            results.append([segment])
        
        return results

    def refine_text(self, raw_text: str, instructions: str | None = None) -> str:
        prompt = instructions or DEFAULT_REFINE_PROMPT
        cleaned = raw_text.strip()
        if not cleaned:
            return ""

        if self._model is None:
            raise DependencyError(
                "Canary-Qwen model not loaded; install NeMo trunk: pip install \"nemo_toolkit[asr,tts] @ git+https://github.com/NVIDIA/NeMo.git\""
            )

        # Qwen3 models have a "thinking mode" by default that generates <think>...</think>
        # content before the actual response. We disable this by appending the instruction
        # to respond directly without reasoning.
        refine_prompt = (
            f"{prompt}\n\n"
            "Respond with ONLY the refined transcript. Do not explain your changes or "
            "show your reasoning. Output the corrected text directly.\n\n"
            f"{cleaned}"
        )
        
        prompts = [[{"role": "user", "content": refine_prompt}]]
        with self._model.llm.disable_adapter():
            answer_ids = self._model.generate(
                prompts=prompts,
                max_new_tokens=self._resolve_refine_tokens(cleaned),
            )

        # Type assertion: ids_to_text returns str but lacks type hints
        raw_output: str = self._model.tokenizer.ids_to_text(answer_ids[0].cpu()).strip()
        
        # Extract clean assistant response from chat template format
        refined = self._extract_assistant_response(raw_output, cleaned)
        return refined

    def _extract_assistant_response(self, raw_output: str, original_text: str = "") -> str:
        """Extract clean assistant response from Qwen chat template format.
        
        Qwen models output in chat template format with markers like:
        - <|im_start|>user ... <|im_end|>
        - <|im_start|>assistant ... <|im_end|>
        - <think>internal reasoning</think> (Qwen's chain-of-thought)
        
        This method strips all template artifacts to return only the final answer.
        
        Args:
            raw_output: The raw tokenizer output containing chat template
            original_text: The original input text (fallback if extraction fails)
        """
        output = raw_output
        
        # Step 1: Extract content after the last <|im_start|>assistant marker
        # This skips the user prompt that may have been echoed back
        assistant_marker = "<|im_start|>assistant"
        if assistant_marker in output:
            parts = output.split(assistant_marker)
            output = parts[-1]  # Take content after last assistant marker
        
        # Also check for just "assistant" on its own line (after marker removal)
        lines = output.split("\n")
        if lines and lines[0].strip() == "assistant":
            output = "\n".join(lines[1:])
        
        # Step 2: Remove <|im_end|> closing tags
        output = output.replace("<|im_end|>", "")
        
        # Step 3: Remove Qwen's <think>...</think> internal reasoning blocks
        # The model may output: <think>reasoning here</think>actual answer
        if "</think>" in output:
            # Take everything after the closing </think> tag
            parts = output.split("</think>")
            output = parts[-1]
        elif "<think>" in output:
            # Incomplete thinking block - the model didn't finish thinking
            # Take everything BEFORE the <think> tag as that may contain the answer
            before_think = output.split("<think>")[0].strip()
            if before_think and len(before_think) >= 20:
                output = before_think
            else:
                # Nothing useful before <think> - model got stuck in thinking mode
                # This is a generation failure; return original text as fallback
                logger.warning(
                    "Model entered thinking mode without completing. "
                    "The model may need more tokens or different prompting. "
                    "Falling back to original transcript."
                )
                return original_text if original_text else ""
        
        # Step 4: Remove any remaining chat template markers
        markers_to_remove = [
            "<|im_start|>",
            "<|im_end|>",
            "<|endoftext|>",
            "<|end|>",
            "user\n",  # Leftover role labels
            "assistant\n",
        ]
        for marker in markers_to_remove:
            output = output.replace(marker, "")
        
        # Step 5: Clean up whitespace
        output = output.strip()
        
        # Step 6: Check if output looks valid
        # If output is empty, too short, or still contains the prompt, fallback
        prompt_fragments = [
            "Refine the following transcript",
            "Correcting grammar and punctuation",
            "Respond with ONLY the refined",
        ]
        
        is_valid = (
            len(output) >= 20 and  # Reasonable minimum length
            not any(frag in output for frag in prompt_fragments)  # No prompt leakage
        )
        
        if not is_valid:
            logger.warning(
                f"Refinement extraction failed (output length: {len(output)} chars). "
                "Falling back to original text. Check model generation settings."
            )
            # Return original text as fallback (no refinement is better than garbage)
            return original_text if original_text else output
        
        return output

    # Internals ---------------------------------------------------------
    def _lazy_model(self) -> None:
        if self._model is not None:
            return
        try:
            import torch  # pragma: no cover - optional
            from nemo.collections.speechlm2.models import SALM  # pragma: no cover - optional
        except ImportError:  # pragma: no cover - dependency guard
            raise DependencyError(
                "Missing dependencies for Canary-Qwen SALM. Install NeMo trunk (requires torch>=2.6): "
                "pip install \"nemo_toolkit[asr,tts] @ git+https://github.com/NVIDIA/NeMo.git\"\n"
                "Then run: vociferous deps check --engine canary_qwen"
            )

        cache_dir = Path(self.config.model_cache_dir).expanduser() if self.config.model_cache_dir else None
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

        # Map compute_type to torch dtype to prevent float32 auto-loading
        # (Issue: Models saved as bfloat16 default-load as float32, doubling VRAM usage)
        dtype_map = {
            "float32": torch.float32,
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
        }
        target_dtype = dtype_map.get(self.config.compute_type, torch.bfloat16)  # Default to bfloat16
        device = self._resolve_device(torch, self.device)

        try:
            # Load model with explicit dtype to prevent memory leak
            # See: https://github.com/huggingface/transformers/issues/34743
            model = SALM.from_pretrained(self.model_name)
            
            # Convert to target dtype BEFORE moving to device to avoid double allocation
            model = model.to(dtype=target_dtype)
            model = model.to(device=device)
            
            # Enable eval mode for inference optimizations (disables dropout, etc.)
            model = model.eval()
            
            self._model = model
            self._audio_tag = getattr(model, "audio_locator_tag", "<|audioplaceholder|>")
        except Exception as exc:  # pragma: no cover - optional guard
            raise DependencyError(
                f"Failed to load Canary-Qwen model '{self.model_name}': {exc}\n"
                "Ensure NeMo toolkit is installed from trunk: pip install \"nemo_toolkit[asr,tts] @ git+https://github.com/NVIDIA/NeMo.git\""
            ) from exc

    def _load_audio_bytes(self, audio_path: Path) -> bytes:
        try:
            import wave

            with wave.open(str(audio_path), "rb") as wf:
                return wf.readframes(wf.getnframes())
        except Exception:
            return audio_path.read_bytes()

    @staticmethod
    def _estimate_duration(data: bytes, sample_rate: int = 16000) -> float:
        if not data:
            return 0.0
        # PCM16 audio stores one sample per 2 bytes.
        samples = len(data) / 2
        return float(samples) / float(sample_rate)

    @staticmethod
    def _resolve_device(torch_module: Any, requested: str) -> Any:
        if requested == "cpu":
            return torch_module.device("cpu")
        if requested == "cuda" and torch_module.cuda.is_available():
            return torch_module.device("cuda")
        # auto or unavailable cuda falls back to cpu
        return torch_module.device("cuda" if torch_module.cuda.is_available() else "cpu")

    @staticmethod
    def _resolve_asr_tokens(options: TranscriptionOptions | None) -> int:
        try:
            raw = options.params.get("max_new_tokens") if options and options.params else None
            return int(raw) if raw is not None else 256
        except (TypeError, ValueError):
            return 256

    @staticmethod
    def _resolve_refine_tokens(text: str) -> int:
        # Keep headroom for longer refinements; cap at 2048 tokens.
        length_hint = max(512, min(len(text) // 2, 2048))
        return length_hint

    @staticmethod
    def _resolve_dtype(torch_module: Any, precision: str) -> Any:
        mapping: Mapping[str, Any] = {
            "float16": getattr(torch_module, "float16", None),
            "fp16": getattr(torch_module, "float16", None),
            "float32": getattr(torch_module, "float32", None),
            "fp32": getattr(torch_module, "float32", None),
            "bfloat16": getattr(torch_module, "bfloat16", None),
        }
        return mapping.get(precision, torch_module.float32)
