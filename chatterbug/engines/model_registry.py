from __future__ import annotations

from typing import Dict

from chatterbug.domain.model import EngineKind

# Verified model names for faster-whisper (accepts short names or full Systran paths)
WHISPER_MODELS: Dict[str, str] = {
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

PARAKEET_MODELS: Dict[str, str] = {
    "nvidia/parakeet-rnnt-1.1b": "https://huggingface.co/nvidia/parakeet-rnnt-1.1b",
}

_DEFAULTS = {
    "whisper_turbo": "distil-whisper/distil-large-v3",
    "voxtral": "mistralai/Voxtral-Mini-3B-2507",
    "parakeet_rnnt": "nvidia/parakeet-rnnt-1.1b",
}

_ALIASES: Dict[str, Dict[str, str]] = {
    "whisper_turbo": {
        "turbo": "openai/whisper-large-v3-turbo",
        "large-v3-turbo": "openai/whisper-large-v3-turbo",
        "large-v3": "openai/whisper-large-v3",
        "distil-large-v3": "distil-whisper/distil-large-v3",
        "medium": "openai/whisper-medium",
        "small": "openai/whisper-small",
        "base": "openai/whisper-base",
        "tiny": "openai/whisper-tiny",
    },
    "voxtral": {
        "voxtral-mini": "mistralai/Voxtral-Mini-3B-2507",
        "voxtral-small": "mistralai/Voxtral-Small-24B-2507",
        "mini": "mistralai/Voxtral-Mini-3B-2507",
        "small": "mistralai/Voxtral-Small-24B-2507",
    },
    "parakeet_rnnt": {
        "parakeet": "nvidia/parakeet-rnnt-1.1b",
        "parakeet-rnnt": "nvidia/parakeet-rnnt-1.1b",
    },
}


def normalize_model_name(kind: EngineKind, name: str | None) -> str:
    """Resolve aliases and provide defaults per engine kind.
    
    For whisper_turbo: maps full names to shorter faster-whisper compatible names
    (e.g., "openai/whisper-large-v3" -> "large-v3"). faster-whisper accepts both formats.
    """
    default = _DEFAULTS.get(kind)
    if not name:
        name = default or ""
    else:
        alias = _ALIASES.get(kind, {})
        lookup = alias.get(name.lower())
        name = lookup or name
    
    # For whisper_turbo, prefer short names for faster-whisper (better compatibility)
    if kind == "whisper_turbo" and name in WHISPER_MODELS:
        return WHISPER_MODELS[name]
    
    return name
