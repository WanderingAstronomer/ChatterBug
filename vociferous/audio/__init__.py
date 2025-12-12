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
from .validation import (
    SUPPORTED_EXTENSIONS,
    AudioFileInfo,
    is_supported_format,
    validate_audio_file,
)

__all__ = [
    "AudioDecoder",
    "AudioFileInfo",
    "AudioPreprocessor",
    "DecodedAudio",
    "FFmpegCondenser",
    "FfmpegDecoder",
    "MicrophoneRecorder",
    "PreprocessingConfig",
    "SUPPORTED_EXTENSIONS",
    "SileroVAD",
    "SoundDeviceRecorder",
    "WavDecoder",
    "apply_noise_gate",
    "chunk_pcm_bytes",
    "is_supported_format",
    "preprocess_audio",
    "trim_trailing_silence",
    "utilities",
    "validate_audio_file",
]
