"""
Official OpenAI Whisper engine for local ASR.

Uses the official openai-whisper package (NOT faster-whisper, NOT CTranslate2).
Supports Whisper Turbo, V3, and Large models.
"""

from __future__ import annotations

import logging
import wave
from pathlib import Path
from typing import Any

import numpy as np

from vociferous.domain.exceptions import DependencyError
from vociferous.domain.model import (
    DEFAULT_MODEL_CACHE_DIR,
    EngineConfig,
    EngineMetadata,
    TranscriptionEngine,
    TranscriptionOptions,
    TranscriptSegment,
)
from vociferous.engines.hardware import get_optimal_device
from vociferous.engines.model_registry import normalize_model_name

logger = logging.getLogger(__name__)

PCM16_SCALE = 32768.0


def load_audio_file(audio_path: Path) -> np.ndarray:
    """Load 16kHz mono PCM WAV file as normalized float32 numpy array."""
    with wave.open(str(audio_path), "rb") as wf:
        if wf.getnchannels() != 1:
            raise ValueError(f"Expected mono audio, got {wf.getnchannels()} channels")
        if wf.getsampwidth() != 2:
            raise ValueError(f"Expected 16-bit audio, got {wf.getsampwidth() * 8}-bit")
        if wf.getframerate() != 16000:
            raise ValueError(f"Expected 16kHz audio, got {wf.getframerate()}Hz")
        frames = wf.readframes(wf.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / PCM16_SCALE


class WhisperTurboEngine(TranscriptionEngine):
    """Official OpenAI Whisper engine for CPU/GPU batch transcription.
    
    Uses the official openai-whisper package. Supports Turbo, V3, and Large models.
    Does NOT use faster-whisper or CTranslate2.
    """

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        self.model_name = normalize_model_name("whisper_turbo", config.model_name)
        
        # Device defaults (OpenAI Whisper uses "cuda" or "cpu")
        self.device = config.device if config.device != "auto" else get_optimal_device()
        self.precision = config.compute_type if config.compute_type != "auto" else "float16"
        
        cache_root = Path(config.model_cache_dir or DEFAULT_MODEL_CACHE_DIR).expanduser()
        cache_root.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_root
        
        self._model: Any = None
        self._lazy_model()

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            model_name=self.model_name,
            device=self.device,
            precision=self.precision,
        )

    def transcribe_file(self, audio_path: Path, options: TranscriptionOptions | None = None) -> list[TranscriptSegment]:
        """Transcribe entire audio file in batch using official Whisper."""
        if self._model is None:
            raise DependencyError("Whisper model not loaded")
        
        resolved_options = options or TranscriptionOptions()
        
        # Official Whisper transcribe() accepts file path directly
        # It handles audio loading internally
        result = self._model.transcribe(
            str(audio_path),
            language=resolved_options.language if resolved_options.language != "auto" else None,
            fp16=(self.device == "cuda" and self.precision in ("float16", "fp16")),
        )
        
        # Convert to domain segments
        result_segments: list[TranscriptSegment] = []
        for idx, seg in enumerate(result.get("segments", [])):
            result_segments.append(
                TranscriptSegment(
                    id=f"segment-{idx}",
                    start=seg["start"],
                    end=seg["end"],
                    raw_text=seg["text"].strip(),
                )
            )
        
        return result_segments

    def _lazy_model(self) -> None:
        """Lazy-load official Whisper model on first use."""
        if self._model is not None:
            return
        
        try:
            import whisper
        except ImportError as exc:
            raise DependencyError(
                "openai-whisper required; install with: pip install openai-whisper"
            ) from exc
        
        logger.info(f"Loading Whisper model: {self.model_name} (device={self.device})")
        
        # Official Whisper uses model size names: "turbo", "large-v3", "large", "medium", "small", "base", "tiny"
        self._model = whisper.load_model(
            self.model_name,
            device=self.device,
            download_root=str(self.cache_dir),
        )
