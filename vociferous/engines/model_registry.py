"""Model registry for ASR engines.

Provides canonical model names, aliases, and validation for supported
ASR engines (Canary-Qwen and Whisper).
"""

from __future__ import annotations

from typing import Literal

# Canary-Qwen model (GPU-only, state-of-the-art)
DEFAULT_CANARY_MODEL = "nvidia/canary-qwen-2.5b"
CANARY_MODELS: frozenset[str] = frozenset({DEFAULT_CANARY_MODEL})

# Official OpenAI Whisper models (NOT faster-whisper, NOT CTranslate2)
# See: https://github.com/openai/whisper
DEFAULT_WHISPER_MODEL = "turbo"
WHISPER_MODELS: frozenset[str] = frozenset({
    "turbo",        # Whisper Turbo (recommended, fastest)
    "large-v3",     # Whisper V3 Large
    "large-v2",     # Whisper V2 Large
    "large",        # Whisper Large (original)
    "medium",
    "small",
    "base",
    "tiny",
})

# Engine kind type
EngineKindLiteral = Literal["canary_qwen", "whisper_turbo"]

# Model aliases for backward compatibility
_MODEL_ALIASES: dict[str, dict[str, str]] = {
    "canary_qwen": {
        "default": DEFAULT_CANARY_MODEL,
        "canary": DEFAULT_CANARY_MODEL,
        "canary-qwen": DEFAULT_CANARY_MODEL,
    },
    "whisper_turbo": {
        "default": DEFAULT_WHISPER_MODEL,
        "large-v3-turbo": "turbo",  # Legacy alias
    },
}


def _is_valid_canary_model(name: str) -> bool:
    """Check if model name is valid for Canary-Qwen engine."""
    if not name:
        return False
    # Accept exact matches or any nvidia/canary-* prefix
    return name in CANARY_MODELS or name.startswith("nvidia/canary")


def _is_valid_whisper_model(name: str) -> bool:
    """Check if model name is valid for Whisper engine."""
    if not name:
        return False
    return name.lower() in WHISPER_MODELS


def _is_faster_whisper_model(name: str) -> bool:
    """Check if model name appears to be a faster-whisper/CTranslate2 model.
    
    These are NOT supported. Vociferous uses official OpenAI Whisper only.
    """
    if not name:
        return False
    name_lower = name.lower()
    return (
        "faster-whisper" in name_lower
        or "ct2" in name_lower
        or "ctranslate" in name_lower
        or name_lower.startswith("deepdml/")
        or name_lower.startswith("guillaumekln/")
    )


def normalize_model_name(kind: str, model_name: str | None) -> str:
    """Normalize and validate model names for the engine.

    Resolves aliases to canonical names and validates against allowed models.
    Returns the default model if none specified.

    Args:
        kind: Engine kind ("canary_qwen" or "whisper_turbo")
        model_name: User-provided model name or alias (optional)

    Returns:
        Canonical model name

    Raises:
        ValueError: If engine kind is unknown or model name is invalid
    """
    kind_lower = kind.lower()
    
    # Validate engine kind
    if kind_lower not in ("canary_qwen", "whisper_turbo"):
        raise ValueError(
            f"Unknown engine kind: '{kind}'. "
            "Supported engines: canary_qwen, whisper_turbo"
        )
    
    # Return default if no model specified
    if not model_name:
        if kind_lower == "canary_qwen":
            return DEFAULT_CANARY_MODEL
        return DEFAULT_WHISPER_MODEL
    
    # Check aliases first
    aliases = _MODEL_ALIASES.get(kind_lower, {})
    model_lower = model_name.lower()
    if model_lower in aliases:
        return aliases[model_lower]
    
    # Validate against allowed models
    if kind_lower == "canary_qwen":
        if _is_valid_canary_model(model_name):
            return model_name
        raise ValueError(
            f"Invalid model '{model_name}' for canary_qwen engine. "
            f"Use: {DEFAULT_CANARY_MODEL}"
        )
    
    # whisper_turbo
    if _is_valid_whisper_model(model_name):
        return model_lower  # Normalize to lowercase
    
    # Check if this is a faster-whisper model (common misconfiguration)
    if _is_faster_whisper_model(model_name):
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "Detected faster-whisper/CTranslate2 model '%s' but Vociferous uses "
            "official OpenAI Whisper only. Using default model '%s' instead.",
            model_name,
            DEFAULT_WHISPER_MODEL,
        )
        return DEFAULT_WHISPER_MODEL
    
    models_str = ", ".join(sorted(WHISPER_MODELS))
    raise ValueError(
        f"Invalid model '{model_name}' for whisper_turbo engine. "
        f"Available models: {models_str}"
    )
