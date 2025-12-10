from __future__ import annotations

from pathlib import Path
from typing import Iterable, Iterator, Literal, Mapping, Protocol, Sequence, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .constants import Device, ComputeType

DEFAULT_MODEL_CACHE_DIR = Path.home() / ".cache" / "vociferous" / "models"
DEFAULT_WHISPER_MODEL = "deepdml/faster-whisper-large-v3-turbo-ct2"

# Local engines only; "voxtral" is deprecated alias for "voxtral_local"
EngineKind = Literal["whisper_turbo", "voxtral_local", "voxtral", "canary_qwen"]

# Transcription presets for accuracy vs speed trade-offs
TranscriptionPreset = Literal["high_accuracy", "balanced", "fast"]


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


class SpeechMap(BaseModel):
    """Analysis results from audio preprocessing/VAD.
    
    Contains speech boundaries and silence gap information for
    intelligent audio segmentation.
    """
    model_config = ConfigDict(frozen=True)
    first_speech_ms: int
    last_speech_ms: int
    silence_gaps: Sequence[tuple[int, int, int]] = Field(default_factory=tuple)  # (start_ms, end_ms, duration_ms)
    
    
class PreprocessingConfig(BaseModel):
    """Configuration for audio preprocessing pipeline."""
    model_config = ConfigDict(frozen=True)
    
    # Trimming
    trim_head: bool = True
    trim_tail: bool = True
    head_margin_ms: int = 500
    tail_margin_ms: int = 500
    
    # Splitting
    split_on_gaps: bool = True
    gap_threshold_ms: int = 5000  # Only split at 5+ second gaps
    
    # VAD settings
    energy_threshold_db: float = -40.0
    min_speech_duration_ms: int = 300
    min_silence_duration_ms: int = 500
    
    @field_validator("head_margin_ms", "tail_margin_ms", "gap_threshold_ms", "min_speech_duration_ms", "min_silence_duration_ms")
    @classmethod
    def validate_positive_ms(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Time values must be non-negative")
        return v
    
    @field_validator("energy_threshold_db")
    @classmethod
    def validate_energy_threshold(cls, v: float) -> float:
        if v > 0:
            raise ValueError("Energy threshold must be negative (dB)")
        return v


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(frozen=True)
    text: str
    start_s: float
    end_s: float
    language: str
    confidence: float


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
    model_name: str = DEFAULT_WHISPER_MODEL
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
    preset: TranscriptionPreset | None = None
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
    def stream(self) -> Iterator[AudioChunk]:
        ...


@runtime_checkable
class TranscriptionEngine(Protocol):
    """
    Stateful, push-based ASR engine protocol.
    """
    config: EngineConfig
    model_name: str

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

    @property
    def metadata(self) -> EngineMetadata:
        """Return engine metadata for result building."""
        ...


@runtime_checkable
class TranscriptSink(Protocol):
    def handle_segment(self, segment: TranscriptSegment) -> None:
        ...

    def complete(self, result: TranscriptionResult) -> None:
        ...
