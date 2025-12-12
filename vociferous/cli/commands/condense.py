from __future__ import annotations

import json
import wave
from pathlib import Path
from typing import Annotated

import typer

from vociferous.cli.components import CondenserComponent
from vociferous.domain.exceptions import (
    AudioDecodeError,
    AudioProcessingError,
    UnsplittableSegmentError,
)


def register_condense(app: typer.Typer) -> None:
    @app.command("condense", rich_help_panel="Audio Components")
    def condense_cmd(
        timestamps_json: Annotated[
            Path,
            typer.Argument(..., metavar="TIMESTAMPS.json", help="Speech timestamps JSON"),
        ],
        audio: Annotated[
            Path,
            typer.Argument(..., metavar="AUDIO.wav", help="Standardized WAV to condense"),
        ],
        output: Annotated[
            Path | None,
            typer.Option(
                None,
                "--output",
                "-o",
                metavar="PATH",
                help="Optional output path (default: <audio>_condensed.wav). Disables multi-chunk splitting.",
            ),
        ] = None,
        # New intelligent chunking parameters
        max_chunk_s: Annotated[
            float,
            typer.Option(
                60.0,
                "--max-chunk-s",
                help="Hard ceiling for chunk duration (default: 60s for Canary)",
            ),
        ] = 60.0,
        search_start_s: Annotated[
            float,
            typer.Option(
                30.0,
                "--search-start-s",
                help="When to start looking for split points (seconds)",
            ),
        ] = 30.0,
        min_gap_s: Annotated[
            float,
            typer.Option(
                3.0,
                "--min-gap-s",
                help="Minimum silence gap for natural splits (seconds)",
            ),
        ] = 3.0,
        margin_ms: Annotated[
            int,
            typer.Option(
                300,
                "--margin-ms",
                help="Silence margin at chunk edges (milliseconds)",
            ),
        ] = 300,
        max_intra_gap_ms: Annotated[
            int,
            typer.Option(
                800,
                "--max-intra-gap-ms",
                help="Maximum preserved gap inside chunks (milliseconds)",
            ),
        ] = 800,
    ) -> None:
        """Condense audio with intelligent chunking that respects engine duration limits.
        
        Removes silence between speech segments and intelligently splits long audio
        into chunks that respect the engine's maximum input duration (60s for Canary).
        
        Natural splits occur at 3s+ silence gaps when possible. Force-splits occur
        at segment boundaries when no natural pauses are available.
        """
        if not timestamps_json.exists():
            typer.echo(f"Error: timestamps file not found: {timestamps_json}", err=True)
            raise typer.Exit(code=2)
        if not audio.exists():
            typer.echo(f"Error: audio file not found: {audio}", err=True)
            raise typer.Exit(code=2)

        with open(timestamps_json) as f:
            timestamps = json.load(f)

        typer.echo(f"Condensing {audio} using {timestamps_json}...")
        typer.echo(f"Processing {len(timestamps)} segments (max chunk: {max_chunk_s}s)...")

        component = CondenserComponent()
        try:
            outputs = component.condense(
                timestamps_json,
                audio,
                output_path=output,
                # Pass new parameters via legacy interface until profile support is added
                margin_ms=margin_ms,
                max_duration_s=max_chunk_s,
                min_gap_for_split_s=min_gap_s,
            )
        except UnsplittableSegmentError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        except (ValueError, AudioProcessingError) as exc:
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
            typer.echo(f"✓ Output: {len(outputs)} chunks (split at natural pauses)")
            for path in outputs:
                try:
                    with wave.open(str(path), "rb") as wf:
                        chunk_duration = wf.getnframes() / float(wf.getframerate())
                    typer.echo(f"  - {path.name} ({chunk_duration:.1f}s)")
                except Exception:
                    typer.echo(f"  - {path.name}")

    condense_cmd.dev_only = True  # type: ignore[attr-defined]
    return None
