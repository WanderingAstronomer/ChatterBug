"""CLI helper functions for config building and preset resolution.

Extracted from main.py to reduce monolithic script size and improve testability.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from chatterbug.domain import EngineConfig, TranscriptSink
from chatterbug.domain.model import DEFAULT_WHISPER_MODEL, EngineKind
from chatterbug.engines.model_registry import normalize_model_name
from chatterbug.polish.base import PolisherConfig


@dataclass
class PresetSettings:
    """Resolved settings from a preset."""
    model: str | None
    compute_type: str | None
    beam_size: int
    batch_size: int
    enable_batching: bool
    vad_filter: bool


def resolve_preset(
    preset: str,
    engine: EngineKind,
    device: str,
    *,
    current_model: str | None = None,
    current_compute_type: str | None = None,
    current_beam_size: int = 1,
    current_batch_size: int = 16,
) -> PresetSettings:
    """Resolve preset to concrete engine settings.
    
    Args:
        preset: One of 'fast', 'balanced', 'high_accuracy'
        engine: Engine kind being used
        device: Target device ('cpu' or 'cuda')
        current_*: Current values that may be overridden
        
    Returns:
        PresetSettings with resolved values
    """
    model = current_model
    compute_type = current_compute_type
    beam_size = current_beam_size
    batch_size = current_batch_size
    enable_batching = True
    vad_filter = True

    if engine == "whisper_vllm":
        if preset == "high_accuracy":
            model = model or "openai/whisper-large-v3"
            compute_type = compute_type or ("bfloat16" if device == "cuda" else "float32")
            beam_size = 2
        elif preset == "fast":
            model = model or "openai/whisper-large-v3-turbo"
            compute_type = compute_type or ("float16" if device == "cuda" else "int8")
            beam_size = 1
        else:  # balanced
            model = model or "openai/whisper-large-v3-turbo"
            compute_type = compute_type or ("bfloat16" if device == "cuda" else "float32")
            beam_size = max(beam_size, 1)
            
    elif engine == "whisper_turbo":
        if preset == "high_accuracy":
            model = model or "openai/whisper-large-v3"
            compute_type = compute_type or ("float16" if device == "cuda" else "int8")
            beam_size = max(beam_size, 2)
            batch_size = max(batch_size, 8)
        elif preset == "fast":
            model = model or DEFAULT_WHISPER_MODEL
            compute_type = compute_type or "int8_float16"
            beam_size = 1
            batch_size = max(batch_size, 16)
        else:  # balanced
            model = model or DEFAULT_WHISPER_MODEL
            compute_type = compute_type or ("float16" if device == "cuda" else "int8")
            beam_size = max(beam_size, 1)
            batch_size = max(batch_size, 12)

    return PresetSettings(
        model=model,
        compute_type=compute_type,
        beam_size=beam_size,
        batch_size=batch_size,
        enable_batching=enable_batching,
        vad_filter=vad_filter,
    )


def build_engine_config(
    engine: EngineKind,
    *,
    model_name: str | None,
    compute_type: str | None,
    device: str,
    model_cache_dir: str | None,
    params: Mapping[str, str],
    preset: str = "",
    word_timestamps: bool = False,
    enable_batching: bool = True,
    batch_size: int = 16,
    vad_filter: bool = True,
    clean_disfluencies: bool = True,
    vllm_endpoint: str = "http://localhost:8000",
) -> EngineConfig:
    """Build an EngineConfig from CLI options.
    
    Normalizes model name and constructs params dict.
    """
    normalized_model = normalize_model_name(engine, model_name) if model_name else DEFAULT_WHISPER_MODEL
    
    return EngineConfig(
        model_name=normalized_model,
        compute_type=compute_type or "auto",
        device=device,
        model_cache_dir=model_cache_dir,
        params={
            **params,
            "preset": preset,
            "word_timestamps": str(word_timestamps).lower(),
            "enable_batching": str(enable_batching).lower(),
            "batch_size": str(batch_size),
            "vad_filter": str(vad_filter).lower(),
            "clean_disfluencies": str(clean_disfluencies).lower(),
            "vllm_endpoint": vllm_endpoint,
        },
    )


def build_polisher_config(
    *,
    enabled: bool,
    model: str | None,
    base_params: Mapping[str, str],
    max_tokens: int = 128,
    temperature: float = 0.2,
    gpu_layers: int = 0,
    context_length: int = 2048,
) -> PolisherConfig:
    """Build a PolisherConfig from CLI options."""
    return PolisherConfig(
        enabled=enabled,
        model=model,
        params={
            **base_params,
            "max_tokens": str(max_tokens),
            "temperature": str(temperature),
            "gpu_layers": str(gpu_layers),
            "context_length": str(context_length),
        },
    )


def build_sink(
    *,
    output: Path | None,
    clipboard: bool,
    save_history: bool,
    history_dir: Path,
    history_limit: int,
) -> TranscriptSink:
    """Build a composed sink from CLI flags.
    
    Returns a CompositeSink wrapping all enabled sinks.
    Falls back to StdoutSink if no other outputs specified.
    """
    from chatterbug.app.sinks import (
        ClipboardSink, FileSink, HistorySink, StdoutSink, CompositeSink
    )
    from chatterbug.storage.history import HistoryStorage

    sinks: list[TranscriptSink] = []
    if output:
        sinks.append(FileSink(output))
    if clipboard:
        sinks.append(ClipboardSink())
    if save_history:
        storage = HistoryStorage(history_dir, limit=history_limit)
        sinks.append(HistorySink(storage, target=output))
    if not sinks:
        sinks.append(StdoutSink())

    return CompositeSink(sinks)
