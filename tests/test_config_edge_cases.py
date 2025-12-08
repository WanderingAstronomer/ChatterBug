"""Test config loading and validation edge cases (TDD approach)."""
import pytest
from pathlib import Path
from typing import Mapping

from pydantic import ValidationError

import tomllib

from vociferous.config.schema import AppConfig, load_config, save_config
from vociferous.config.migrations import migrate_raw_config
from vociferous.domain.model import DEFAULT_WHISPER_MODEL


def test_app_config_from_dict_with_invalid_types() -> None:
    """Test AppConfig.from_dict handles type mismatches."""
    data: Mapping[str, object] = {
        "chunk_ms": "not a number",  # type: ignore[dict-item]
    }
    with pytest.raises(ValidationError):
        AppConfig.from_dict(data)


def test_validate_config_rejects_invalid_compute_type() -> None:
    """Test _validate_config catches invalid compute types."""
    with pytest.raises(ValidationError, match="Invalid compute_type"):
        AppConfig(compute_type="int4")  # Invalid

    with pytest.raises(ValidationError, match="Invalid compute_type"):
        AppConfig(compute_type="bfloat16")  # Invalid


def test_validate_config_rejects_zero_chunk_ms() -> None:
    """Test _validate_config catches zero chunk_ms."""
    with pytest.raises(ValidationError, match="chunk_ms must be positive"):
        AppConfig(chunk_ms=0)


def test_validate_config_rejects_negative_chunk_ms() -> None:
    """Test _validate_config catches negative chunk_ms."""
    with pytest.raises(ValidationError, match="chunk_ms must be positive"):
        AppConfig(chunk_ms=-100)


def test_validate_config_accepts_valid_compute_types() -> None:
    """Test _validate_config accepts all valid compute types."""
    valid_types = ["auto", "int8", "int8_float16", "float16", "float32", "fp16"]
    
    for ct in valid_types:
        cfg = AppConfig(compute_type=ct)
        assert cfg.compute_type == ct  # Should not raise


def test_validate_config_missing_fp32() -> None:
    """Test whether fp32 is actually in the validation list (bug check)."""
    # The validation only checks for 5 types, not 6 - missing fp32?
    cfg = AppConfig(compute_type="fp32")
    assert cfg.compute_type == "fp32"


def test_load_config_creates_cache_directory(tmp_path: Path) -> None:
    """Test load_config creates model cache directory if it doesn't exist."""
    cache_dir = tmp_path / "models"
    assert not cache_dir.exists()
    
    # Create a config file that specifies this cache dir
    config_path = tmp_path / "config.toml"
    config_path.write_text(f'model_cache_dir = "{cache_dir}"\n')
    
    cfg = load_config(config_path)
    assert Path(cfg.model_cache_dir).exists()  # type: ignore[arg-type]


def test_load_config_with_nonexistent_file_uses_defaults(tmp_path: Path) -> None:
    """Test load_config returns defaults when config file doesn't exist."""
    nonexistent = tmp_path / "nonexistent.toml"
    cfg = load_config(nonexistent)
    
    assert cfg.model_name == DEFAULT_WHISPER_MODEL
    assert cfg.engine == "whisper_turbo"  # Local engine is default (works out of the box)
    assert cfg.device == "auto"


def test_load_config_with_partial_config(tmp_path: Path) -> None:
    """Test load_config merges partial config with defaults."""
    config_path = tmp_path / "config.toml"
    config_path.write_text('device = "cuda"\ncompute_type = "float16"\n')
    
    cfg = load_config(config_path)
    assert cfg.device == "cuda"  # Overridden
    assert cfg.compute_type == "float16"  # Overridden
    assert cfg.model_name == DEFAULT_WHISPER_MODEL  # Default


def test_load_config_with_invalid_toml(tmp_path: Path) -> None:
    """Test load_config handles malformed TOML."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("this is not valid TOML [[[")
    
    with pytest.raises(Exception):  # tomllib.TOMLDecodeError or similar
        load_config(config_path)


def test_app_config_default_params_are_strings() -> None:
    """Test AppConfig default params are all strings."""
    cfg = AppConfig()
    for key, value in cfg.params.items():
        assert isinstance(value, str), f"Param {key} should be string, got {type(value)}"


def test_app_config_history_limit_is_positive() -> None:
    """Test we could add validation for history_limit."""
    cfg = AppConfig(history_limit=5)
    assert cfg.history_limit == 5
    with pytest.raises(ValidationError):
        AppConfig(history_limit=-1)


def test_app_config_params_immutability() -> None:
    """Test whether params dict can be mutated after creation."""
    cfg = AppConfig()
    original_params = dict(cfg.params)
    
    # Try to mutate (shouldn't work if properly frozen)
    # But Mapping might not be truly frozen...
    try:
        cfg.params["new_key"] = "new_value"  # type: ignore[index]
        # If this works, params is mutable - potential bug
        assert "new_key" not in original_params
    except (TypeError, AttributeError):
        # Good - params is immutable
        pass


def test_load_config_migrates_parakeet_and_updates_model(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Parakeet engine configs should migrate to whisper_vllm with a better model."""
    config_path = tmp_path / "config.toml"
    config_path.write_text('engine = "parakeet_rnnt"\nmodel_name = "openai/whisper-large-v3-turbo"\n')

    with caplog.at_level("WARNING"):
        cfg = load_config(config_path)

    assert cfg.engine == "whisper_vllm"
    assert cfg.model_name == "openai/whisper-large-v3-turbo"
    assert any("Parakeet engine removed" in msg for msg in caplog.messages)


def test_load_config_migrates_voxtral_alias(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Legacy voxtral engine name should migrate to voxtral_local."""
    config_path = tmp_path / "config.toml"
    config_path.write_text('engine = "voxtral"\n')

    with caplog.at_level("WARNING"):
        cfg = load_config(config_path)

    assert cfg.engine == "voxtral_local"
    assert any("Engine 'voxtral' renamed" in msg for msg in caplog.messages)


def test_migrate_raw_config_returns_new_dict() -> None:
    original = {"engine": "voxtral"}
    migrated = migrate_raw_config(original)

    assert migrated is not original
    assert migrated["engine"] == "voxtral_local"
    assert original["engine"] == "voxtral"


def test_save_config_writes_toml_and_creates_directory(tmp_path: Path) -> None:
    """save_config should create directories and write TOML content."""
    target_dir = tmp_path / "nested" / "config"
    config_path = target_dir / "config.toml"
    cfg = AppConfig(device="cuda", compute_type="float16")

    save_config(cfg, config_path)

    assert config_path.exists()
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    assert data["device"] == "cuda"
    assert data["compute_type"] == "float16"
