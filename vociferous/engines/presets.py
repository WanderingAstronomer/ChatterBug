from __future__ import annotations

"""Shared preset definitions and helpers for transcription engines."""

from typing import Mapping

from vociferous.domain.model import DEFAULT_WHISPER_MODEL

# Default CT2/vLLM Whisper presets shared across engines
WHISPER_TURBO_PRESETS: Mapping[str, dict[str, object]] = {
    # Default: large-v3-turbo CT2, FP16 on CUDA, INT8 on CPU
    "balanced": {
        "model_name": DEFAULT_WHISPER_MODEL,
        "precision": {"cuda": "float16", "cpu": "int8"},
        "beam_size": 1,
        "temperature": 0.0,
        "window_sec": 25.0,
        "hop_sec": 5.0,
    },
    # Accuracy-first: full large-v3, FP16 on CUDA
    "accuracy": {
        "model_name": "openai/whisper-large-v3",
        "precision": {"cuda": "float16", "cpu": "int8"},
        "beam_size": 2,
        "temperature": 0.0,
        "window_sec": 30.0,
        "hop_sec": 5.0,
    },
    # Latency-first: turbo INT8/FP16 mix on CUDA
    "low_latency": {
        "model_name": DEFAULT_WHISPER_MODEL,
        "precision": {"cuda": "int8_float16", "cpu": "int8"},
        "beam_size": 1,
        "temperature": 0.0,
        "window_sec": 18.0,
        "hop_sec": 4.0,
    },
}

WHISPER_VLLM_PRESETS: Mapping[str, dict[str, object]] = {
    "high_accuracy": {
        "model": "openai/whisper-large-v3",
        "beam_size": 2,
        "temperature": 0.0,
    },
    "balanced": {
        "model": "openai/whisper-large-v3-turbo",
        "beam_size": 1,
        "temperature": 0.0,
    },
    "fast": {
        "model": "openai/whisper-large-v3-turbo",
        "beam_size": 1,
        "temperature": 0.0,
    },
}


def resolve_preset_name(
    raw_value: str | None,
    presets: Mapping[str, object],
    *,
    default: str = "balanced",
    custom_label: str = "custom",
) -> tuple[str, bool]:
    """Normalize user-provided preset/profile names.

    Returns a tuple of (resolved preset name, was_explicit). Unknown explicit
    presets are mapped to custom to preserve previous behavior.
    """
    normalized = (raw_value or "").replace("-", "_").strip().lower()
    if not normalized:
        return default, False

    if normalized in presets:
        return normalized, True

    return custom_label, True


def get_preset_config(name: str, presets: Mapping[str, dict[str, object]], fallback: str) -> dict[str, object]:
    """Fetch a preset config with a safe fallback."""
    return presets.get(name) or presets[fallback]
