"""Tests for engine registry pattern."""
import pytest

from vociferous.domain.model import EngineConfig, TranscriptionEngine
from vociferous.domain.exceptions import ConfigurationError
from vociferous.engines.factory import ENGINE_REGISTRY, build_engine, _register_engines


def test_engine_registry_contains_all_engines():
    """Test that all expected engines are registered."""
    # Trigger registration
    _register_engines()
    
    assert "whisper_turbo" in ENGINE_REGISTRY
    assert "voxtral_local" in ENGINE_REGISTRY
    assert "voxtral" in ENGINE_REGISTRY  # legacy alias


def test_engine_registry_stores_classes():
    """Test that registry stores engine classes, not instances."""
    # Trigger registration
    _register_engines()
    
    for engine_kind, engine_class in ENGINE_REGISTRY.items():
        # Should be a class
        assert isinstance(engine_class, type)
        # Note: Cannot use issubclass with Protocols that have non-method members (e.g., metadata property)
        # Instead, verify the class has the required protocol methods
        assert hasattr(engine_class, 'start')
        assert hasattr(engine_class, 'push_audio')
        assert hasattr(engine_class, 'flush')
        assert hasattr(engine_class, 'poll_segments')


def test_build_engine_creates_instances():
    """Test that build_engine creates instances from registry."""
    config = EngineConfig()
    
    engine = build_engine("whisper_turbo", config)
    assert isinstance(engine, TranscriptionEngine)
    assert engine.__class__.__name__ == "WhisperTurboEngine"


def test_build_engine_with_unknown_kind_raises():
    """Test that building unknown engine kind raises ValueError."""
    config = EngineConfig()
    
    with pytest.raises(ConfigurationError, match="Unknown engine kind"):
        build_engine("nonexistent_engine", config)  # type: ignore[arg-type]


def test_registry_lazy_initialization():
    """Test that registry is lazily initialized on first use."""
    # Clear registry
    ENGINE_REGISTRY.clear()
    
    # Should be empty
    assert len(ENGINE_REGISTRY) == 0
    
    # Building an engine should trigger registration
    config = EngineConfig()
    engine = build_engine("whisper_turbo", config)
    
    # Registry should now be populated (whisper_turbo, voxtral_local, voxtral)
    assert len(ENGINE_REGISTRY) == 3
    assert isinstance(engine, TranscriptionEngine)


def test_registry_pattern_enables_plugin_architecture():
    """Test that registry pattern enables adding engines dynamically."""
    # Ensure registry is initialized
    _register_engines()
    
    # Define a custom engine at runtime
    class CustomEngine(TranscriptionEngine):
        def __init__(self, config: EngineConfig):
            self.config = config
            self.model_name = config.model_name
        
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

def test_registry_reinitialization_idempotent():
    """Test that re-registering engines is idempotent."""
    _register_engines()
    original_size = len(ENGINE_REGISTRY)
    
    # Re-register
    _register_engines()
    
    # Size should be the same
    assert len(ENGINE_REGISTRY) == original_size
