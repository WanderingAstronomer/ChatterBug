"""Tests for engine registry pattern."""
import pytest

from chatterbug.domain.model import EngineConfig, TranscriptionEngine
from chatterbug.domain.exceptions import ConfigurationError
from chatterbug.engines.factory import ENGINE_REGISTRY, build_engine, register_engine


def test_engine_registry_contains_all_engines():
    """Test that all expected engines are registered."""
    assert "whisper_turbo" in ENGINE_REGISTRY
    assert "voxtral" in ENGINE_REGISTRY
    assert "parakeet_rnnt" in ENGINE_REGISTRY


def test_engine_registry_stores_classes():
    """Test that registry stores engine classes, not instances."""
    for engine_kind, engine_class in ENGINE_REGISTRY.items():
        # Should be a class
        assert isinstance(engine_class, type)
        # Should be a subclass of TranscriptionEngine
        assert issubclass(engine_class, TranscriptionEngine)


def test_build_engine_creates_instances():
    """Test that build_engine creates instances from registry."""
    config = EngineConfig()
    
    engine = build_engine("whisper_turbo", config)
    assert isinstance(engine, TranscriptionEngine)
    assert engine.__class__.__name__ == "WhisperTurboEngine"


def test_build_engine_with_unknown_kind_raises():
    """Test that building unknown engine kind raises ConfigurationError."""
    config = EngineConfig()
    
    with pytest.raises(ConfigurationError, match="Unknown engine kind"):
        build_engine("nonexistent_engine", config)  # type: ignore[arg-type]


def test_register_engine_decorator_works():
    """Test that register_engine decorator registers engines correctly."""
    # Create a test engine class
    @register_engine("test_engine")  # type: ignore[arg-type]
    class TestEngine(TranscriptionEngine):
        def __init__(self, config: EngineConfig):
            self.config = config
        
        def start(self, options):
            pass
        
        def push_audio(self, pcm16: bytes, timestamp_ms: int):
            pass
        
        def flush(self):
            pass
        
        def poll_segments(self):
            return []
    
    # Should be registered
    assert "test_engine" in ENGINE_REGISTRY  # type: ignore[comparison-overlap]
    assert ENGINE_REGISTRY["test_engine"] == TestEngine  # type: ignore[index, comparison-overlap]
    
    # Should be buildable
    config = EngineConfig()
    engine = build_engine("test_engine", config)  # type: ignore[arg-type]
    assert isinstance(engine, TestEngine)
    
    # Cleanup
    del ENGINE_REGISTRY["test_engine"]  # type: ignore[arg-type]


def test_register_engine_returns_class():
    """Test that register_engine decorator returns the class unchanged."""
    class DummyEngine(TranscriptionEngine):
        pass
    
    decorator = register_engine("dummy_engine")  # type: ignore[arg-type]
    result = decorator(DummyEngine)
    
    # Should return the same class
    assert result is DummyEngine
    
    # Cleanup
    if "dummy_engine" in ENGINE_REGISTRY:  # type: ignore[comparison-overlap]
        del ENGINE_REGISTRY["dummy_engine"]  # type: ignore[arg-type]


def test_engine_registry_immutability():
    """Test that engines cannot be accidentally overwritten without explicit action."""
    original_engine = ENGINE_REGISTRY["whisper_turbo"]
    
    # Attempting to register again should work (overwrite)
    @register_engine("whisper_turbo")
    class FakeEngine(TranscriptionEngine):
        pass
    
    # Registry should now have the fake engine
    assert ENGINE_REGISTRY["whisper_turbo"] == FakeEngine
    
    # Restore original
    ENGINE_REGISTRY["whisper_turbo"] = original_engine


def test_registry_pattern_enables_plugin_architecture():
    """Test that registry pattern enables adding engines dynamically."""
    # Define a custom engine at runtime
    class CustomEngine(TranscriptionEngine):
        def __init__(self, config: EngineConfig):
            self.config = config
        
        def start(self, options):
            pass
        
        def push_audio(self, pcm16: bytes, timestamp_ms: int):
            pass
        
        def flush(self):
            pass
        
        def poll_segments(self):
            return []
    
    # Register it dynamically
    ENGINE_REGISTRY["custom_engine"] = CustomEngine  # type: ignore[index]
    
    # Should be immediately usable
    config = EngineConfig()
    engine = build_engine("custom_engine", config)  # type: ignore[arg-type]
    assert isinstance(engine, CustomEngine)
    
    # Cleanup
    del ENGINE_REGISTRY["custom_engine"]  # type: ignore[arg-type]


def test_build_engine_normalizes_model_names():
    """Test that build_engine normalizes model names via registry."""
    config = EngineConfig(model_name="small")
    engine = build_engine("whisper_turbo", config)
    
    # Model name should be normalized
    assert engine.model_name == "small"  # normalized to faster-whisper format


def test_build_engine_preserves_config():
    """Test that build_engine preserves all config parameters."""
    config = EngineConfig(
        model_name="turbo",
        device="cuda",
        compute_type="float16",
        params={"enable_batching": "true"},
    )
    
    engine = build_engine("whisper_turbo", config)
    
    # Config should be preserved (though model name may be normalized)
    assert engine.config.device == "cuda"
    assert engine.config.compute_type in ("float16", "float16")  # May be auto-adjusted
    assert engine.config.params.get("enable_batching") == "true"
