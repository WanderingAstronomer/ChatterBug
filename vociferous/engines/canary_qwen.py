from __future__ import annotations

"""
Lightweight Canary-Qwen 2.5B engine wrapper.

This implementation is intentionally dependency-light and defaults to a mock
path that does not download large models during tests. When torch/transformers
are available and `use_mock` is set to false, the class can be extended to load
the real model.
"""

from pathlib import Path
from typing import Any, Mapping

from vociferous.domain.model import (
    EngineConfig,
    EngineMetadata,
    TranscriptSegment,
    TranscriptionEngine,
    TranscriptionOptions,
)
from vociferous.engines.model_registry import normalize_model_name


class CanaryQwenEngine(TranscriptionEngine):
    """Minimal dual-mode stub that fits the streaming engine protocol."""

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        self.model_name = normalize_model_name("canary_qwen", config.model_name)
        self.device = config.device
        self.precision = config.compute_type
        params = {k.lower(): v for k, v in (config.params or {}).items()}
        self.mode = params.get("mode", "asr")
        self.use_mock = params.get("use_mock", "true").lower() != "false"
        self._buffer = bytearray()
        self._segments: list[TranscriptSegment] = []
        self._options: TranscriptionOptions | None = None
        self._model: Any | None = None
        self._processor: Any | None = None
        self._pending_text: str = ""
        self._last_timestamp_ms: int = 0

    # Streaming protocol -------------------------------------------------
    def start(self, options: TranscriptionOptions) -> None:
        self._options = options
        self._buffer = bytearray()
        self._segments = []
        self._pending_text = ""
        if not self.use_mock:
            self._lazy_model()

    def push_audio(self, pcm16: bytes, timestamp_ms: int) -> None:
        self._buffer.extend(pcm16)
        self._last_timestamp_ms = timestamp_ms

    def flush(self) -> None:
        if self.mode == "llm":
            text_input = self._pending_text.strip()
            if not text_input:
                return
            text = self.refine_text(text_input)
            duration_s = 0.0
            self._pending_text = ""
        else:
            if not self._buffer:
                return
            text = self._transcribe_bytes(self._buffer)
            duration_s = self._estimate_duration(self._buffer)
            self._buffer = bytearray()

        language = self._options.language if self._options else "en"
        segment = TranscriptSegment(
            text=text,
            start_s=0.0,
            end_s=duration_s,
            language=language,
            confidence=1.0 if self.use_mock else 0.0,
        )
        self._segments.append(segment)

    def poll_segments(self) -> list[TranscriptSegment]:
        segments = list(self._segments)
        self._segments.clear()
        return segments

    @property
    def metadata(self) -> EngineMetadata:  # pragma: no cover - simple data accessor
        return EngineMetadata(
            model_name=self.model_name,
            device=self.device,
            precision=self.precision,
        )

    # Convenience methods -----------------------------------------------
    def transcribe_file(self, audio_path: Path, options: TranscriptionOptions) -> list[TranscriptSegment]:
        pcm_bytes = self._load_audio_bytes(audio_path)
        self.start(options)
        self.push_audio(pcm_bytes, 0)
        self.flush()
        return self.poll_segments()

    def refine_text(self, raw_text: str, instructions: str | None = None) -> str:
        if not instructions:
            instructions = (
                "Fix any transcription errors, add punctuation, and improve readability "
                "without changing the meaning."
            )
        cleaned = raw_text.strip()
        if not cleaned:
            return ""
        # Minimal refinement: ensure sentence-style output.
        if len(cleaned) == 1:
            refined = cleaned.upper()
        else:
            refined = cleaned[0].upper() + cleaned[1:]
        if not refined.rstrip().endswith((".", "!", "?")):
            refined = refined.rstrip() + "."
        if self.use_mock:
            decorated = f"{refined} ({instructions})"
            if not decorated.endswith((".", "!", "?")):
                decorated = decorated.rstrip() + "."
            return decorated
        return refined

    def set_text_input(self, text: str) -> None:
        """Provide text directly for LLM-only mode without touching audio buffers."""
        self._pending_text = text or ""

    # Internals ---------------------------------------------------------
    def _lazy_model(self) -> None:
        if self._model is not None or self.use_mock:
            return
        try:
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor  # pragma: no cover - optional
            import torch  # pragma: no cover - optional
        except ImportError:  # pragma: no cover - dependency guard
            self.use_mock = True
            return

        try:
            self._processor = AutoProcessor.from_pretrained(self.model_name)
            self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
                self.model_name,
                torch_dtype=self._resolve_dtype(torch, self.precision),
            )
            self._model.to(self.device if self.device != "auto" else "cpu")
        except Exception:  # pragma: no cover - optional guard
            self.use_mock = True
            self._processor = None
            self._model = None

    def _transcribe_bytes(self, data: bytes) -> str:
        if not data:
            return ""
        if self.use_mock or self._model is None or self._processor is None:
            duration = self._estimate_duration(data)
            return f"Canary-Qwen mock transcript (~{duration:.1f}s of audio)"

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
