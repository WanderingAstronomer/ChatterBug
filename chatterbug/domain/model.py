from __future__ import annotations

from pathlib import Path
from typing import Iterable, Literal, Mapping, Protocol, Sequence, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_MODEL_CACHE_DIR = Path.home() / ".cache" / "chatterbug" / "models"

EngineKind = Literal["whisper_turbo", "voxtral", "parakeet_rnnt"]


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


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(frozen=True)
    text: str
    start_s: float
    end_s: float
    language: str
    confidence: float


class EngineConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    model_name: str = "distil-whisper/distil-large-v3"
    compute_type: str = "int8"
    device: str = "cpu"
    model_cache_dir: str | None = str(DEFAULT_MODEL_CACHE_DIR)
    params: Mapping[str, str] = Field(default_factory=dict)

    @field_validator("params", mode="before")
    @classmethod
    def sanitize_params(cls, v: Mapping[str, str] | None) -> dict[str, str]:
        return _sanitize_params(v)

    @field_validator("device")
    @classmethod
    def validate_device(cls, v: str) -> str:
        if v not in ("cpu", "cuda", "auto"):
            raise ValueError(f"Invalid device: {v}; must be cpu, cuda, or auto")
        return v

    @field_validator("compute_type")
    @classmethod
    def validate_compute_type(cls, v: str) -> str:
        valid_types = ("int8", "int8_float16", "float16", "float32", "fp16", "fp32")
        if v not in valid_types:
            raise ValueError(f"Invalid compute_type: {v}")
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


class TranscriptionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    source: "AudioSource"
    engine: EngineKind = "whisper_turbo"
    engine_config: EngineConfig = Field(default_factory=EngineConfig)
    options: TranscriptionOptions = Field(default_factory=TranscriptionOptions)
    metadata: Mapping[str, str] = Field(default_factory=dict)


class TranscriptionResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    text: str
    segments: Sequence[TranscriptSegment]
    model_name: str
    device: str
    precision: str
    engine: EngineKind
    duration_s: float
    warnings: Sequence[str] = Field(default_factory=tuple)


@runtime_checkable
class AudioSource(Protocol):
    def stream(self) -> Iterable[AudioChunk]:
        ...


@runtime_checkable
class TranscriptionEngine(Protocol):
    """
    Stateful, push-based ASR engine protocol.
    """
    def start(self, options: TranscriptionOptions) -> None:
        """Initialize the engine with session-specific options."""
        ...

    def push_audio(self, pcm16: bytes, timestamp_ms: int) -> None:
        """Append raw 16 kHz mono PCM16 audio to the internal buffer."""
        ...

    def flush(self) -> None:
        """Force processing of whatever is currently buffered."""
        ...

    def poll_segments(self) -> list[TranscriptSegment]:
        """Return any new segments produced since last call."""
        ...


@runtime_checkable
class TranscriptSink(Protocol):
    def handle_segment(self, segment: TranscriptSegment) -> None:
        ...

    def complete(self, result: TranscriptionResult) -> None:
        ...
