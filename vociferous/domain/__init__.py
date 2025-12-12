"""Dependency-free domain models and protocols for Vociferous."""

from .constants import (
    ComputeType,
    Device,
)
from .exceptions import (
    AudioDecodeError,
    AudioProcessingError,
    ConfigurationError,
    DependencyError,
    EngineError,
    UnsplittableSegmentError,
    VociferousError,
)
from .model import (
    AudioChunk,
    EngineConfig,
    EngineKind,
    EngineMetadata,
    RefinementEngine,
    TranscriptionEngine,
    TranscriptionOptions,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptSegment,
    TranscriptSink,
)
from .protocols import (
    ProgressCallback,
    ProgressUpdate,
    ProgressUpdateData,
)

__all__ = [
    "AudioChunk",
    "AudioDecodeError",
    "AudioProcessingError",
    "ComputeType",
    "ConfigurationError",
    "DependencyError",
    "Device",
    "EngineConfig",
    "EngineError",
    "EngineKind",
    "EngineMetadata",
    "ProgressCallback",
    "ProgressUpdate",
    "ProgressUpdateData",
    "RefinementEngine",
    "TranscriptSegment",
    "TranscriptSink",
    "TranscriptionEngine",
    "TranscriptionOptions",
    "TranscriptionRequest",
    "TranscriptionResult",
    "UnsplittableSegmentError",
    "VociferousError",
]
