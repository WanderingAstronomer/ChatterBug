"""Test EngineConfig validation and param sanitization."""
import pytest

from chatterbug.domain.model import DEFAULT_WHISPER_MODEL, EngineConfig


def test_engine_config_defaults() -> None:
    """Test default EngineConfig values."""
    cfg = EngineConfig()
    assert cfg.model_name == DEFAULT_WHISPER_MODEL
    assert cfg.compute_type == "auto"
    assert cfg.device == "auto"
    assert cfg.params == {}


def test_engine_config_validates_device() -> None:
    """Test device validation rejects invalid values."""
    with pytest.raises(ValueError, match="Invalid device.*must be cpu, cuda, or auto"):
        EngineConfig(device="tpu")
    
    with pytest.raises(ValueError, match="Invalid device.*must be cpu, cuda, or auto"):
        EngineConfig(device="")


def test_engine_config_validates_compute_type() -> None:
    """Test compute_type validation rejects invalid values."""
    with pytest.raises(ValueError, match="Invalid compute_type"):
        EngineConfig(compute_type="int4")
    
    with pytest.raises(ValueError, match="Invalid compute_type"):
        EngineConfig(compute_type="bfloat16")


def test_engine_config_accepts_valid_compute_types() -> None:
    """Test all valid compute types are accepted."""
    valid_types = ["auto", "int8", "int8_float16", "float16", "float32", "fp16", "fp32"]
    for ct in valid_types:
        cfg = EngineConfig(compute_type=ct)
        assert cfg.compute_type == ct


def test_engine_config_accepts_valid_devices() -> None:
    """Test all valid devices are accepted."""
    for device in ["cpu", "cuda", "auto"]:
        cfg = EngineConfig(device=device)
        assert cfg.device == device


def test_engine_config_sanitizes_params() -> None:
    """Test empty/whitespace param values are removed."""
    cfg = EngineConfig(
        params={
            "word_timestamps": "true",
            "empty_key": "",
            "whitespace_key": "   ",
            "valid_key": "value",
        }
    )
    assert "word_timestamps" in cfg.params
    assert "valid_key" in cfg.params
    assert "empty_key" not in cfg.params
    assert "whitespace_key" not in cfg.params
    assert cfg.params["word_timestamps"] == "true"
    assert cfg.params["valid_key"] == "value"


def test_engine_config_none_params_becomes_empty_dict() -> None:
    """Test None params is converted to empty dict."""
    cfg = EngineConfig(params=None)
    assert cfg.params == {}


def test_engine_config_immutable() -> None:
    """Test EngineConfig is frozen (immutable)."""
    cfg = EngineConfig()
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        cfg.device = "cuda"  # type: ignore[misc]
