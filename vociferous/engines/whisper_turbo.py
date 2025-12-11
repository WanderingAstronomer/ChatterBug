from __future__ import annotations

import logging
import wave
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from vociferous.domain.model import (
    DEFAULT_MODEL_CACHE_DIR,
    EngineConfig,
    EngineMetadata,
    TranscriptSegment,
    TranscriptionEngine,
    TranscriptionOptions,
)
from vociferous.domain.exceptions import DependencyError, ConfigurationError
from vociferous.engines.cuda_utils import ensure_cuda_libs_available
from vociferous.engines.hardware import get_optimal_device, get_optimal_compute_type
from vociferous.engines.model_registry import normalize_model_name

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

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
    """Simplified faster-whisper engine for CPU/GPU batch transcription."""

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        self.model_name = normalize_model_name("whisper_turbo", config.model_name)
        
        # Device/compute defaults
        self.device = config.device if config.device != "auto" else get_optimal_device()
        self.precision = config.compute_type if config.compute_type != "auto" else get_optimal_compute_type(self.device)
        
        cache_root = Path(config.model_cache_dir or DEFAULT_MODEL_CACHE_DIR).expanduser()
        cache_root.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_root
        
        self._model: WhisperModel | None = None
        self._lazy_model()

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            model_name=self.model_name,
            device=self.device,
            precision=self.precision,
        )

    def transcribe_file(self, audio_path: Path, options: TranscriptionOptions | None = None) -> list[TranscriptSegment]:
        """Transcribe entire audio file in batch."""
        if self._model is None:
            raise DependencyError("Whisper model not loaded")
        
        audio = load_audio_file(audio_path)

        resolved_options = options or TranscriptionOptions()
        
        # Transcribe with faster-whisper
        # IMPORTANT: vad_filter=False since we use manual VAD (Silero) in audio module
        segments_iter, _ = self._model.transcribe(
            audio,
            language=resolved_options.language if resolved_options.language != "auto" else None,
            beam_size=1,  # Greedy decoding for speed
            word_timestamps=False,
            vad_filter=False,  # Disable internal VAD - we handle VAD manually
        )
        
        # Convert to domain segments
        result_segments: list[TranscriptSegment] = []
        for idx, seg in enumerate(segments_iter):
            result_segments.append(
                TranscriptSegment(
                    id=f"segment-{idx}",
                    start=seg.start,
                    end=seg.end,
                    raw_text=seg.text.strip(),
                )
            )
        
        return result_segments

    def _lazy_model(self) -> None:
        """Lazy-load Whisper model on first use."""
        if self._model is not None:
            return
        
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise DependencyError(
                "faster-whisper required; install with: pip install faster-whisper>=1.0.0"
            ) from exc
        
        # Ensure CUDA libs available if using GPU
        if self.device == "cuda":
            ensure_cuda_libs_available()
        
        logger.info(f"Loading Whisper model: {self.model_name} (device={self.device}, compute={self.precision})")
        
        self._model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=self.precision,
            download_root=str(self.cache_dir),
        )
