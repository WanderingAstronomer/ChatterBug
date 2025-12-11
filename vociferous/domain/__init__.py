"""Dependency-free domain models and protocols for Vociferous."""

from .model import (  # noqa: F401
    AudioChunk,
    EngineConfig,
    EngineKind,
    EngineMetadata,
    TranscriptSegment,
    TranscriptionEngine,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionOptions,
    RefinementEngine,
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
    DependencyError,
)

__all__ = [
    "AudioChunk",
    "EngineConfig",
    "EngineKind",
    "EngineMetadata",
    "TranscriptSegment",
    "TranscriptionEngine",
    "TranscriptionRequest",
    "TranscriptionResult",
    "TranscriptionOptions",
    "RefinementEngine",
    "TranscriptSink",
    "Device",
    "ComputeType",
    "VociferousError",
    "EngineError",
    "AudioDecodeError",
    "ConfigurationError",
    "DependencyError",
]
