"""Dependency-free domain models and protocols for ChatterBug."""

from .model import (  # noqa: F401
    AudioChunk,
    AudioSource,
    EngineConfig,
    EngineKind,
    EngineMetadata,
    TranscriptSegment,
    TranscriptionEngine,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionOptions,
    TranscriptSink,
)
from .constants import (  # noqa: F401
    Device,
    ComputeType,
)
from .exceptions import (  # noqa: F401
    ChatterBugError,
    EngineError,
    AudioDecodeError,
    ConfigurationError,
    SessionError,
    DependencyError,
)

__all__ = [
    "AudioChunk",
    "AudioSource",
    "EngineConfig",
    "EngineKind",
    "EngineMetadata",
    "TranscriptSegment",
    "TranscriptionEngine",
    "TranscriptionRequest",
    "TranscriptionResult",
    "TranscriptionOptions",
    "TranscriptSink",
    "Device",
    "ComputeType",
    "ChatterBugError",
    "EngineError",
    "AudioDecodeError",
    "ConfigurationError",
    "SessionError",
    "DependencyError",
]
