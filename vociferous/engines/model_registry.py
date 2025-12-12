from __future__ import annotations

DEFAULT_CANARY_MODEL = "nvidia/canary-qwen-2.5b"
CANARY_MODELS: dict[str, str] = {
    DEFAULT_CANARY_MODEL: DEFAULT_CANARY_MODEL,
}

# Official OpenAI Whisper models (NOT faster-whisper, NOT CTranslate2)
# See: https://github.com/openai/whisper
DEFAULT_WHISPER_MODEL = "turbo"
WHISPER_MODELS: dict[str, str] = {
    "turbo": "turbo",           # Whisper Turbo (recommended, fastest)
    "large-v3": "large-v3",     # Whisper V3 Large
    "large-v2": "large-v2",     # Whisper V2 Large
    "large": "large",           # Whisper Large (original)
    "medium": "medium",
    "small": "small",
    "base": "base",
    "tiny": "tiny",
}


def _is_invalid_canary_model(name: str, default: str | None) -> bool:
    if not name:
        return True
    if name in CANARY_MODELS or str(name).startswith("nvidia/canary"):
        return False
    return not (default and name == default)


def _is_invalid_whisper_model(name: str, default: str | None) -> bool:
    if not name:
        return True
    # Official Whisper model names: turbo, large-v3, large-v2, large, medium, small, base, tiny
    if name in WHISPER_MODELS or str(name).lower() in WHISPER_MODELS:
        return False
    return not (default and name == default)


_DEFAULTS = {
    "canary_qwen": DEFAULT_CANARY_MODEL,
    "whisper_turbo": DEFAULT_WHISPER_MODEL,
}

_ALIASES: dict[str, dict[str, str]] = {
    "canary_qwen": {
        "default": DEFAULT_CANARY_MODEL,
    },
    "whisper_turbo": {
        "default": DEFAULT_WHISPER_MODEL,
        "large-v3-turbo": "turbo",  # Map old alias to turbo
        "large-v3": "large-v3",
        "medium": "medium",
        "small": "small",
    },
}


def normalize_model_name(kind: str, model_name: str | None) -> str:
    """Normalize and validate model names for the engine.

    Args:
        kind: Engine kind (e.g., "canary_qwen", "whisper_turbo")
        model_name: User-provided model name or alias

    Returns:
        Canonical model name

    Raises:
        ValueError: If model name is invalid for the engine
    """
    kind_lower = kind.lower()
    
    if kind_lower not in ("canary_qwen", "whisper_turbo"):
        raise ValueError(f"Unknown engine kind: {kind}")
    
    # If no model specified, use default
    if not model_name:
        return _DEFAULTS[kind_lower]
    
    model_lower = model_name.lower()
    
    # Check aliases first
    aliases = _ALIASES.get(kind_lower, {})
    if model_lower in aliases:
        return aliases[model_lower]
    
    # Validate against allowed models
    if kind_lower == "canary_qwen":
        if _is_invalid_canary_model(model_name, _DEFAULTS.get(kind_lower)):
            raise ValueError(
                f"Invalid model '{model_name}' for {kind}. "
                f"Allowed: {list(CANARY_MODELS.keys())}"
            )
        return model_name
    
    if kind_lower == "whisper_turbo":
        if _is_invalid_whisper_model(model_name, _DEFAULTS.get(kind_lower)):
            raise ValueError(
                f"Invalid model '{model_name}' for {kind}. "
                f"Allowed: {list(WHISPER_MODELS.keys())}"
            )
        return model_name
    
    raise ValueError(f"Unknown engine kind: {kind}")
