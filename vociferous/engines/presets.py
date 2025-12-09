from __future__ import annotations

"""Shared preset definitions and helpers for transcription engines.

Quality Presets (whisper_turbo):
---------------------------------
- balanced (default): Large-v3-turbo, float16/int8, beam=1, batch=12
  Best general-purpose option with good speed/quality balance.

- fast: Large-v3-turbo, int8_float16 mixed, beam=1, batch=16
  Maximum speed, slightly lower accuracy. Good for drafts or bulk processing.

- high_accuracy: Full large-v3, float16/int8, beam=2, batch=8
  Best quality with beam search. Slower but more accurate for important content.

Key differences:
- Model: high_accuracy uses full large-v3 (more parameters), others use turbo variant
- Beam size: high_accuracy uses beam=2 (explores hypotheses), others use greedy (beam=1)
- Compute: fast uses mixed int8_float16 for speed, others use standard precision
- Batch size: fast=16 (throughput), high_accuracy=8 (careful), balanced=12 (middle)
"""

from typing import Mapping, TypedDict

from vociferous.domain.model import DEFAULT_WHISPER_MODEL


class WhisperPreset(TypedDict, total=False):
    model_name: str
    precision: Mapping[str, str]
    beam_size: int
    temperature: float
    window_sec: float
    hop_sec: float

# Default CT2 Whisper presets shared across engines
WHISPER_TURBO_PRESETS: Mapping[str, WhisperPreset] = {
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


def get_preset_config(name: str, presets: Mapping[str, WhisperPreset], fallback: str) -> WhisperPreset:
    """Fetch a preset config with a safe fallback."""
    return presets.get(name) or presets[fallback]
