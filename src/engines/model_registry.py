from __future__ import annotations

from typing import Dict

from vociferous.domain.model import DEFAULT_WHISPER_MODEL, EngineKind

# Verified model names for faster-whisper (accepts short names or full Systran paths)
WHISPER_MODELS: Dict[str, str] = {
    DEFAULT_WHISPER_MODEL: DEFAULT_WHISPER_MODEL,
    "openai/whisper-large-v3-turbo": "large-v3-turbo",
    "distil-whisper/distil-large-v3": "distil-large-v3",
    "openai/whisper-large-v3": "large-v3",
    "openai/whisper-medium": "medium",
    "openai/whisper-small": "small",
    "openai/whisper-base": "base",
    "openai/whisper-tiny": "tiny",
}

VOXTRAL_MODELS: Dict[str, str] = {
    "mistralai/Voxtral-Mini-3B-2507": "https://huggingface.co/mistralai/Voxtral-Mini-3B-2507",
    "mistralai/Voxtral-Small-24B-2507": "https://huggingface.co/mistralai/Voxtral-Small-24B-2507",
}

CANARY_MODELS: Dict[str, str] = {
    "nvidia/canary-qwen-2.5b": "nvidia/canary-qwen-2.5b",
}


def _is_invalid_canary_model(name: str, default: str | None) -> bool:
    if not name:
        return True
    if name in CANARY_MODELS or str(name).startswith("nvidia/canary"):
        return False
    if name in VOXTRAL_MODELS or name in WHISPER_MODELS:
        return True
    if default and name == default:
        return False
    return True


_DEFAULTS = {
    "whisper_turbo": DEFAULT_WHISPER_MODEL,
    "voxtral": "mistralai/Voxtral-Mini-3B-2507",  # Legacy alias, maps to voxtral_local
    "voxtral_local": "mistralai/Voxtral-Mini-3B-2507",
    "canary_qwen": "nvidia/canary-qwen-2.5b",
}

_ALIASES: Dict[str, Dict[str, str]] = {
    "whisper_turbo": {
        "default": DEFAULT_WHISPER_MODEL,
        "balanced": DEFAULT_WHISPER_MODEL,
        "turbo-ct2": DEFAULT_WHISPER_MODEL,
        "large-v3-turbo-ct2": DEFAULT_WHISPER_MODEL,
        "deepdml/faster-whisper-large-v3-turbo-ct2": DEFAULT_WHISPER_MODEL,
        "turbo": "openai/whisper-large-v3-turbo",
        "large-v3-turbo": "openai/whisper-large-v3-turbo",
        "large-v3": "openai/whisper-large-v3",
        "distil-large-v3": "distil-whisper/distil-large-v3",
        "medium": "openai/whisper-medium",
        "small": "openai/whisper-small",
        "base": "openai/whisper-base",
        "tiny": "openai/whisper-tiny",
    },
    "voxtral": {  # Legacy alias for voxtral_local
        "voxtral-mini": "mistralai/Voxtral-Mini-3B-2507",
        "voxtral-small": "mistralai/Voxtral-Small-24B-2507",
        "mini": "mistralai/Voxtral-Mini-3B-2507",
        "small": "mistralai/Voxtral-Small-24B-2507",
    },
    "voxtral_local": {
        "voxtral-mini": "mistralai/Voxtral-Mini-3B-2507",
        "voxtral-small": "mistralai/Voxtral-Small-24B-2507",
        "mini": "mistralai/Voxtral-Mini-3B-2507",
        "small": "mistralai/Voxtral-Small-24B-2507",
    },
}


def normalize_model_name(kind: EngineKind, name: str | None) -> str:
    """Resolve aliases and provide defaults per engine kind.

    For whisper_turbo: maps full names to shorter faster-whisper compatible names
    (e.g., "openai/whisper-large-v3" -> "large-v3"). faster-whisper accepts both formats.

    If a model name from a different engine is passed (e.g., whisper model for voxtral),
    falls back to the default for the requested engine kind.
    """
    default = _DEFAULTS.get(kind)
    if not name:
        name = default or ""
    else:
        # Check if this is a model name from a different engine - if so, use default
        if kind in ("voxtral", "voxtral_local"):
            # If passed a whisper model, use voxtral default
            if name in WHISPER_MODELS or any(name.startswith(p) for p in ["distil-whisper/", "openai/whisper"]):
                name = default or ""
        elif kind == "whisper_turbo":
            # If passed a voxtral model, use whisper default
            if name in VOXTRAL_MODELS or name.startswith("mistralai/"):
                name = default or ""
        elif kind == "canary_qwen":
            if _is_invalid_canary_model(name, default):
                name = default or ""

        alias = _ALIASES.get(kind, {})
        lookup = alias.get(name.lower()) if name else None
        name = lookup or name or default or ""

    # For whisper_turbo, prefer short names for faster-whisper (better compatibility)
    if kind == "whisper_turbo" and name in WHISPER_MODELS:
        return WHISPER_MODELS[name]

    if kind == "canary_qwen" and name in CANARY_MODELS:
        return CANARY_MODELS[name]

    return name
