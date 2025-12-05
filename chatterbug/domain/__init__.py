"""Dependency-free domain models and protocols for ChatterBug."""

from .model import (  # noqa: F401
    AudioChunk,
    AudioSource,
    EngineConfig,
    EngineKind,
    TranscriptSegment,
    TranscriptionEngine,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionOptions,
    TranscriptSink,
)
from .exceptions import (  # noqa: F401
    ChatterBugError,
    EngineError,
    AudioDecodeError,
    ConfigurationError,
    SessionError,
    DependencyError,
)
