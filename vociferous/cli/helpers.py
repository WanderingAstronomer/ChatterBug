"""CLI helper functions for config building.

Extracted from main.py to reduce monolithic script size and improve testability.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from vociferous.config.schema import AppConfig
from vociferous.domain import EngineConfig, TranscriptSink
from vociferous.domain.model import (
    EngineKind,
    TranscriptionOptions,
)
from vociferous.engines.model_registry import normalize_model_name
from vociferous.refinement.base import RefinerConfig
from vociferous.sources import FileSource, Source


@dataclass
class TranscribeConfigBundle:
    """Bundle of all configs needed for transcription."""
    engine_config: EngineConfig
    options: TranscriptionOptions
    refiner_config: RefinerConfig
    numexpr_threads: int | None


def build_engine_config(
    engine: EngineKind,
    *,
    model_name: str | None,
    compute_type: str | None,
    device: str,
    model_cache_dir: str | None,
    params: Mapping[str, str],
) -> EngineConfig:
    """Build an EngineConfig from CLI options.
    
    Normalizes model name and constructs params dict.
    """
    normalized_model = normalize_model_name(engine, model_name)
    
    return EngineConfig(
        model_name=normalized_model,
        compute_type=compute_type or "auto",
        device=device,
        model_cache_dir=model_cache_dir,
        params=params,
    )


def build_refiner_config(
    *,
    enabled: bool,
    model: str | None,
    base_params: Mapping[str, str],
    max_tokens: int = 128,
    temperature: float = 0.2,
    gpu_layers: int = 0,
    context_length: int = 2048,
) -> RefinerConfig:
    """Build a RefinerConfig from CLI options."""
    params = dict(base_params)
    if model:
        params["model"] = model
    params.update({
        "max_tokens": str(max_tokens),
        "temperature": str(temperature),
        "gpu_layers": str(gpu_layers),
        "context_length": str(context_length),
    })
    return RefinerConfig(
        enabled=enabled,
        params=params,
    )


def build_transcribe_configs_from_cli(
    *,
    app_config: AppConfig,
    engine: EngineKind,
    language: str,
    refine: bool | None,
) -> TranscribeConfigBundle:
    """Build transcription configs from CLI user-facing options.
    
    All advanced settings come from AppConfig (loaded from ~/.config/vociferous/config.toml).
    
    Args:
        app_config: Loaded application configuration
        engine: Engine selected by user (--engine)
        language: Language code (--language)
        refine: Refinement flag (--refine/--no-refine); True enables, False disables
        
    Returns:
        Complete config bundle for transcription
    """
    target_device = app_config.device
    resolved_model = app_config.model_name if engine == app_config.engine else None
    resolved_compute = app_config.compute_type
    
    # Refiner enabled by CLI flag (explicit user choice)
    # Only Canary-Qwen supports refinement; other engines ignore this
    refiner_enabled = refine if refine is not None else False

    refiner_config = build_refiner_config(
        enabled=refiner_enabled,
        model=None,  # Refinement uses engine's LLM mode (Canary-Qwen only)
        base_params={},
    )

    # Build engine config
    engine_config = build_engine_config(
        engine,
        model_name=resolved_model,
        compute_type=resolved_compute,
        device=target_device,
        model_cache_dir=app_config.model_cache_dir,
        params=app_config.params,
    )

    # Build transcription options
    options = TranscriptionOptions(
        language=language,
        params={},
    )

    return TranscribeConfigBundle(
        engine_config=engine_config,
        options=options,
        refiner_config=refiner_config,
        numexpr_threads=app_config.numexpr_max_threads,
    )


def build_sink(
    *,
    output: Path | None,
) -> TranscriptSink:
    """Build output sink from CLI flags.
    
    If output path provided, writes to file. Otherwise writes to stdout.
    
    Args:
        output: Optional output file path
        
    Returns:
        TranscriptSink implementation
    """
    from vociferous.app.sinks import FileSink, StdoutSink

    if output:
        return FileSink(output)
    return StdoutSink()


def build_audio_source(
    *,
    audio_path: Path,
    cache_dir: Path | None = None,
) -> Source:
    """Build audio source from path.
    
    Args:
        audio_path: Path to audio file
        cache_dir: Optional cache directory for intermediate files
        
    Returns:
        Source implementation
    """
    return FileSource(audio_path)
