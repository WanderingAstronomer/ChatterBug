from __future__ import annotations

from pathlib import Path
import os

import typer

from vociferous.audio.components import (
    DecoderComponent,
    VADComponent,
    CondenserComponent,
)
from vociferous.app import TranscriptionSession
from vociferous.app.sinks import PolishingSink
from vociferous.cli.helpers import build_audio_source, build_sink, build_transcribe_configs_from_cli
from vociferous.config import load_config
from vociferous.domain.exceptions import AudioDecodeError, DependencyError, EngineError, ConfigurationError
from vociferous.domain.model import TranscriptionPreset, EngineKind
from vociferous.engines.factory import build_engine
from vociferous.polish.factory import build_polisher


def _run_transcription(
    audio_path: Path,
    *,
    engine: EngineKind,
    language: str,
    output: Path | None,
    preset: TranscriptionPreset | None,
    polish: bool | None,
) -> None:
    config = load_config()
    bundle = build_transcribe_configs_from_cli(
        app_config=config,
        engine=engine,
        language=language,
        preset=preset,
        polish=polish,
    )

    if bundle.numexpr_threads is not None:
        os.environ["NUMEXPR_MAX_THREADS"] = str(bundle.numexpr_threads)

    try:
        engine_adapter = build_engine(engine, bundle.engine_config)
        polisher = build_polisher(bundle.polisher_config) if bundle.polisher_config.enabled else None
    except (DependencyError, EngineError) as exc:
        raise RuntimeError(f"Engine initialization error: {exc}") from exc
    except ConfigurationError as exc:
        raise RuntimeError(f"Polisher error: {exc}") from exc

    source = build_audio_source(audio_path, config)
    sink = build_sink(output=output)
    if polisher is not None:
        sink = PolishingSink(sink, polisher)

    session = TranscriptionSession()
    session.start(source, engine_adapter, sink, bundle.options, engine_kind=engine)
    session.join()


def register_transcribe_full(app: typer.Typer) -> None:
    @app.command("transcribe-full", rich_help_panel="Core Commands")
    def transcribe_full_cmd(
        input: Path = typer.Argument(..., metavar="INPUT", help="Audio file to process end-to-end"),
        engine: EngineKind = typer.Option("whisper_turbo", "--engine", "-e", help="Transcription engine to use"),
        language: str = typer.Option("en", "--language", "-l", help="Language code or 'auto'"),
        output: Path | None = typer.Option(
            None,
            "--output",
            "-o",
            metavar="PATH",
            help="Final transcript path (default: <input>_transcript.txt)",
        ),
        threshold: float = typer.Option(0.5, help="VAD threshold (0-1, higher = stricter)"),
        min_silence_ms: int = typer.Option(500, help="Minimum silence between segments (ms)"),
        min_speech_ms: int = typer.Option(250, help="Minimum speech duration (ms)"),
        margin_ms: int = typer.Option(1000, help="Silence margin to keep at edges (ms)"),
        max_duration_min: int = typer.Option(30, help="Maximum duration per condensed file (minutes)"),
        preset: TranscriptionPreset | None = typer.Option(
            None,
            "--preset",
            "-p",
            help="Transcription preset: fast, balanced, high_accuracy",
            case_sensitive=False,
            show_default=False,
        ),
        polish: bool | None = typer.Option(
            None,
            "--polish/--no-polish",
            help="Post-process final transcript text",
            show_default=False,
        ),
    ) -> None:
        if not input.exists():
            typer.echo(f"Error: file not found: {input}", err=True)
            raise typer.Exit(code=2)

        base = input.stem
        decoded_path = Path(f"{base}_decoded.wav")
        timestamps_path = Path(f"{base}_decoded_vad_timestamps.json")
        condensed_path = Path(f"{base}_decoded_condensed.wav")
        transcript_path = output or Path(f"{base}_transcript.txt")

        # 1) Decode
        typer.echo("[1/5] Decoding...")
        try:
            decoded_path = DecoderComponent().decode_to_wav(input, decoded_path)
        except FileNotFoundError as exc:
            typer.echo("ffmpeg not found. Install ffmpeg and retry.", err=True)
            raise typer.Exit(code=2) from exc
        except AudioDecodeError as exc:
            typer.echo(f"Decode failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        # 2) VAD
        typer.echo("[2/5] Detecting speech...")
        timestamps = VADComponent().detect(
            decoded_path,
            output_path=timestamps_path,
            threshold=threshold,
            min_silence_ms=min_silence_ms,
            min_speech_ms=min_speech_ms,
        )
        if not timestamps:
            typer.echo("No speech detected; aborting.", err=True)
            raise typer.Exit(code=1)

        typer.echo(f"Found {len(timestamps)} segments.")

        # 3) Condense
        typer.echo("[3/5] Condensing...")
        try:
            condensed_files = CondenserComponent().condense(
                timestamps_path,
                decoded_path,
                output_path=condensed_path,
                margin_ms=margin_ms,
                max_duration_min=max_duration_min,
            )
        except (ValueError, AudioDecodeError) as exc:
            typer.echo(f"Condense failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        if not condensed_files:
            typer.echo("No condensed output generated.", err=True)
            raise typer.Exit(code=1)
        condensed_path = condensed_files[0]

        # 4) Transcribe
        typer.echo("[4/5] Transcribing...")
        try:
            _run_transcription(
                condensed_path,
                engine=engine,
                language=language,
                output=transcript_path,
                preset=preset,
                polish=polish,
            )
        except Exception as exc:
            typer.echo(f"Transcription failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        typer.echo("[5/5] Polishing complete." if polish else "[5/5] Done.")
        typer.echo(f"✓ Final transcript: {transcript_path}")

    return None
