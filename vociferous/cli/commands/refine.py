from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from vociferous.cli.helpers import build_refiner_config
from vociferous.config import load_config
from vociferous.domain.exceptions import ConfigurationError, DependencyError
from vociferous.domain.model import DEFAULT_CANARY_MODEL
from vociferous.refinement.factory import build_refiner


def register_refine(app: typer.Typer) -> None:
    @app.command("refine", rich_help_panel="Refinement Components")
    def refine_cmd(
        input: Annotated[
            Path,
            typer.Argument(..., metavar="TRANSCRIPT", help="Path to raw transcript text file"),
        ],
        output: Annotated[
            Path | None,
            typer.Option(
                "--output",
                "-o",
                metavar="PATH",
                help="Write refined text to file (default: stdout)",
            ),
        ] = None,
        mode: Annotated[
            str | None,
            typer.Option(
                "--mode",
                help="Refinement mode: grammar_only (default), summary, bullet_points",
                show_default=False,
            ),
        ] = None,
        instructions: Annotated[
            str | None,
            typer.Option(
                "--instructions",
                "-i",
                help="Custom refinement instructions (overrides mode)",
                show_default=False,
            ),
        ] = None,
        model: Annotated[
            str | None,
            typer.Option(
                "--model",
                "-m",
                help="Refiner model (defaults to config refinement_model)",
                show_default=False,
            ),
        ] = None,
        max_tokens: Annotated[int, typer.Option(help="Max tokens for LLM-based refiners")] = 128,
        temperature: Annotated[float, typer.Option(help="Temperature for LLM-based refiners")] = 0.2,
        gpu_layers: Annotated[int, typer.Option(help="GPU layers for llama-cpp refiners")] = 0,
        context_length: Annotated[int, typer.Option(help="Context length for llama-cpp refiners")] = 2048,
    ) -> None:
        """Refine a transcript text file using Canary-Qwen LLM.

        MODES:
            grammar_only   - Fix grammar, punctuation, capitalization (default)
            summary        - Produce a concise summary of key points
            bullet_points  - Convert to structured bullet points

        EXAMPLES:
            vociferous refine transcript.txt -o refined.txt
            vociferous refine transcript.txt --mode summary
            vociferous refine transcript.txt --instructions \"Make it formal\"
        """
        if not input.exists():
            typer.echo(f"Error: transcript not found: {input}", err=True)
            raise typer.Exit(code=2)
        try:
            raw_text = input.read_text(encoding="utf-8")
        except OSError as exc:
            typer.echo(f"Error reading transcript: {exc}", err=True)
            raise typer.Exit(code=2) from exc

        if not raw_text.strip():
            typer.echo("Error: transcript is empty", err=True)
            raise typer.Exit(code=2)

        config = load_config()
        base_params = dict(config.params)
        # Allow CLI overrides for core LLM knobs
        base_params.update(
            {
                "max_tokens": str(max_tokens),
                "temperature": str(temperature),
                "gpu_layers": str(gpu_layers),
                "context_length": str(context_length),
            }
        )

        refiner_config = build_refiner_config(
            enabled=True,
            model=model or DEFAULT_CANARY_MODEL,
            base_params=base_params,
            max_tokens=max_tokens,
            temperature=temperature,
            gpu_layers=gpu_layers,
            context_length=context_length,
        )

        try:
            refiner = build_refiner(refiner_config)
        except (DependencyError, ConfigurationError, RuntimeError, ValueError) as exc:
            typer.echo(f"Refiner initialization error: {exc}", err=True)
            raise typer.Exit(code=3) from exc

        # Use mode if no custom instructions provided
        effective_mode = mode or "grammar_only"
        refined = refiner.refine(raw_text, instructions) if instructions else refiner.refine(raw_text, _get_prompt_for_mode(effective_mode))

        if output:
            output.write_text(refined, encoding="utf-8")
            typer.echo(f"✓ Refined transcript written to {output}")
        else:
            typer.echo(refined)

    refine_cmd.dev_only = True  # type: ignore[attr-defined]

def _get_prompt_for_mode(mode: str) -> str | None:
    """Resolve prompt template for mode."""
    from vociferous.refinement import PROMPT_TEMPLATES
    return PROMPT_TEMPLATES.get(mode)
