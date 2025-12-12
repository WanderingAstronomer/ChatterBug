from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from vociferous.cli.components import VADComponent
from vociferous.domain.exceptions import AudioDecodeError


def register_vad(app: typer.Typer) -> None:
    @app.command("vad", rich_help_panel="Audio Components")
    def vad_cmd(
        input: Annotated[
            Path,
            typer.Argument(..., metavar="INPUT_WAV", help="PCM mono 16kHz WAV"),
        ],
        output: Annotated[
            Path | None,
            typer.Option(
                "--output",
                "-o",
                metavar="PATH",
                help="Optional output path for timestamps JSON (default: <input>_vad_timestamps.json)",
            ),
        ] = None,
        threshold: Annotated[float, typer.Option(help="VAD threshold (0-1, higher = stricter)")] = 0.5,
        min_silence_ms: Annotated[int, typer.Option(help="Minimum silence between segments (ms)")] = 500,
        min_speech_ms: Annotated[int, typer.Option(help="Minimum speech duration (ms)")] = 250,
        speech_pad_ms: Annotated[int, typer.Option(help="Padding added to segment boundaries (ms)")] = 250,
        max_speech_duration_s: Annotated[float, typer.Option(help="Max duration for any speech segment (s)")] = 40.0,
    ) -> None:
        typer.echo(f"Detecting speech in {input}...")
        if not input.exists():
            typer.echo(f"Error: file not found: {input}", err=True)
            raise typer.Exit(code=2)

        output_path = output or input.with_name(f"{input.stem}_vad_timestamps.json")

        component = VADComponent()
        try:
            timestamps = component.detect(
                input,
                output_path=output_path,
                threshold=threshold,
                min_silence_ms=min_silence_ms,
                min_speech_ms=min_speech_ms,
                speech_pad_ms=speech_pad_ms,
                max_speech_duration_s=max_speech_duration_s,
            )
        except FileNotFoundError as exc:
            typer.echo("ffmpeg not found. Install ffmpeg and retry.", err=True)
            raise typer.Exit(code=2) from exc
        except AudioDecodeError as exc:
            typer.echo(f"VAD decode failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        speech_duration = sum(ts["end"] - ts["start"] for ts in timestamps)
        typer.echo(f"Found {len(timestamps)} segments ({speech_duration:.1f}s of speech)")
        typer.echo(f"✓ Saved: {output_path}")

    vad_cmd.dev_only = True  # type: ignore[attr-defined]
    return None
