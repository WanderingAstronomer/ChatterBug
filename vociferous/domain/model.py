from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal, Mapping, Protocol, Sequence, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .constants import Device, ComputeType

DEFAULT_MODEL_CACHE_DIR = Path.home() / ".cache" / "vociferous" / "models"
DEFAULT_WHISPER_MODEL = "deepdml/faster-whisper-large-v3-turbo-ct2"
DEFAULT_CANARY_MODEL = "nvidia/canary-qwen-2.5b"

# Supported engines: canary_qwen (GPU-optimized), whisper_turbo (CPU-friendly)
EngineKind = Literal["canary_qwen", "whisper_turbo"]


@dataclass(frozen=True, slots=True)
class SegmentationProfile:
    """VAD + condensation parameters used for canonical workflows."""

    threshold: float = 0.5
    min_silence_ms: int = 500
    min_speech_ms: int = 250
    speech_pad_ms: int = 250
    max_speech_duration_s: float = 40.0
    boundary_margin_ms: int = 250
    min_gap_for_split_s: float = 2.0
    sample_rate: int = 16000
    device: str = "cpu"

    def __post_init__(self) -> None:
        if not (0.0 < self.threshold < 1.0):
            raise ValueError("threshold must be between 0 and 1")
        for name, value in (
            ("min_silence_ms", self.min_silence_ms),
            ("min_speech_ms", self.min_speech_ms),
            ("speech_pad_ms", self.speech_pad_ms),
            ("boundary_margin_ms", self.boundary_margin_ms),
        ):
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.max_speech_duration_s <= 0:
            raise ValueError("max_speech_duration_s must be positive")
        if self.min_gap_for_split_s < 0:
            raise ValueError("min_gap_for_split_s must be non-negative")
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")


def _sanitize_params(params: Mapping[str, str] | None) -> dict[str, str]:
    """Remove empty/whitespace-only values from params to avoid engine confusion."""
    if not params:
        return {}
    return {k: v for k, v in params.items() if v and v.strip()}


class AudioChunk(BaseModel):
    model_config = ConfigDict(frozen=True)
    samples: bytes
    sample_rate: int
    channels: int
    start_s: float
    end_s: float


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    """Immutable transcript span with optional refinement metadata.

    `text`/`start_s`/`end_s` legacy accessors remain for backward compatibility.
    """

    id: str = field(default_factory=lambda: uuid4().hex)
    start: float = 0.0
    end: float = 0.0
    raw_text: str = ""
    refined_text: str | None = None
    language: str | None = None
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < 0:
            raise ValueError("start/end must be non-negative")
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")

    @property
    def text(self) -> str:
        """Legacy accessor preferring refined text when available."""
        return self.refined_text or self.raw_text

    @property
    def start_s(self) -> float:
        return self.start

    @property
    def end_s(self) -> float:
        return self.end

    def with_refined(self, refined_text: str) -> "TranscriptSegment":
        """Return a copy with `refined_text` set; leaves other fields unchanged."""
        return replace(self, refined_text=refined_text)


class EngineMetadata(BaseModel):
    """Metadata about a transcription engine instance.

    This provides a type-safe way for engines to expose their configuration
    and runtime information, avoiding the need for attribute introspection.
    """
    model_config = ConfigDict(frozen=True)
    model_name: str
    device: str
    precision: str


class EngineConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    model_name: str = DEFAULT_CANARY_MODEL
    compute_type: str = "auto"
    device: str = "auto"
    model_cache_dir: str | None = str(DEFAULT_MODEL_CACHE_DIR)
    params: Mapping[str, str] = Field(default_factory=dict)

    @field_validator("params", mode="before")
    @classmethod
    def sanitize_params(cls, v: Mapping[str, str] | None) -> dict[str, str]:
        return _sanitize_params(v)

    @field_validator("device")
    @classmethod
    def validate_device(cls, v: str) -> str:
        valid_devices = {d.value for d in Device}
        if v not in valid_devices:
            raise ValueError(f"Invalid device: {v}; must be cpu, cuda, or auto")
        return v

    @field_validator("compute_type")
    @classmethod
    def validate_compute_type(cls, v: str) -> str:
        if v == "auto":
            return v
        valid_types = {ct.value for ct in ComputeType}
        if v not in valid_types:
            raise ValueError(f"Invalid compute_type: {v}; must be one of {', '.join(valid_types)} or auto")
        return v


class TranscriptionOptions(BaseModel):
    model_config = ConfigDict(frozen=True)
    language: str = "en"
    max_duration_s: float | None = None
    beam_size: int | None = None
    temperature: float | None = None
    prompt: str | None = None
    params: Mapping[str, str] = Field(default_factory=dict)

    @field_validator("params", mode="before")
    @classmethod
    def sanitize_params(cls, v: Mapping[str, str] | None) -> dict[str, str]:
        return _sanitize_params(v)

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        v = v.lower().strip()
        if v == "auto":
            return v
        if len(v) != 2 or not v.isalpha():
            raise ValueError(
                f"Invalid language code '{v}'. Must be a 2-letter ISO 639-1 code (e.g., 'en', 'es', 'fr') or 'auto'."
            )
        return v

    @field_validator("beam_size")
    @classmethod
    def validate_beam_size(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("beam_size must be >= 1")
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 2.0):
            raise ValueError("temperature must be between 0.0 and 2.0")
        return v

    @field_validator("max_duration_s")
    @classmethod
    def validate_max_duration_s(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("max_duration_s must be positive")
        return v


@dataclass(frozen=True, slots=True)
class EngineProfile:
    """Engine selection and options for workflows."""

    kind: EngineKind
    config: EngineConfig = field(default_factory=EngineConfig)
    options: TranscriptionOptions = field(default_factory=TranscriptionOptions)


class TranscriptionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    audio_path: Path
    engine: EngineKind = "canary_qwen"
    engine_config: EngineConfig = Field(default_factory=EngineConfig)
    options: TranscriptionOptions = Field(default_factory=TranscriptionOptions)
    metadata: Mapping[str, str] = Field(default_factory=dict)


class TranscriptionResult(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    text: str
    segments: Sequence[TranscriptSegment]
    model_name: str
    device: str
    precision: str
    engine: EngineKind
    duration_s: float
    warnings: Sequence[str] = Field(default_factory=tuple)


@runtime_checkable
class TranscriptionEngine(Protocol):
    """Batch-only transcription engine protocol: file in → segments out."""

    config: EngineConfig
    model_name: str

    def transcribe_file(self, audio_path: Path, options: TranscriptionOptions | None = None) -> list[TranscriptSegment]:
        """Transcribe a preprocessed audio file in a single batch."""
        ...

    @property
    def metadata(self) -> EngineMetadata:
        """Return engine metadata for result building."""
        ...


@runtime_checkable
class RefinementEngine(Protocol):
    """Text-only refinement engine operating on transcript segments."""

    name: str

    def refine_segments(self, segments: list[TranscriptSegment], instructions: str | None = None) -> list[TranscriptSegment]:
        ...


@runtime_checkable
class TranscriptSink(Protocol):
    def handle_segment(self, segment: TranscriptSegment) -> None:
        ...

    def complete(self, result: TranscriptionResult) -> None:
        ...
