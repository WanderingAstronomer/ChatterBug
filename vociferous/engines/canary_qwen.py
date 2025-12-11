from __future__ import annotations

"""
Canary-Qwen 2.5B dual-pass engine (ASR + refinement).

Mocks are disallowed at runtime. If dependencies or downloads fail, the engine
raises a DependencyError so the CLI can fail loudly with guidance.
"""

import logging
from pathlib import Path
from typing import Any

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

    def refine_text(self, raw_text: str, instructions: str | None = None) -> str:
        prompt = instructions or DEFAULT_REFINE_PROMPT
        cleaned = raw_text.strip()
        if not cleaned:
            return ""

        if self._model is None:
            raise DependencyError(
                "Canary-Qwen model not loaded; install NeMo trunk: pip install \"nemo_toolkit[asr,tts] @ git+https://github.com/NVIDIA/NeMo.git\""
            )

        prompts = [[{"role": "user", "content": f"{prompt}\n\n{cleaned}"}]]
        with self._model.llm.disable_adapter():
            answer_ids = self._model.generate(
                prompts=prompts,
                max_new_tokens=self._resolve_refine_tokens(cleaned),
            )

        # Type assertion: ids_to_text returns str but lacks type hints
        refined: str = self._model.tokenizer.ids_to_text(answer_ids[0].cpu()).strip()
        return refined

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
