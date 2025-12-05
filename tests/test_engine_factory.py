"""Test engine factory and model registry integration."""
import pytest

from chatterbug.domain.model import EngineConfig
from chatterbug.domain.exceptions import ConfigurationError
from chatterbug.engines.factory import build_engine
from chatterbug.engines.whisper_turbo import WhisperTurboEngine
from chatterbug.engines.whisper_vllm import WhisperVLLMEngine
from chatterbug.engines.voxtral_local import VoxtralLocalEngine
from chatterbug.engines.voxtral_vllm import VoxtralVLLMEngine


def test_build_whisper_turbo_engine() -> None:
    """Test factory builds WhisperTurboEngine."""
    cfg = EngineConfig(model_name="turbo")
    engine = build_engine("whisper_turbo", cfg)
    assert isinstance(engine, WhisperTurboEngine)
    assert engine.model_name == "large-v3-turbo"  # normalized to faster-whisper format


def test_build_voxtral_engine() -> None:
    """Test factory builds VoxtralLocalEngine via legacy alias."""
    cfg = EngineConfig(model_name="voxtral-mini")
    engine = build_engine("voxtral", cfg)
    assert isinstance(engine, VoxtralLocalEngine)
    assert "Voxtral" in engine.model_name


def test_build_voxtral_vllm_engine() -> None:
    """Test factory builds VoxtralVLLMEngine."""
    cfg = EngineConfig(model_name="voxtral-mini")
    engine = build_engine("voxtral_vllm", cfg)
    assert isinstance(engine, VoxtralVLLMEngine)


def test_build_whisper_vllm_engine() -> None:
    """Test factory builds WhisperVLLMEngine."""
    cfg = EngineConfig(model_name="openai/whisper-large-v3-turbo")
    engine = build_engine("whisper_vllm", cfg)
    assert isinstance(engine, WhisperVLLMEngine)


def test_build_engine_with_unknown_kind() -> None:
    """Test factory raises on unknown engine kind."""
    cfg = EngineConfig()
    with pytest.raises(ConfigurationError, match="Unknown engine kind"):
        build_engine("unknown_engine", cfg)  # type: ignore[arg-type]


def test_build_engine_normalizes_model_names() -> None:
    """Test factory normalizes model aliases via registry."""
    cfg = EngineConfig(model_name="small")
    engine = build_engine("whisper_turbo", cfg)
    assert engine.model_name == "small"  # normalized to faster-whisper format
    
    cfg = EngineConfig(model_name="distil-large-v3")
    engine = build_engine("whisper_turbo", cfg)
    assert engine.model_name == "distil-large-v3"  # normalized to faster-whisper format


def test_build_engine_preserves_config() -> None:
    """Test factory preserves engine config parameters."""
    cfg = EngineConfig(
        device="cuda",
        compute_type="float16",
        params={"enable_batching": "false"},
    )
    engine = build_engine("whisper_turbo", cfg)
    assert engine.config.device == "cuda"
    assert engine.config.compute_type == "float16"
    assert engine.config.params["enable_batching"] == "false"
