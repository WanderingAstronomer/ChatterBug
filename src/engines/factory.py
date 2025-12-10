from __future__ import annotations

import logging
from typing import Callable

from vociferous.domain.model import EngineConfig, EngineKind, TranscriptionEngine
from vociferous.domain.exceptions import ConfigurationError
from .model_registry import normalize_model_name

logger = logging.getLogger(__name__)

EngineBuilder = Callable[[EngineConfig], TranscriptionEngine]

# Engine registry: maps EngineKind to engine builder
ENGINE_REGISTRY: dict[EngineKind, EngineBuilder] = {}


def build_engine(kind: EngineKind, config: EngineConfig) -> TranscriptionEngine:
    """Build an engine instance using the registry pattern.

    Handles legacy engine aliases for backward compatibility:
    - "voxtral" is automatically mapped to "voxtral_local" with deprecation warning

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

    # Handle legacy "voxtral" alias for backward compatibility
    if kind == "voxtral":
        logger.warning(
            "⚠ Engine 'voxtral' renamed to 'voxtral_local'. "
            "Update config; existing behavior unchanged."
        )
        kind = "voxtral_local"

    normalized_name = normalize_model_name(kind, config.model_name)
    config = config.model_copy(update={"model_name": normalized_name})

    engine_class = ENGINE_REGISTRY.get(kind)
    if engine_class is None:
        raise ConfigurationError(f"Unknown engine kind: {kind}")

    return engine_class(config)


def _register_engines() -> None:
    """Register all available engines. Called lazily on first use."""
    from .whisper_turbo import WhisperTurboEngine
    from .voxtral_local import VoxtralLocalEngine

    ENGINE_REGISTRY["whisper_turbo"] = WhisperTurboEngine
    ENGINE_REGISTRY["voxtral_local"] = VoxtralLocalEngine
    ENGINE_REGISTRY["voxtral"] = VoxtralLocalEngine  # Legacy alias
