from __future__ import annotations

"""Standalone Canary-Qwen transcription entrypoint."""

from pathlib import Path

import typer

from vociferous.domain.model import EngineConfig, TranscriptionOptions
from vociferous.engines.canary_qwen import CanaryQwenEngine


def register_transcribe_canary(app: typer.Typer) -> None:
    @app.command("transcribe-canary", rich_help_panel="Core Commands")
    def transcribe_canary_cmd(
        input: Path = typer.Argument(..., metavar="INPUT", help="Audio file to process with Canary-Qwen"),
        output: Path | None = typer.Option(None, "--output", "-o", help="Optional transcript output path"),
        refine: bool = typer.Option(True, "--refine/--no-refine", help="Run LLM refinement after ASR"),
        instructions: str | None = typer.Option(
            None,
            "--instructions",
            "-i",
            help="Override default refinement instructions",
        ),
        use_mock: bool = typer.Option(
            True,
            "--mock/--no-mock",
            help="Use lightweight mock path (no model download)",
            show_default=True,
        ),
    ) -> None:
        """Dual-pass Canary-Qwen workflow (ASR + optional refinement)."""
        if not input.exists():
            typer.echo(f"Error: file not found: {input}", err=True)
            raise typer.Exit(code=2)

        config = EngineConfig(
            model_name="nvidia/canary-qwen-2.5b",
            params={"mode": "asr", "use_mock": str(use_mock).lower()},
        )
        engine = CanaryQwenEngine(config)
        options = TranscriptionOptions(language="en")

        segments = engine.transcribe_file(input, options)
        raw_text = " ".join(seg.text for seg in segments).strip()

        final_text = engine.refine_text(raw_text, instructions) if refine else raw_text

        if output:
            output.write_text(final_text, encoding="utf-8")
            typer.echo(f"✓ Saved transcript to {output}")
        else:
            typer.echo(final_text)
