from __future__ import annotations

import logging
from collections.abc import Callable

from vociferous.domain.exceptions import ConfigurationError
from vociferous.domain.model import EngineConfig, EngineKind, TranscriptionEngine

from .hardware import get_optimal_device
from .model_registry import normalize_model_name

logger = logging.getLogger(__name__)

EngineBuilder = Callable[[EngineConfig], TranscriptionEngine]

# Engine registry: supports canary_qwen (GPU-optimized) and whisper_turbo (CPU-friendly)
ENGINE_REGISTRY: dict[EngineKind, EngineBuilder] = {}


def build_engine(kind: EngineKind, config: EngineConfig) -> TranscriptionEngine:
    """Build an engine instance with smart device detection.

    Args:
        kind: The type of engine to build ("canary_qwen" or "whisper_turbo")
        config: Configuration for the engine

    Returns:
        TranscriptionEngine instance (CanaryQwenEngine or WhisperTurboEngine)

    Raises:
        ConfigurationError: If engine kind is unsupported or Canary requested on CPU-only system
    """
    # Lazy import engines if not already registered
    if not ENGINE_REGISTRY:
        _register_engines()

    # Validate Canary-Qwen GPU requirement
    if kind == "canary_qwen":
        device = config.device if config.device != "auto" else get_optimal_device()
        if device == "cpu":
            raise ConfigurationError(
                "Canary-Qwen requires a CUDA-capable GPU (Ampere, Blackwell, Hopper, etc.). "
                "This system has no GPU detected. Use --engine whisper_turbo for CPU transcription."
            )

    normalized_name = normalize_model_name(kind, config.model_name)
    config = config.model_copy(update={"model_name": normalized_name})

    engine_class = ENGINE_REGISTRY.get(kind)
    if engine_class is None:
        supported = ", ".join(ENGINE_REGISTRY.keys())
        raise ConfigurationError(f"Unknown engine kind: {kind}. Supported: {supported}")

    return engine_class(config)


def _register_engines() -> None:
    """Register all available engines. Called lazily on first use."""
    from .canary_qwen import CanaryQwenEngine
    from .whisper_turbo import WhisperTurboEngine

    ENGINE_REGISTRY["canary_qwen"] = CanaryQwenEngine
    ENGINE_REGISTRY["whisper_turbo"] = WhisperTurboEngine

