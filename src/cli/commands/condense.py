from __future__ import annotations

import json
import wave
from pathlib import Path

import typer

from vociferous.audio.components import CondenserComponent
from vociferous.domain.exceptions import AudioDecodeError


def register_condense(app: typer.Typer) -> None:
    @app.command("condense", rich_help_panel="Audio Components")
    def condense_cmd(
        timestamps_json: Path = typer.Argument(..., metavar="TIMESTAMPS.json", help="Speech timestamps JSON"),
        audio: Path = typer.Argument(..., metavar="AUDIO.wav", help="Standardized WAV to condense"),
        output: Path | None = typer.Option(
            None,
            "--output",
            "-o",
            metavar="PATH",
            help="Optional output path (default: <audio>_condensed.wav)",
        ),
        margin_ms: int = typer.Option(1000, help="Silence margin to keep at edges (ms)"),
        max_duration_min: int = typer.Option(30, help="Maximum duration per output file (minutes)"),
    ) -> None:
        if not timestamps_json.exists():
            typer.echo(f"Error: timestamps file not found: {timestamps_json}", err=True)
            raise typer.Exit(code=2)
        if not audio.exists():
            typer.echo(f"Error: audio file not found: {audio}", err=True)
            raise typer.Exit(code=2)

        with open(timestamps_json, "r") as f:
            timestamps = json.load(f)

        typer.echo(f"Condensing {audio} using {timestamps_json}...")
        typer.echo(f"Processing {len(timestamps)} segments...")

        component = CondenserComponent()
        try:
            outputs = component.condense(
                timestamps_json,
                audio,
                output_path=output,
                margin_ms=margin_ms,
                max_duration_min=max_duration_min,
            )
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        except AudioDecodeError as exc:
            typer.echo(f"Condense failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        if not outputs:
            typer.echo("No output generated (no speech detected).", err=True)
            raise typer.Exit(code=1)

        if len(outputs) == 1:
            out = outputs[0]
            size_mb = out.stat().st_size / (1024 * 1024)
            try:
                with wave.open(str(out), "rb") as wf:
                    duration_s = wf.getnframes() / float(wf.getframerate())
            except Exception:
                duration_s = 0.0
            typer.echo(f"✓ Output: {out.name} ({size_mb:.2f} MB, {duration_s:.1f}s)")
        else:
            typer.echo(f"✓ Output: {len(outputs)} files")
            for path in outputs:
                typer.echo(f"  - {path}")

    return None
