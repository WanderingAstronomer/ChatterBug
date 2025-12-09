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
    AudioSource,
    DEFAULT_WHISPER_MODEL,
    EngineKind,
    PreprocessingConfig,
    TranscriptionOptions,
    TranscriptionPreset,
)
from vociferous.engines.model_registry import normalize_model_name
from vociferous.polish.base import PolisherConfig
from vociferous.sources import FileSource


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

    if engine == "whisper_turbo":
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
    """Bundle of all configs needed for transcription."""
    engine_config: EngineConfig
    options: TranscriptionOptions
    polisher_config: PolisherConfig
    preset: str
    numexpr_threads: int | None


def build_transcribe_configs_from_cli(
    *,
    app_config: AppConfig,
    engine: EngineKind,
    language: str,
    preset: TranscriptionPreset | None,
    polish: bool | None,
) -> TranscribeConfigBundle:
    """Build transcription configs from CLI user-facing options only.
    
    All advanced settings come from AppConfig (loaded from ~/.config/vociferous/config.toml).
    This is the clean separation: CLI for user intent, config file for tuning.
    
    Args:
        app_config: Loaded application configuration
        engine: Engine selected by user (--engine)
        language: Language code (--language)
        preset: Quality preset (--preset) or None for defaults
        
    Returns:
        Complete config bundle for transcription
    """
    # Normalize preset
    preset_lower = (preset or "").replace("-", "_").lower()

    # Resolve model/compute/batch settings from preset
    target_device = app_config.device
    resolved_model = app_config.model_name if engine == app_config.engine else None
    resolved_compute = app_config.compute_type
    
    # Extract current batch settings from config params
    current_batch_size = int(app_config.params.get("batch_size", "16"))
    current_enable_batching = app_config.params.get("enable_batching", "true").lower() == "true"
    current_vad = app_config.params.get("vad_filter", "true").lower() == "true"
    current_word_timestamps = app_config.params.get("word_timestamps", "false").lower() == "true"
    
    resolved_beam = 1
    resolved_batch = current_batch_size
    resolved_enable_batching = current_enable_batching
    resolved_vad = current_vad

    if preset_lower in {"high_accuracy", "balanced", "fast"}:
        preset_settings = resolve_preset(
            preset_lower,
            engine,
            target_device,
            current_model=resolved_model,
            current_compute_type=resolved_compute,
            current_beam_size=1,
            current_batch_size=current_batch_size,
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

    # Polisher config from AppConfig only
    polisher_enabled = app_config.polish_enabled if polish is None else polish

    polisher_config = build_polisher_config(
        enabled=polisher_enabled,
        model=app_config.polish_model,
        base_params=app_config.polish_params,
        max_tokens=int(app_config.polish_params.get("max_tokens", "128")),
        temperature=float(app_config.polish_params.get("temperature", "0.2")),
        gpu_layers=int(app_config.polish_params.get("gpu_layers", "0")),
        context_length=int(app_config.polish_params.get("context_length", "2048")),
    )

    # Build engine config using resolved preset values + config defaults
    engine_config = build_engine_config(
        engine,
        model_name=resolved_model or app_config.model_name,
        compute_type=resolved_compute,
        device=target_device,
        model_cache_dir=app_config.model_cache_dir,
        params=app_config.params,
        preset=preset_lower,
        word_timestamps=current_word_timestamps,
        enable_batching=resolved_enable_batching,
        batch_size=resolved_batch,
        vad_filter=resolved_vad,
        clean_disfluencies=True,  # Always enabled (users can disable in config.toml)
    )

    # Build transcription options (language + preset only from CLI)
    options = TranscriptionOptions(
        language=language,
        preset=preset_value,
        prompt=None,  # Advanced: config-only
        params={},  # Advanced params come from config
        beam_size=resolved_beam if resolved_beam > 0 else None,
        temperature=None,  # Advanced: config-only
    )

    return TranscribeConfigBundle(
        engine_config=engine_config,
        options=options,
        polisher_config=polisher_config,
        preset=preset_lower,
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
    path: Path,
    app_config: AppConfig,
) -> AudioSource:
    """Construct an audio source based on preprocessing settings.

    When preprocessing is enabled, uses SileroVAD and FFmpegCondenser for
    intelligent audio preprocessing. Otherwise falls back to standard FileSource.
    """
    preprocessing_enabled = getattr(app_config, "preprocessing_enabled", False)
    chunk_ms = getattr(app_config, "chunk_ms", 30000)

    if preprocessing_enabled:
        from vociferous.audio import SileroVAD, FFmpegCondenser
        from vociferous.sources import MemorySource
        from vociferous.audio.decoder import FfmpegDecoder
        
        # Use new VAD + Condenser pipeline
        vad = SileroVAD()
        
        # Detect speech timestamps
        threshold = 0.5
        min_silence_ms = getattr(app_config, "preprocessing_min_silence_duration_ms", 500)
        min_speech_ms = getattr(app_config, "preprocessing_min_speech_duration_ms", 300)
        
        timestamps = vad.detect_speech(
            path,
            threshold=threshold,
            min_silence_ms=min_silence_ms,
            min_speech_ms=min_speech_ms,
        )
        
        if timestamps:
            # Condense using FFmpegCondenser
            condenser = FFmpegCondenser()
            gap_threshold_ms = getattr(app_config, "preprocessing_gap_threshold_ms", 5000)
            
            try:
                condensed_files = condenser.condense(
                    path,
                    timestamps,
                    max_duration_minutes=30,
                    min_gap_for_split_s=gap_threshold_ms / 1000.0,
                )
                
                if condensed_files:
                    # Load condensed audio into memory
                    decoder = FfmpegDecoder()
                    pcm_segments = []
                    try:
                        for condensed_file in condensed_files:
                            decoded = decoder.decode(str(condensed_file))
                            pcm_segments.append(decoded.samples)
                    finally:
                        # Clean up temporary condensed files
                        for condensed_file in condensed_files:
                            try:
                                condensed_file.unlink(missing_ok=True)
                            except OSError:
                                pass  # Ignore cleanup failures
                    
                    return MemorySource(
                        pcm_segments=pcm_segments,
                        sample_rate=16000,
                        channels=1,
                        chunk_ms=chunk_ms,
                    )
            except Exception:
                # Fall through to FileSource if preprocessing fails
                pass
        
        # Fall through to FileSource if no speech detected or condensation failed

    return FileSource(
        path,
        chunk_ms=chunk_ms,
    )
