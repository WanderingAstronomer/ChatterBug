from __future__ import annotations

from dataclasses import replace
from typing import Callable, Type

from chatterbug.domain.model import EngineConfig, EngineKind, TranscriptionEngine
from chatterbug.domain.exceptions import ConfigurationError
from .model_registry import normalize_model_name

EngineBuilder = Callable[[EngineConfig], TranscriptionEngine]

# Engine registry: maps EngineKind to engine class
ENGINE_REGISTRY: dict[EngineKind, Type[TranscriptionEngine]] = {}


def build_engine(kind: EngineKind, config: EngineConfig) -> TranscriptionEngine:
    """Build an engine instance using the registry pattern.
    
    Args:
        kind: The type of engine to build
        config: Configuration for the engine
        
    Returns:
        An instance of the requested engine
        
    Raises:
        ConfigurationError: If the engine kind is not registered
    """
    # Lazy import engines if not already registered
    if not ENGINE_REGISTRY:
        _register_engines()
    
    normalized_name = normalize_model_name(kind, config.model_name)
    config = config.model_copy(update={"model_name": normalized_name})
    
    engine_class = ENGINE_REGISTRY.get(kind)
    if engine_class is None:
        raise ValueError(f"Unknown engine kind: {kind}")
    
    return engine_class(config)


def _register_engines():
    """Register all available engines. Called lazily on first use."""
    from .whisper_turbo import WhisperTurboEngine
    from .voxtral import VoxtralEngine
    from .parakeet import ParakeetEngine
    
    ENGINE_REGISTRY["whisper_turbo"] = WhisperTurboEngine
    ENGINE_REGISTRY["voxtral"] = VoxtralEngine
    ENGINE_REGISTRY["parakeet_rnnt"] = ParakeetEngine
