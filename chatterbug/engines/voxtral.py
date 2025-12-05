from __future__ import annotations

from pathlib import Path
from typing import Iterable

from chatterbug.domain.model import (
    AudioChunk,
    DEFAULT_MODEL_CACHE_DIR,
    EngineConfig,
    EngineMetadata,
    TranscriptSegment,
    TranscriptionEngine,
    TranscriptionOptions,
)
from chatterbug.domain.exceptions import DependencyError
from chatterbug.engines.model_registry import normalize_model_name


class VoxtralEngine(TranscriptionEngine):
    """Voxtral smart-mode engine for audio understanding."""

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        self.model_name = normalize_model_name("voxtral", config.model_name)
        self.device = config.device
        self.precision = config.compute_type
        cache_root = Path(config.model_cache_dir or DEFAULT_MODEL_CACHE_DIR).expanduser()
        cache_root.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_root
        self._model = None
        self._processor = None

    def _lazy_model(self):
        if self._model is not None:
            return
        try:
            from transformers import VoxtralForConditionalGeneration, AutoProcessor
            import torch
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise DependencyError(
                "transformers and torch are required for VoxtralEngine; install with voxtral extra"
            ) from exc

        self._processor = AutoProcessor.from_pretrained(
            self.model_name, cache_dir=str(self.cache_dir)
        )
        dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
        self._model = VoxtralForConditionalGeneration.from_pretrained(
            self.model_name,
            dtype=dtype,
            cache_dir=str(self.cache_dir),
        ).to(self.device)

    def start(self, options: TranscriptionOptions) -> None:
        self._options = options
        self._buffer = bytearray()
        self._segments = []
        self._lazy_model()

    def push_audio(self, pcm16: bytes, timestamp_ms: int) -> None:
        self._buffer.extend(pcm16)

    def flush(self) -> None:
        if not self._buffer:
            return
        
        import numpy as np
        import torch

        # Process the entire buffer
        audio_np = np.frombuffer(self._buffer, dtype=np.int16).astype("float32") / 32768.0
        
        inputs = self._processor.apply_transcription_request(
            audio=[audio_np],
            language=self._options.language or "en",
            model_id=self.model_name,
            sampling_rate=16000,
            format=["wav"],
        ).to(self.device, dtype=self._model.dtype)

        gen_kwargs = {}
        params = self._options.params
        if "max_new_tokens" in params:
            gen_kwargs["max_new_tokens"] = int(params["max_new_tokens"])
        else:
            gen_kwargs["max_new_tokens"] = 2048

        # Note: temperature is not supported for Voxtral transcription mode
        # and will be ignored by the model

        with torch.inference_mode():
            outputs = self._model.generate(**inputs, **gen_kwargs)
        
        input_length = inputs.input_ids.shape[1]
        new_tokens = outputs[:, input_length:]
        transcription = self._processor.batch_decode(
            new_tokens, skip_special_tokens=True
        )[0]

        if transcription.strip():
            self._segments.append(TranscriptSegment(
                text=transcription.strip(),
                start_s=0.0,
                end_s=len(audio_np) / 16000.0,
                language=self._options.language or "en",
                confidence=1.0
            ))
        
        self._buffer.clear()

    def poll_segments(self) -> list[TranscriptSegment]:
        segs = list(self._segments)
        self._segments.clear()
        return segs

    @property
    def metadata(self) -> EngineMetadata:
        """Return engine metadata for result building."""
        return EngineMetadata(
            model_name=self.model_name,
            device=self.device,
            precision=self.precision,
        )
