from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from vociferous.cli.components import DecoderComponent
from vociferous.domain.exceptions import AudioDecodeError


def register_decode(app: typer.Typer) -> None:
    @app.command("decode", rich_help_panel="Audio Components")
    def decode_cmd(
        input: Annotated[Path, typer.Argument(..., metavar="INPUT", help="Audio file to standardize")],
        output: Annotated[
            Path | None,
            typer.Option(
                "--output",
                "-o",
                metavar="PATH",
                help="Optional output path (default: <input>_decoded.wav in CWD)",
            ),
        ] = None,
    ) -> None:
        typer.echo(f"Decoding {input}...")
        if not input.exists():
            typer.echo(f"Error: file not found: {input}", err=True)
            raise typer.Exit(code=2)

        component = DecoderComponent()
        try:
            out_path = component.decode_to_wav(input, output)
        except FileNotFoundError as exc:
            typer.echo("ffmpeg not found. Install ffmpeg and retry.", err=True)
            raise typer.Exit(code=2) from exc
        except AudioDecodeError as exc:
            typer.echo(f"Decode failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        size_mb = out_path.stat().st_size / (1024 * 1024)
        typer.echo(f"✓ Output: {out_path.name} (PCM mono 16kHz, {size_mb:.2f} MB)")

    decode_cmd.dev_only = True  # type: ignore[attr-defined]
    return None
