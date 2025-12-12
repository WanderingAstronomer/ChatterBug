from __future__ import annotations

import logging
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path

import tomli_w
from pydantic import BaseModel, Field, field_validator, model_validator

from vociferous.config.migrations import migrate_raw_config
from vociferous.domain.model import (
    DEFAULT_CANARY_MODEL,
    DEFAULT_MODEL_CACHE_DIR,
    DEFAULT_WHISPER_MODEL,
    EngineConfig,
    EngineKind,
    EngineProfile,
    SegmentationProfile,
    TranscriptionOptions,
)

logger = logging.getLogger(__name__)


class ArtifactConfig(BaseModel):
    """Configuration for intermediate artifact handling."""

    cleanup_intermediates: bool = Field(
        default=True,
        description="Delete intermediate files after successful transcription",
    )
    keep_on_error: bool = Field(
        default=True,
        description="Keep intermediate files when a step fails (for debugging)",
    )
    output_directory: Path = Field(
        default=Path("."),
        description="Directory to write intermediate artifacts",
    )
    naming_pattern: str = Field(
        default="{input_stem}_{step}.{ext}",
        description="Filename pattern for intermediate artifacts",
    )


class EngineProfileConfig(BaseModel):
    """Declarative engine profile mapping to EngineProfile dataclass."""

    kind: EngineKind
    model_name: str = DEFAULT_CANARY_MODEL
    compute_type: str = "auto"
    device: str = "auto"
    model_cache_dir: str | None = Field(default_factory=lambda: str(DEFAULT_MODEL_CACHE_DIR))
    params: Mapping[str, str] = Field(default_factory=dict)
    max_audio_chunk_seconds: float | None = None
    language: str = "en"

    def to_profile(self) -> EngineProfile:
        model_name = self.model_name
        # Guardrail: ensure Canary engine uses official model
        if self.kind == EngineKind.canary_qwen:
            model_name = DEFAULT_CANARY_MODEL

        engine_config = EngineConfig(
            model_name=model_name,
            compute_type=self.compute_type,
            device=self.device,
            model_cache_dir=self.model_cache_dir,
            params=self.params,
        )
        options = TranscriptionOptions(language=self.language, max_duration_s=self.max_audio_chunk_seconds)
        return EngineProfile(kind=self.kind, config=engine_config, options=options)


