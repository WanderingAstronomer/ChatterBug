"""
Canary-Qwen 2.5B dual-pass engine (ASR + refinement).

Mocks are disallowed at runtime. If dependencies or downloads fail, the engine
raises a DependencyError so the CLI can fail loudly with guidance.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from vociferous.domain.exceptions import DependencyError
from vociferous.domain.model import (
    EngineConfig,
    EngineMetadata,
    TranscriptionEngine,
    TranscriptionOptions,
    TranscriptSegment,
)
from vociferous.engines.model_registry import normalize_model_name

logger = logging.getLogger(__name__)

# System prompt that explicitly disables Qwen3's thinking mode
REFINE_SYSTEM_PROMPT = (
    "You are a transcript editor. Output ONLY the corrected text. "
    "Never explain your changes. Never add commentary. "
    "Never use <think> tags. Just output the corrected text directly."
)

DEFAULT_REFINE_PROMPT = (
    "Refine the following transcript by:\n"
    "1. Correcting grammar and punctuation\n"
    "2. Fixing capitalization\n"
    "3. Removing filler words (um, uh, like) and false starts\n"
    "4. Improving fluency while preserving meaning\n"
    "5. Maintaining the speaker's intent\n\n"
    "Output the corrected text and nothing else."
)


def _suppress_third_party_logging() -> None:
    """Suppress noisy third-party logging before importing NeMo.
    
    NeMo, Transformers, and related libraries produce INFO/WARNING messages
    that pollute Rich progress displays. This function silences them via
    environment variables (for NeMo's custom logging) and Python's logging
    and warnings modules.
    
    Must be called BEFORE importing nemo.collections.
    """
    import logging
    import os
    import warnings
    
    # Environment variables for NeMo's custom logging system
    os.environ["NEMO_LOGGING_LEVEL"] = "ERROR"
    os.environ["NEMO_TELEMETRY_DISABLE"] = "1"
    
    # Suppress Python warnings from third-party libraries
    warnings.filterwarnings("ignore", message=".*generation_config.*")
    warnings.filterwarnings("ignore", message=".*special tokens.*")
    warnings.filterwarnings("ignore", message=".*PADDING.*")
    warnings.filterwarnings("ignore", message=".*Megatron.*")
    warnings.filterwarnings("ignore", message=".*LoRA adapter.*")
    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings("ignore", category=UserWarning, module="transformers")
    warnings.filterwarnings("ignore", category=UserWarning, module="nemo")
    warnings.filterwarnings("ignore", category=UserWarning, module="peft")
    
    # Suppress standard Python loggers
    noisy_loggers = [
        "nemo",
        "nemo_logging",
        "nemo.collections",
        "nemo.utils",
        "transformers",
        "transformers.generation",
        "huggingface_hub",
        "pytorch_lightning",
        "lightning",
        "peft",
        "onelogger",
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.CRITICAL)


def _set_nemo_log_level_after_import() -> None:
    """Set NeMo log level after import.
    
    NeMo's logging system ignores the NEMO_LOGGING_LEVEL environment variable
    when it's set via Python (os.environ). We must call nemo_logging.setLevel()
    AFTER importing NeMo.
    """
    try:
        from nemo.utils import logging as nemo_logging  # type: ignore[import-untyped]
        nemo_logging.setLevel("ERROR")
    except ImportError:
        pass  # NeMo not installed


class CanaryQwenEngine(TranscriptionEngine):
    """Dual-pass Canary wrapper with batch `transcribe_file` and `refine_text`."""

    def __init__(self, config: EngineConfig) -> None:
        # Suppress third-party logging BEFORE loading model
        _suppress_third_party_logging()
        
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
        logger.debug(f"Batch transcribing {len(audio_paths)} audio files in single inference call")
        with torch.inference_mode():
            answer_ids_batch = self._model.generate(
                prompts=prompts,
                max_new_tokens=self._resolve_asr_tokens(options),
            )
        
        # Parse results
        results: list[list[TranscriptSegment]] = []
        for idx, (answer_ids, duration_s, _audio_path) in enumerate(
            zip(answer_ids_batch, durations, audio_paths, strict=True)
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

        # Build prompt that explicitly instructs no thinking/explanation
        # Note: SALM only supports 'user' and 'assistant' roles, not 'system'
        full_prompt = (
            f"{REFINE_SYSTEM_PROMPT}\n\n"
            f"{prompt}\n\n"
            f"Text to edit:\n{cleaned}\n\n"
            f"Edited text:"
        )
        
        prompts = [[{"role": "user", "content": full_prompt}]]
        
        with self._model.llm.disable_adapter():
            # Generate with balanced settings for quality and consistency
            answer_ids = self._model.generate(
                prompts=prompts,
                max_new_tokens=self._resolve_refine_tokens(cleaned),
            )

        # Type assertion: ids_to_text returns str but lacks type hints
        raw_output: str = self._model.tokenizer.ids_to_text(answer_ids[0].cpu()).strip()
        
        # Extract clean assistant response from chat template format
        refined = self._extract_assistant_response(raw_output, cleaned)
        
        # Validate the refinement output
        refined = self._validate_refinement(cleaned, refined)
        
        return refined

    def _extract_assistant_response(self, raw_output: str, original_text: str = "") -> str:
        """Extract clean assistant response from Qwen chat template format.
        
        Qwen models output in chat template format with markers like:
        - <|im_start|>user ... <|im_end|>
        - <|im_start|>assistant ... <|im_end|>
        - <think>internal reasoning</think> (Qwen's chain-of-thought)
        
        This method strips all template artifacts to return only the final answer.
        Uses regex to remove ALL thinking blocks, not just trailing ones.
        
        Args:
            raw_output: The raw tokenizer output containing chat template
            original_text: The original input text (fallback if extraction fails)
        """
        import re
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
        
        # Step 3: Remove ALL Qwen's <think>...</think> internal reasoning blocks
        # This regex handles:
        # - Multiple thinking blocks
        # - Thinking blocks anywhere in the output (not just at end)
        # - Multi-line thinking content
        output = re.sub(
            r'<think>.*?</think>',
            '',
            output,
            flags=re.DOTALL | re.IGNORECASE
        )
        
        # Step 4: Handle incomplete thinking blocks
        # If <think> exists without matching </think>, the model got stuck
        if "<think>" in output.lower():
            # Take everything BEFORE the <think> tag
            before_think = re.split(r'<think>', output, flags=re.IGNORECASE)[0].strip()
            if before_think and len(before_think) >= 10:
                output = before_think
            else:
                # Nothing useful before <think>
                # Try to salvage by just removing the incomplete <think>... content
                # Sometimes the model outputs: <think>reasoning\nActual output
                # where reasoning continues without </think>
                after_think_match = re.search(r'<think>[^<]*\n+([^<]+)', output, flags=re.IGNORECASE)
                if after_think_match and len(after_think_match.group(1).strip()) >= 10:
                    output = after_think_match.group(1).strip()
                else:
                    logger.warning(
                        "Model entered thinking mode without completing. "
                        "Falling back to original transcript."
                    )
                    return original_text if original_text else ""
        
        # Step 5: Remove any remaining chat template markers
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
        
        # Step 6: Remove common response artifacts/preambles
        # These patterns indicate the model is explaining rather than just outputting
        artifact_patterns = [
            r'^\s*Edited text:\s*',
            r'^\s*Here is the (?:corrected|refined|edited) (?:text|version|transcript):\s*',
            r'^\s*The (?:corrected|refined|edited) (?:text|version|transcript):\s*',
            r'^\s*Corrected text:\s*',
            r'^\s*Refined text:\s*',
            r'^\s*Output:\s*',
        ]
        for pattern in artifact_patterns:
            output = re.sub(pattern, '', output, flags=re.IGNORECASE)
        
        # Step 7: Clean up whitespace
        output = output.strip()
        
        return output

    def _validate_refinement(self, original: str, refined: str) -> str:
        """Validate refinement output is reasonable.
        
        Returns the original text if refinement appears to have failed or
        produced garbage output.
        """
        # If refinement is empty, return original
        if not refined:
            logger.warning("Refinement output is empty, using original")
            return original
        
        # For short inputs (< 50 chars), be more lenient with length comparisons
        # since small changes can result in larger percentage differences
        is_short_input = len(original) < 50
        
        # If refinement is too short compared to original (likely truncated or garbage)
        # Use different thresholds for short vs long inputs
        min_ratio = 0.2 if is_short_input else 0.3
        if len(refined) < len(original) * min_ratio:
            logger.warning(
                f"Refinement output suspiciously short ({len(refined)} vs {len(original)} chars), "
                "using original"
            )
            return original
        
        # If refinement is way too long, it probably includes thinking/explanation
        max_ratio = 3.0 if is_short_input else 2.5
        if len(refined) > len(original) * max_ratio:
            logger.warning(
                f"Refinement output suspiciously long ({len(refined)} vs {len(original)} chars), "
                "using original"
            )
            return original
        
        # Check for obvious artifacts that indicate failed extraction
        artifacts = [
            "here is the corrected",
            "here is the refined",
            "here is the edited",
            "i have corrected",
            "i have refined",
            "the edited version",
            "the corrected version",
            "<think>",
            "</think>",
            "explanation:",
            "changes made:",
            "note:",
        ]
        
        refined_lower = refined.lower()
        for artifact in artifacts:
            if artifact in refined_lower:
                logger.warning(f"Refinement contains artifact '{artifact}', using original")
                return original
        
        # Check if output looks like it's mostly prompt leakage
        prompt_fragments = [
            "refine the following transcript",
            "correcting grammar and punctuation",
            "removing filler words",
            "maintaining the speaker",
            "text to edit:",
        ]
        
        if any(frag in refined_lower for frag in prompt_fragments):
            logger.warning("Refinement contains prompt leakage, using original")
            return original
        
        return refined

    # Internals ---------------------------------------------------------
    def _lazy_model(self) -> None:
        if self._model is not None:
            return
        
        import os
        import sys
        
        # Suppress ALL stdout/stderr during model loading at OS level
        # This catches: NumExpr "detected N cores", OneLogger initialization,
        # and libraries that write directly to file descriptors (bypassing sys.stdout)
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        old_stdout_fd = os.dup(1)
        old_stderr_fd = os.dup(2)
        os.dup2(devnull_fd, 1)
        os.dup2(devnull_fd, 2)
        
        try:
            import torch  # pragma: no cover - optional
            from nemo.collections.speechlm2.models import SALM  # type: ignore[import-untyped]  # pragma: no cover - optional
            
            # Set NeMo log level AFTER import (env vars don't work for NeMo)
            _set_nemo_log_level_after_import()
            
            cache_dir = Path(self.config.model_cache_dir).expanduser() if self.config.model_cache_dir else None
            if cache_dir:
                cache_dir.mkdir(parents=True, exist_ok=True)

            # Map compute_type to torch dtype to prevent float32 auto-loading
            dtype_map = {
                "float32": torch.float32,
                "float16": torch.float16,
                "bfloat16": torch.bfloat16,
            }
            target_dtype = dtype_map.get(self.config.compute_type, torch.bfloat16)
            device = self._resolve_device(torch, self.device)

            # Load model with explicit dtype to prevent memory leak
            model = SALM.from_pretrained(self.model_name)
            
            # Convert to target dtype BEFORE moving to device to avoid double allocation
            model = model.to(dtype=target_dtype)
            model = model.to(device=device)
            
            # Enable eval mode for inference optimizations
            model = model.eval()
            
            self._model = model
            self._audio_tag = getattr(model, "audio_locator_tag", "<|audioplaceholder|>")
            
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise DependencyError(
                "Missing dependencies for Canary-Qwen SALM. Install NeMo trunk (requires torch>=2.6): "
                "pip install \"nemo_toolkit[asr,tts] @ git+https://github.com/NVIDIA/NeMo.git\"\n"
                "Then run: vociferous deps check --engine canary_qwen"
            ) from exc
        except Exception as exc:  # pragma: no cover - optional guard
            raise DependencyError(
                f"Failed to load Canary-Qwen model '{self.config.model_name}': {exc}\n"
                "Ensure NeMo toolkit is installed from trunk."
            ) from exc
        finally:
            # Always restore stdout/stderr at OS level
            os.dup2(old_stdout_fd, 1)
            os.dup2(old_stderr_fd, 2)
            os.close(devnull_fd)
            os.close(old_stdout_fd)
            os.close(old_stderr_fd)

    def _load_audio_bytes(self, audio_path: Path) -> bytes:
        try:
            import wave

            with wave.open(str(audio_path), "rb") as wf:
                return wf.readframes(wf.getnframes())
        except Exception:
            return audio_path.read_bytes()

    @staticmethod
    def _estimate_duration(data: bytes, sample_rate: int = 16000) -> float:
        """Estimate audio duration from PCM16 byte data.
        
        Args:
            data: Raw PCM16 audio bytes
            sample_rate: Audio sample rate in Hz (default: 16000)
            
        Returns:
            Duration in seconds
        """
        if not data:
            return 0.0
        # PCM16 audio stores one sample per 2 bytes
        samples = len(data) / 2
        return float(samples) / float(sample_rate)

    @staticmethod
    def _resolve_device(torch_module: Any, requested: str) -> Any:
        """Resolve requested device to torch.device.
        
        Args:
            torch_module: The torch module
            requested: Requested device ("cpu", "cuda", or "auto")
            
        Returns:
            torch.device instance
        """
        if requested == "cpu":
            return torch_module.device("cpu")
        if requested == "cuda" and torch_module.cuda.is_available():
            return torch_module.device("cuda")
        # auto or unavailable cuda falls back to best available
        return torch_module.device("cuda" if torch_module.cuda.is_available() else "cpu")

    @staticmethod
    def _resolve_asr_tokens(options: TranscriptionOptions | None) -> int:
        """Resolve max_new_tokens for ASR from options.
        
        Args:
            options: Transcription options (may contain max_new_tokens param)
            
        Returns:
            Token limit (default: 256)
        """
        if options is None or not options.params:
            return 256
        try:
            raw = options.params.get("max_new_tokens")
            if raw is not None:
                tokens = int(raw)
                # Clamp to reasonable range
                return max(64, min(tokens, 4096))
            return 256
        except (TypeError, ValueError):
            return 256

    @staticmethod
    def _resolve_refine_tokens(text: str) -> int:
        """Calculate appropriate token limit for refinement.
        
        Refined text is typically similar length to input, with some
        expansion for improved grammar. Uses conservative estimate.
        
        Args:
            text: Input text to be refined
            
        Returns:
            Token limit for generation (512-2048 range)
        """
        if not text:
            return 512
        # Approximate 4 characters per token (conservative)
        # Allow 50% expansion for grammatical improvements
        estimated_tokens = int(len(text) / 4 * 1.5)
        return max(512, min(estimated_tokens, 2048))
