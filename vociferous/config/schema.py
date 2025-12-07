from __future__ import annotations

import logging
from pathlib import Path
from typing import Mapping

import tomllib
import tomli_w

from pydantic import BaseModel, Field, field_validator

from vociferous.domain.model import DEFAULT_MODEL_CACHE_DIR, DEFAULT_WHISPER_MODEL, EngineKind
from vociferous.domain.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class AppConfig(BaseModel):
    model_name: str = DEFAULT_WHISPER_MODEL
    engine: EngineKind = "whisper_turbo"  # Local engine is default (works out of the box)
    compute_type: str = "auto"
    device: str = "auto"
    model_cache_dir: str | None = str(DEFAULT_MODEL_CACHE_DIR)
    vllm_endpoint: str = "http://localhost:8000"  # Default vLLM server endpoint
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

    @field_validator("compute_type")
    @classmethod
    def validate_compute_type(cls, v: str) -> str:
        allowed = {"auto", "int8", "int8_float16", "float16", "float32", "fp16", "fp32"}
        if v not in allowed:
            raise ValueError("Invalid compute_type")
        return v

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
    if config_path is None:
        config_path = Path.home() / ".config" / "vociferous" / "config.toml"

    if not config_path.exists():
        cfg = AppConfig()
    else:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        # Migrate deprecated engines before validation
        if "engine" in data:
            engine = data["engine"]

            # Migrate parakeet_rnnt -> whisper_vllm
            if engine == "parakeet_rnnt":
                logger.warning(
                    "⚠ Parakeet engine removed; migrated to whisper_vllm with large-v3-turbo "
                    "(comparable accuracy). Update ~/.config/vociferous/config.toml."
                )
                data["engine"] = "whisper_vllm"
                # Use large-v3-turbo as Parakeet replacement (RNNT-class accuracy)
                if "model_name" not in data or data["model_name"] == DEFAULT_WHISPER_MODEL:
                    data["model_name"] = "openai/whisper-large-v3-turbo"

            # Migrate voxtral -> voxtral_local (backward compat)
            elif engine == "voxtral":
                logger.warning(
                    "⚠ Engine 'voxtral' renamed to 'voxtral_local'. "
                    "Update config; existing behavior unchanged."
                )
                data["engine"] = "voxtral_local"

        cfg = AppConfig.model_validate(data)

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
