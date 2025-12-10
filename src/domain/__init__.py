"""Dependency-free domain models and protocols for Vociferous."""

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
    VociferousError,
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
    "VociferousError",
    "EngineError",
    "AudioDecodeError",
    "ConfigurationError",
    "SessionError",
    "DependencyError",
]