class SegmentationProfileConfig(BaseModel):
    """Declarative segmentation profile for Silero VAD + intelligent chunking.
    
    This profile controls both Voice Activity Detection and the audio chunking
    system that splits long files into engine-compatible segments.
    """

    # VAD parameters
    threshold: float = 0.5
    min_silence_ms: int = 500
    min_speech_ms: int = 250
    speech_pad_ms: int = 250
    sample_rate: int = 16000
    device: str = "cpu"
    vad_model: str | None = None
    
    # Chunking parameters (new intelligent splitting system)
    max_chunk_s: float = Field(
        default=60.0,
        description="Hard ceiling for chunk duration (seconds)",
        ge=10.0,
        le=300.0,
    )
    chunk_search_start_s: float = Field(
        default=30.0,
        description="When to start looking for split points (seconds)",
        ge=5.0,
        le=60.0,
    )
    min_gap_for_split_s: float = Field(
        default=3.0,
        description="Minimum silence gap for natural splits (seconds)",
        ge=0.5,
        le=10.0,
    )
    boundary_margin_s: float = Field(
        default=0.30,
        description="Silence margin at chunk edges (seconds)",
        ge=0.0,
        le=1.0,
    )
    max_intra_gap_s: float = Field(
        default=0.8,
        description="Maximum preserved gap inside chunks (seconds)",
        ge=0.0,
        le=5.0,
    )
    
    # Legacy fields (for backward compatibility)
    max_speech_duration_s: float = Field(
        default=60.0,
        description="Legacy alias for max_chunk_s",
    )
    boundary_margin_ms: int = Field(
        default=300,
        description="Legacy alias for boundary_margin_s * 1000",
    )

    @field_validator("threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not 0.0 < v < 1.0:
            raise ValueError("threshold must be between 0 and 1")
        return v

    @field_validator(
        "min_silence_ms",
        "min_speech_ms",
        "speech_pad_ms",
        "boundary_margin_ms",
    )
    @classmethod
    def validate_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("values must be non-negative")
        return v

    @field_validator("max_chunk_s", "max_speech_duration_s")
    @classmethod
    def validate_positive_duration(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("duration must be positive")
        return v

    @field_validator("sample_rate")
    @classmethod
    def validate_sample_rate(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("sample_rate must be positive")
        return v

    @model_validator(mode="after")
    def validate_search_start(self) -> SegmentationProfileConfig:
        """Ensure chunk_search_start_s < max_chunk_s."""
        if self.chunk_search_start_s >= self.max_chunk_s:
            raise ValueError(
                f"chunk_search_start_s ({self.chunk_search_start_s}) must be less than "
                f"max_chunk_s ({self.max_chunk_s})"
            )
        return self

    def to_profile(self) -> SegmentationProfile:
        return SegmentationProfile(
            # VAD parameters
            threshold=self.threshold,
            min_silence_ms=self.min_silence_ms,
            min_speech_ms=self.min_speech_ms,
            speech_pad_ms=self.speech_pad_ms,
            sample_rate=self.sample_rate,
            device=self.device,
            # Chunking parameters
            max_chunk_s=self.max_chunk_s,
            chunk_search_start_s=self.chunk_search_start_s,
            min_gap_for_split_s=self.min_gap_for_split_s,
            boundary_margin_s=self.boundary_margin_s,
            max_intra_gap_s=self.max_intra_gap_s,
            # Legacy fields
            max_speech_duration_s=self.max_speech_duration_s,
            boundary_margin_ms=self.boundary_margin_ms,
        )


class AppConfig(BaseModel):
    """Main application configuration for Vociferous.
    
    Essential settings:
    - engine: ASR engine (canary_qwen or whisper_turbo)
    - model_name: Model identifier for the engine
    - device: Target device (auto, cpu, cuda)
    - compute_type: Precision (auto, int8, float16, float32, etc.)
    - model_cache_dir: Directory to cache downloaded models
    
    Refinement is handled per-engine in the CLI; not config-driven.
    Audio preprocessing uses the audio module (decode, vad, condense).
    """

    # Core engine configuration
    model_name: str = DEFAULT_CANARY_MODEL
    engine: EngineKind = "canary_qwen"  # Canary-Qwen is the primary default
    compute_type: str = "auto"
    device: str = "auto"
    model_cache_dir: str | None = Field(default_factory=lambda: str(DEFAULT_MODEL_CACHE_DIR))
    model_parent_dir: str | None = Field(default_factory=lambda: str(DEFAULT_MODEL_CACHE_DIR))
    
    # Advanced settings
    numexpr_max_threads: int | None = None  # Thread limit for numexpr computations
    
    # Artifact handling for intermediate files
    artifacts: ArtifactConfig = Field(default_factory=ArtifactConfig)

    # Declarative profiles
    engine_profiles: dict[str, EngineProfileConfig] = Field(default_factory=dict)
    segmentation_profiles: dict[str, SegmentationProfileConfig] = Field(default_factory=dict)
    default_engine_profile: str = Field(
        default="canary_qwen_fp16",
        description="Default engine profile key",
    )
    default_segmentation_profile: str = Field(
        default="default",
        description="Default segmentation profile key",
    )
    
    # Engine-specific parameters (for future extensibility)
    params: Mapping[str, str] = Field(
        default_factory=lambda: {
            "enable_batching": "false",
            "batch_size": "1",
            "word_timestamps": "false",
        }
    )

    @field_validator("compute_type")
    @classmethod
    def validate_compute_type(cls, v: str) -> str:
        allowed = {"auto", "int8", "int8_float16", "float16", "float32", "fp16", "fp32"}
        if v not in allowed:
            raise ValueError("Invalid compute_type")
        return v

    @field_validator("model_parent_dir")
    @classmethod
    def validate_model_parent_dir(cls, v: str | None) -> str:
        if not v:
            raise ValueError("model_parent_dir must be set")
        return str(Path(v).expanduser())

    @classmethod
    def model_validate(  # type: ignore[override]
        cls,
        obj: Mapping[str, object] | object,
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: dict[str, object] | None = None,
    ) -> "AppConfig":
        # Migrate legacy keep_intermediates → artifacts.cleanup_intermediates
        if isinstance(obj, Mapping):
            data = dict(obj)
            if "artifacts" not in data and "keep_intermediates" in data:
                keep_flag = bool(data.get("keep_intermediates"))
                data["artifacts"] = {
                    "cleanup_intermediates": not keep_flag,
                    "keep_on_error": True,
                    "output_directory": str(Path(".").resolve()),
                    "naming_pattern": "{input_stem}_{step}.{ext}",
                }
            return super().model_validate(
                data, strict=strict, from_attributes=from_attributes, context=context
            )
        return super().model_validate(
            obj, strict=strict, from_attributes=from_attributes, context=context
        )



    @model_validator(mode="after")
    def inject_and_validate_profiles(self) -> AppConfig:
        """Inject default profiles if empty and validate profile references."""
        # Inject defaults if profiles are empty
        if not self.engine_profiles:
            self.engine_profiles = _default_engine_profiles()
        if not self.segmentation_profiles:
            self.segmentation_profiles = _default_segmentation_profiles()
        
        # Validate profile references
        if self.default_engine_profile not in self.engine_profiles:
            available = ", ".join(sorted(self.engine_profiles)) or "<none>"
            raise ValueError(f"default_engine_profile '{self.default_engine_profile}' not found. Available: {available}")
        
        if self.default_segmentation_profile not in self.segmentation_profiles:
            available = ", ".join(sorted(self.segmentation_profiles)) or "<none>"
            raise ValueError(f"default_segmentation_profile '{self.default_segmentation_profile}' not found. Available: {available}")
        
        return self

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> AppConfig:
        # Pydantic handles validation automatically.
        # We use model_validate to parse the dict.
        return cls.model_validate(data)


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load configuration, prompting for model directory only in interactive default runs."""

    default_config_path = Path.home() / ".config" / "vociferous" / "config.toml"
    if config_path is None:
        config_path = default_config_path

    is_first_run = not config_path.exists()

    if is_first_run:
        cfg = AppConfig()
        # Always prompt on first run in interactive mode
        should_prompt = sys.stdin.isatty()
    else:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        migrated = migrate_raw_config(data)
        cfg = AppConfig.model_validate(migrated)
        # Prompt only if model_parent_dir is missing/blank and in interactive mode
        should_prompt = (not cfg.model_parent_dir or not str(cfg.model_parent_dir).strip()) and sys.stdin.isatty()

    if should_prompt:
        default_dir = str(DEFAULT_MODEL_CACHE_DIR)
        print("\nVociferous: Please select a parent directory for your models.")
        print(f"Default: {default_dir}")
        user_input = input("Enter model parent directory (or press Enter to use default): ").strip()
        chosen_dir = user_input if user_input else default_dir
        cfg.model_parent_dir = str(Path(chosen_dir).expanduser())
        save_config(cfg, config_path)

    # Ensure model parent directory exists
    if cfg.model_parent_dir:
        Path(cfg.model_parent_dir).expanduser().mkdir(parents=True, exist_ok=True)
    # Ensure model cache directory exists if provided
    if cfg.model_cache_dir:
        Path(cfg.model_cache_dir).expanduser().mkdir(parents=True, exist_ok=True)

    # Ensure artifact output directory exists
    if cfg.artifacts and cfg.artifacts.output_directory:
        Path(cfg.artifacts.output_directory).expanduser().mkdir(parents=True, exist_ok=True)

    return cfg


def save_config(config: AppConfig, config_path: Path | None = None) -> None:
    """Save configuration to TOML file.
    
    Args:
        config: Configuration to save
        config_path: Path to config file (default: ~/.config/vociferous/config.toml)
    """
    if config_path is None:
        config_path = Path.home() / ".config" / "vociferous" / "config.toml"
    
    # Ensure config directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert config to dict and stringify Path objects for TOML
    config_dict = _stringify_paths(config.model_dump(exclude_none=True))
    
    # Write to TOML file
    with open(config_path, "wb") as f:
        tomli_w.dump(config_dict, f)


def _stringify_paths(value: Any) -> Any:
    """Recursively convert pathlib.Path objects to strings for TOML serialization."""
    from pathlib import Path

    if isinstance(value, dict):
        return {k: _stringify_paths(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_stringify_paths(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _default_engine_profiles() -> dict[str, EngineProfileConfig]:
    return {
        "canary_qwen_fp16": EngineProfileConfig(
            kind="canary_qwen",
            compute_type="float16",
            device="auto",
            model_name=DEFAULT_CANARY_MODEL,
        ),
        "whisper_turbo_default": EngineProfileConfig(
            kind="whisper_turbo",
            compute_type="float16",
            device="auto",
            model_name=DEFAULT_WHISPER_MODEL,
        ),
    }


def _default_segmentation_profiles() -> dict[str, SegmentationProfileConfig]:
    return {
        "default": SegmentationProfileConfig(),
    }


def get_engine_profile(config: AppConfig, name: str | None = None) -> EngineProfile:
    """Return an EngineProfile by name or the configured default."""

    profile_name = name or config.default_engine_profile
    try:
        profile_cfg = config.engine_profiles[profile_name]
    except KeyError:
        available = ", ".join(sorted(config.engine_profiles)) or "<none>"
        raise KeyError(
            f"Engine profile '{profile_name}' not found. Available: {available}"
        ) from None
    return profile_cfg.to_profile()


def get_segmentation_profile(config: AppConfig, name: str | None = None) -> SegmentationProfile:
    """Return a SegmentationProfile by name or the configured default."""

    profile_name = name or config.default_segmentation_profile
    try:
        profile_cfg = config.segmentation_profiles[profile_name]
    except KeyError:
        available = ", ".join(sorted(config.segmentation_profiles)) or "<none>"
        raise KeyError(
            f"Segmentation profile '{profile_name}' not found. Available: {available}"
        ) from None
    return profile_cfg.to_profile()
