"""Audio processing primitives."""

from . import utilities
from .decoder import AudioDecoder, DecodedAudio, FfmpegDecoder, WavDecoder
from .ffmpeg_condenser import FFmpegCondenser
from .preprocessing import (
    AudioPreprocessor,
    PreprocessingConfig,
    preprocess_audio,
)
from .recorder import MicrophoneRecorder, SoundDeviceRecorder
from .silero_vad import SileroVAD
from .utilities import (
    apply_noise_gate,
    chunk_pcm_bytes,
    trim_trailing_silence,
)

__all__ = [
    "AudioDecoder",
    "AudioPreprocessor",
    "DecodedAudio",
    "FFmpegCondenser",
    "FfmpegDecoder",
    "MicrophoneRecorder",
    "PreprocessingConfig",
    "SileroVAD",
    "SoundDeviceRecorder",
    "WavDecoder",
    "apply_noise_gate",
    "chunk_pcm_bytes",
    "preprocess_audio",
    "trim_trailing_silence",
    "utilities",
]
