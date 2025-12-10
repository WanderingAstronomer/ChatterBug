from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Mapping

import tomllib
import tomli_w

from pydantic import BaseModel, Field, field_validator

from vociferous.domain.model import DEFAULT_MODEL_CACHE_DIR, DEFAULT_WHISPER_MODEL, EngineKind
from vociferous.config.migrations import migrate_raw_config

logger = logging.getLogger(__name__)


class AppConfig(BaseModel):
    model_name: str = DEFAULT_WHISPER_MODEL
    engine: EngineKind = "whisper_turbo"  # Local engine is default (works out of the box)
    compute_type: str = "auto"
    device: str = "auto"
    model_cache_dir: str | None = Field(default_factory=lambda: str(DEFAULT_MODEL_CACHE_DIR))
    model_parent_dir: str | None = Field(default_factory=lambda: str(DEFAULT_MODEL_CACHE_DIR))
    allow_local_fallback: bool = False  # Explicit opt-in for auto-fallback to local engines
    chunk_ms: int = 960
    history_limit: int = 20
    history_dir: str = str(Path.home() / ".cache" / "vociferous" / "history")
    numexpr_max_threads: int | None = None
    params: Mapping[str, str] = Field(
        default_factory=lambda: {
            "enable_batching": "false",
            "batch_size": "1",
            "word_timestamps": "false",
        }
    )
    canary_qwen_enabled: bool = False
    canary_qwen_refine_by_default: bool = True
    canary_qwen_refinement_instructions: str = (
        "Fix grammar, add punctuation, improve readability"
    )
    polish_enabled: bool = False
    polish_model: str | None = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    polish_params: Mapping[str, str] = Field(
        default_factory=lambda: {
            "repo_id": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
            "max_tokens": "128",
            "temperature": "0.2",
            "gpu_layers": "0",
            "context_length": "2048",
        }
    )
    # Audio preprocessing options (opt-in for backward compatibility)
    preprocessing_enabled: bool = False
    preprocessing_trim_head: bool = True
    preprocessing_trim_tail: bool = True
    preprocessing_head_margin_ms: int = 500
    preprocessing_tail_margin_ms: int = 500
    preprocessing_split_on_gaps: bool = True
    preprocessing_gap_threshold_ms: int = 5000
    preprocessing_energy_threshold_db: float = -40.0
    preprocessing_min_speech_duration_ms: int = 300
    preprocessing_min_silence_duration_ms: int = 500

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

    @field_validator("chunk_ms")
    @classmethod
    def validate_chunk_ms(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("chunk_ms must be positive")
        return v

    @field_validator("history_limit")
    @classmethod
    def validate_history_limit(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("history_limit must be positive")
        return v

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "AppConfig":
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
    
    # Convert config to dict
    config_dict = config.model_dump(exclude_none=True)
    
    # Write to TOML file
    with open(config_path, "wb") as f:
        tomli_w.dump(config_dict, f)
