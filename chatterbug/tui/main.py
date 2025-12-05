from __future__ import annotations

from pathlib import Path

from chatterbug.app import TranscriptionSession
from chatterbug.audio.sources import FileSource, MicrophoneSource
from chatterbug.cli.sinks import StdoutSink
from chatterbug.config import load_config
from chatterbug.domain import EngineConfig, TranscriptionOptions
from chatterbug.domain.model import EngineKind
from chatterbug.engines.factory import build_engine


def run_tui(file: Path | None = None, engine: EngineKind = "whisper_turbo", language: str = "en") -> None:
    """Minimal Rich-based TUI: streams segments to stdout live."""
    # This is intentionally simple to avoid heavy UI coupling; can be swapped for Textual later.
    config = load_config()
    engine_config = EngineConfig(
        model_name=config.model_name,
        compute_type=config.compute_type,
        device=config.device,
        model_cache_dir=config.model_cache_dir,
        params={**config.params, "vllm_endpoint": config.vllm_endpoint},
    )
    engine_adapter = build_engine(engine, engine_config)
    source = FileSource(file) if file else MicrophoneSource()
    sink = StdoutSink()
    session = TranscriptionSession()

    session.start(source, engine_adapter, sink, TranscriptionOptions(language=language), engine_kind=engine)

    try:
        session.join()
    except KeyboardInterrupt:
        session.stop()
        session.join()
