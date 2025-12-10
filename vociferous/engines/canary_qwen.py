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
from vociferous.domain.exceptions import ConfigurationError, DependencyError
from vociferous.engines.model_registry import normalize_model_name

logger = logging.getLogger(__name__)


def _bool_param(params: Mapping[str, str], key: str, default: bool) -> bool:
    raw = params.get(key)
    if raw is None:
        return default
    return str(raw).strip().lower() == "true"


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
        params = {k.lower(): v for k, v in (config.params or {}).items()}
        if _bool_param(params, "use_mock", False):
            raise ConfigurationError("Mock mode is disabled for Canary-Qwen. Remove params.use_mock=true.")
        self.use_mock = False
        self._model: Any | None = None
        self._processor: Any | None = None
        self._lazy_model()

    @property
    def metadata(self) -> EngineMetadata:  # pragma: no cover - simple data accessor
        return EngineMetadata(
            model_name=self.model_name,
            device=self.device,
            precision=self.precision,
        )

    # Batch interface ----------------------------------------------------
    def transcribe_file(self, audio_path: Path, options: TranscriptionOptions) -> list[TranscriptSegment]:
        pcm_bytes = self._load_audio_bytes(audio_path)
        transcript_text = self._transcribe_bytes(pcm_bytes)
        duration_s = self._estimate_duration(pcm_bytes)
        language = options.language if options and options.language else "en"
        segment = TranscriptSegment(
            text=transcript_text,
            start_s=0.0,
            end_s=duration_s,
            language=language,
            confidence=0.0,
        )
        return [segment]

    def refine_text(self, raw_text: str, instructions: str | None = None) -> str:
        prompt = instructions or DEFAULT_REFINE_PROMPT
        cleaned = raw_text.strip()
        if not cleaned:
            return ""

        if self._model is None or self._processor is None:
            raise DependencyError("Canary-Qwen model not loaded; install transformers/torch/accelerate and retry.")

        # Real refinement path placeholder; keep API stable for future model wiring.
        return cleaned if cleaned else ""

    # Internals ---------------------------------------------------------
    def _lazy_model(self) -> None:
        if self._model is not None:
            return
        try:
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor  # pragma: no cover - optional
            import torch  # pragma: no cover - optional
        except ImportError:  # pragma: no cover - dependency guard
            raise DependencyError(
                "Missing dependencies for Canary-Qwen. Install with: pip install 'transformers' 'torch' 'accelerate'"
            )

        cache_dir = Path(self.config.model_cache_dir).expanduser() if self.config.model_cache_dir else None
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

        try:
            self._processor = AutoProcessor.from_pretrained(self.model_name, cache_dir=cache_dir)
            self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
                self.model_name,
                torch_dtype=self._resolve_dtype(torch, self.precision),
                cache_dir=cache_dir,
            )
            self._model.to(self.device if self.device != "auto" else "cpu")
        except Exception as exc:  # pragma: no cover - optional guard
            raise DependencyError(
                f"Failed to load Canary-Qwen model '{self.model_name}': {exc}\n"
                "Ensure the model is accessible and dependencies are installed."
            ) from exc

    def _transcribe_bytes(self, data: bytes) -> str:
        if not data:
            return ""
        if self._model is None or self._processor is None:
            raise DependencyError("Canary-Qwen model not loaded; install dependencies and retry.")

        import torch  # pragma: no cover - optional heavy path
        import numpy as np  # pragma: no cover - optional heavy path

        samples = np.frombuffer(data, dtype=np.int16).astype("float32")
        max_val = float(np.iinfo(np.int16).max)
        samples = samples / (max_val + 1.0)
        array = torch.from_numpy(samples)
        inputs = self._processor(array, sampling_rate=16000, return_tensors="pt")
        inputs = {k: v.to(self._model.device) for k, v in inputs.items()}
        with torch.no_grad():
            generated_ids = self._model.generate(**inputs, max_length=256)
        transcription = self._processor.batch_decode(generated_ids, skip_special_tokens=True)
        return transcription[0] if transcription else ""

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
    def _resolve_dtype(torch_module: Any, precision: str) -> Any:
        mapping: Mapping[str, Any] = {
            "float16": getattr(torch_module, "float16", None),
            "fp16": getattr(torch_module, "float16", None),
            "float32": getattr(torch_module, "float32", None),
            "fp32": getattr(torch_module, "float32", None),
            "bfloat16": getattr(torch_module, "bfloat16", None),
        }
        return mapping.get(precision, torch_module.float32)
