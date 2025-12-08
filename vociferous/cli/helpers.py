"""CLI helper functions for config building and preset resolution.

Extracted from main.py to reduce monolithic script size and improve testability.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from vociferous.config.schema import AppConfig
from vociferous.domain import EngineConfig, TranscriptSink
from vociferous.domain.model import (
    DEFAULT_WHISPER_MODEL,
    EngineKind,
    TranscriptionOptions,
    TranscriptionPreset,
)
from vociferous.engines.model_registry import normalize_model_name
from vociferous.polish.base import PolisherConfig


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


@dataclass
class TranscribeConfigBundle:
    engine_config: EngineConfig
    options: TranscriptionOptions
    polisher_config: PolisherConfig
    preset: str
    numexpr_threads: int | None


def build_transcribe_configs(
    *,
    app_config: AppConfig,
    engine: EngineKind,
    language: str,
    preset: TranscriptionPreset | None,
    fast_flag: bool,
    model: str | None,
    device: str | None,
    compute_type: str | None,
    batch_size: int,
    beam_size: int,
    enable_batching: bool,
    vad_filter: bool,
    word_timestamps: bool,
    vllm_endpoint: str,
    clean_disfluencies: bool,
    no_clean_disfluencies: bool,
    polish: bool | None,
    polish_model: str | None,
    polish_max_tokens: int,
    polish_temperature: float,
    polish_gpu_layers: int,
    polish_context_length: int,
    numexpr_max_threads: int | None,
    prompt: str | None,
    max_new_tokens: int,
    gen_temperature: float,
    whisper_temperature: float,
) -> TranscribeConfigBundle:
    """Resolve CLI/config settings into engine/polisher/options configs."""
    preset_lower = (preset or "").replace("-", "_").lower()
    if fast_flag and not preset_lower:
        preset_lower = "fast"
    if not preset_lower and engine in {"whisper_vllm", "voxtral_vllm"}:
        preset_lower = "balanced"

    target_device = device or app_config.device
    resolved_model = model or (app_config.model_name if engine == app_config.engine else None)
    resolved_compute = compute_type or app_config.compute_type
    resolved_beam = beam_size
    resolved_batch = batch_size
    resolved_enable_batching = enable_batching
    resolved_vad = vad_filter

    if preset_lower in {"high_accuracy", "balanced", "fast"}:
        preset_settings = resolve_preset(
            preset_lower,
            engine,
            target_device,
            current_model=resolved_model,
            current_compute_type=resolved_compute,
            current_beam_size=beam_size,
            current_batch_size=batch_size,
        )
        resolved_model = preset_settings.model
        resolved_compute = preset_settings.compute_type or resolved_compute
        resolved_beam = preset_settings.beam_size
        resolved_batch = preset_settings.batch_size
        resolved_enable_batching = preset_settings.enable_batching
        resolved_vad = preset_settings.vad_filter

    from typing import cast
    preset_value: TranscriptionPreset | None = (
        cast(TranscriptionPreset, preset_lower) if preset_lower in {"high_accuracy", "balanced", "fast"} else None
    )

    numexpr_threads = app_config.numexpr_max_threads if numexpr_max_threads is None else numexpr_max_threads
    clean_disfluencies_value = clean_disfluencies or not no_clean_disfluencies

    polisher_config = build_polisher_config(
        enabled=app_config.polish_enabled if polish is None else polish,
        model=polish_model or app_config.polish_model,
        base_params=app_config.polish_params,
        max_tokens=polish_max_tokens,
        temperature=polish_temperature,
        gpu_layers=polish_gpu_layers,
        context_length=polish_context_length,
    )

    engine_config = build_engine_config(
        engine,
        model_name=resolved_model or (app_config.model_name if engine == app_config.engine else None),
        compute_type=resolved_compute or app_config.compute_type,
        device=target_device,
        model_cache_dir=app_config.model_cache_dir,
        params=app_config.params,
        preset=preset_lower,
        word_timestamps=word_timestamps,
        enable_batching=resolved_enable_batching,
        batch_size=resolved_batch,
        vad_filter=resolved_vad,
        clean_disfluencies=clean_disfluencies_value,
        vllm_endpoint=vllm_endpoint,
    )

    options = TranscriptionOptions(
        language=language,
        preset=preset_value,
        prompt=prompt,
        params={
            "max_new_tokens": str(max_new_tokens) if max_new_tokens > 0 else "",
            "temperature": str(gen_temperature) if gen_temperature > 0 else "",
        },
        beam_size=resolved_beam if resolved_beam > 0 else None,
        temperature=whisper_temperature if whisper_temperature > 0 else None,
    )

    return TranscribeConfigBundle(
        engine_config=engine_config,
        options=options,
        polisher_config=polisher_config,
        preset=preset_lower,
        numexpr_threads=numexpr_threads,
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
    from vociferous.app.sinks import (
        ClipboardSink, FileSink, HistorySink, StdoutSink, CompositeSink
    )
    from vociferous.storage.history import HistoryStorage

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
