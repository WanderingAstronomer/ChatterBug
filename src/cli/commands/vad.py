from __future__ import annotations

from pathlib import Path

import typer

from vociferous.audio.components import VADComponent
from vociferous.domain.exceptions import AudioDecodeError


def register_vad(app: typer.Typer) -> None:
    @app.command("vad", rich_help_panel="Audio Components")
    def vad_cmd(
        input: Path = typer.Argument(..., metavar="INPUT_WAV", help="PCM mono 16kHz WAV"),
        output: Path | None = typer.Option(
            None,
            "--output",
            "-o",
            metavar="PATH",
            help="Optional output path for timestamps JSON (default: <input>_vad_timestamps.json)",
        ),
        threshold: float = typer.Option(0.5, help="VAD threshold (0-1, higher = stricter)"),
        min_silence_ms: int = typer.Option(500, help="Minimum silence between segments (ms)"),
        min_speech_ms: int = typer.Option(250, help="Minimum speech duration (ms)"),
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
            )
        except AudioDecodeError as exc:
            typer.echo(f"VAD decode failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        speech_duration = sum(ts["end"] - ts["start"] for ts in timestamps)
        typer.echo(f"Found {len(timestamps)} segments ({speech_duration:.1f}s of speech)")
        typer.echo(f"✓ Saved: {output_path}")

    return None
