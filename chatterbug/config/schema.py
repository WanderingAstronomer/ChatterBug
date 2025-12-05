from __future__ import annotations

from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, Field, field_validator

from chatterbug.domain.model import DEFAULT_MODEL_CACHE_DIR, EngineKind
from chatterbug.domain.exceptions import ConfigurationError


class AppConfig(BaseModel):
    model_name: str = "distil-whisper/distil-large-v3"
    engine: EngineKind = "whisper_turbo"
    compute_type: str = "int8"
    device: str = "cpu"
    model_cache_dir: str | None = str(DEFAULT_MODEL_CACHE_DIR)
    chunk_ms: int = 960
    history_limit: int = 20
    history_dir: str = str(Path.home() / ".cache" / "chatterbug" / "history")
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
        allowed = {"int8", "int8_float16", "float16", "float32", "fp16", "fp32"}
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

import tomllib


def load_config(config_path: Path | None = None) -> AppConfig:
    if config_path is None:
        config_path = Path.home() / ".config" / "chatterbug" / "config.toml"

    if not config_path.exists():
        cfg = AppConfig()
    else:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        cfg = AppConfig.model_validate(data)

    # Ensure model cache directory exists if provided
    if cfg.model_cache_dir:
        Path(cfg.model_cache_dir).expanduser().mkdir(parents=True, exist_ok=True)

    return cfg
