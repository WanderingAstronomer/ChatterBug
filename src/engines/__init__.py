"""ASR engine adapters implementing the domain TranscriptionEngine Protocol."""

from .factory import EngineBuilder, build_engine  # noqa: F401
from .whisper_turbo import WhisperTurboEngine  # noqa: F401
from .voxtral_local import VoxtralLocalEngine  # noqa: F401
