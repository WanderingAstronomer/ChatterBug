from __future__ import annotations

from dataclasses import replace
from typing import Callable, Type

from chatterbug.domain.model import EngineConfig, EngineKind, TranscriptionEngine
from chatterbug.domain.exceptions import ConfigurationError
from .model_registry import normalize_model_name

EngineBuilder = Callable[[EngineConfig], TranscriptionEngine]

# Engine registry: maps EngineKind to engine class
ENGINE_REGISTRY: dict[EngineKind, Type[TranscriptionEngine]] = {}


def register_engine(kind: EngineKind):
    """Decorator to register an engine class for a given engine kind.
    
    Usage:
        @register_engine("whisper_turbo")
        class WhisperTurboEngine(TranscriptionEngine):
            ...
    """
    def decorator(cls: Type[TranscriptionEngine]) -> Type[TranscriptionEngine]:
        ENGINE_REGISTRY[kind] = cls
        return cls
    return decorator


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
    normalized_name = normalize_model_name(kind, config.model_name)
    config = config.model_copy(update={"model_name": normalized_name})
    
    engine_class = ENGINE_REGISTRY.get(kind)
    if engine_class is None:
        raise ConfigurationError(f"Unknown engine kind: {kind}")
    
    return engine_class(config)


# Import engines to trigger registration
# This must be done after register_engine is defined
from .whisper_turbo import WhisperTurboEngine  # noqa: E402
from .voxtral import VoxtralEngine  # noqa: E402
from .parakeet import ParakeetEngine  # noqa: E402
