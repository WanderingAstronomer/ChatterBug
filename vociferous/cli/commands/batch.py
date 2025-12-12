"""CLI command for batch transcription.

Provides a command for transcribing multiple audio files at once,
with parallel processing, error handling, and combined output options.

Usage:
    vociferous batch *.mp3
    vociferous batch *.wav --output-dir transcripts/
    vociferous batch podcast_ep*.mp3 --combined --parallel 3
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

console = Console()


def register_batch(app: typer.Typer) -> None:
    """Register the batch command."""

    @app.command("batch")
    def batch_cmd(
        files: Annotated[
            list[Path],
            typer.Argument(
                ...,
                help="Audio files to transcribe (supports globs like *.mp3)",
            ),
        ],
        output_dir: Annotated[
            Path | None,
            typer.Option(
                "--output-dir",
                "-o",
                help="Output directory for transcripts (default: ./transcripts)",
            ),
        ] = None,
        combined: Annotated[
            bool,
            typer.Option(
                "--combined",
                "-c",
                help="Generate a combined transcript from all files",
            ),
        ] = False,
        continue_on_error: Annotated[
            bool,
            typer.Option(
                "--continue-on-error/--stop-on-error",
                help="Continue processing if a file fails",
            ),
        ] = True,
        daemon: Annotated[
            str,
            typer.Option(
                "--daemon",
                "-d",
                help="Daemon mode: 'always' (start if needed), 'auto' (use if running), 'never'",
            ),
        ] = "always",
        parallel: Annotated[
            int,
            typer.Option(
                "--parallel",
                "-j",
                help="Number of parallel transcriptions (use with daemon)",
            ),
        ] = 1,
        preprocess: Annotated[
            str,
            typer.Option(
                "--preprocess",
                "-p",
                help="Preprocessing preset: none, basic, clean, phone, podcast",
            ),
        ] = "none",
        refine: Annotated[
            bool,
            typer.Option(
                "--refine/--no-refine",
                help="Apply transcript refinement",
            ),
        ] = True,
        verbose: Annotated[
            bool,
            typer.Option(
                "--verbose/--quiet",
                help="Show progress output",
            ),
        ] = True,
    ) -> None:
        """Transcribe multiple audio files in batch.

        Supports parallel processing and can generate combined transcripts.

        Examples:

            # Transcribe all MP3 files in current directory
            vociferous batch *.mp3

            # With preprocessing
            vociferous batch *.wav --preprocess clean

            # Generate combined transcript
            vociferous batch podcast_ep*.mp3 --combined --output-dir transcripts/

            # Parallel processing (requires daemon)
            vociferous batch *.mp3 --parallel 3
        """
        from vociferous.app.batch import (
            BatchTranscriptionRunner,
            compute_batch_stats,
            generate_combined_transcript,
        )
        from vociferous.app.progress import NullProgressTracker, RichProgressTracker

        # Expand globs and validate files
        valid_files: list[Path] = []
        invalid_files: list[Path] = []

        for file_pattern in files:
            # Handle glob patterns
            pattern_str = str(file_pattern)
            if '*' in pattern_str or '?' in pattern_str:
                matches = list(Path.cwd().glob(pattern_str))
                if matches:
                    valid_files.extend(p for p in matches if p.is_file())
                else:
                    console.print(f"⚠️  No files match pattern: {pattern_str}", style="yellow")
            elif file_pattern.exists() and file_pattern.is_file():
                valid_files.append(file_pattern)
            else:
                invalid_files.append(file_pattern)

        if invalid_files:
            console.print(f"⚠️  Skipping {len(invalid_files)} non-existent files", style="yellow")
            for f in invalid_files[:5]:
                console.print(f"   - {f}")
            if len(invalid_files) > 5:
                console.print(f"   ... and {len(invalid_files) - 5} more")

        if not valid_files:
            console.print("✗ No valid files to transcribe", style="red")
            raise typer.Exit(1)

        # Remove duplicates while preserving order
        seen = set()
        unique_files = []
        for f in valid_files:
            resolved = f.resolve()
            if resolved not in seen:
                seen.add(resolved)
                unique_files.append(f)
        valid_files = unique_files

        # Setup output directory
        if output_dir is None:
            output_dir = Path.cwd() / "transcripts"
        output_dir.mkdir(parents=True, exist_ok=True)

        console.print("\n[bold]Batch Transcription[/bold]")
        console.print(f"  Files: {len(valid_files)}")
        console.print(f"  Output: {output_dir}")
        if parallel > 1:
            console.print(f"  Workers: {parallel}")
        console.print()

        # Create progress tracker
        progress = RichProgressTracker(verbose=verbose) if verbose else NullProgressTracker()

        # Create and run batch processor
        runner = BatchTranscriptionRunner(
            files=valid_files,
            output_dir=output_dir,
            daemon_mode=daemon,
            parallel=parallel,
            continue_on_error=continue_on_error,
            preprocess=preprocess if preprocess != "none" else None,
            refine=refine,
        )

        with progress:
            results = runner.run(progress=progress)

        # Compute stats
        stats = compute_batch_stats(results)

        # Print summary table
        console.print()
        console.print("=" * 60)
        
        table = Table(title="Batch Transcription Results", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Total files", str(stats.total_files))
        table.add_row("Successful", f"[green]{stats.successful}[/green]")
        if stats.failed > 0:
            table.add_row("Failed", f"[red]{stats.failed}[/red]")
        table.add_row("Duration", f"{stats.total_duration_s:.1f}s")
        table.add_row("Output directory", str(output_dir))
        
        console.print(table)

        # Generate combined transcript if requested
        if combined and stats.successful > 0:
            combined_path = output_dir / "combined_transcript.txt"
            generate_combined_transcript(results, combined_path)
            console.print(f"\n✓ Combined transcript: {combined_path}", style="green")

        # List failed files
        failed = [r for r in results if not r.success]
        if failed:
            console.print("\n[bold red]Failed files:[/bold red]")
            for r in failed:
                error_msg = str(r.error)[:100] if r.error else "Unknown error"
                console.print(f"  ✗ {r.source_file.name}: {error_msg}")

        console.print()

        if stats.failed > 0 and not continue_on_error:
            raise typer.Exit(1)
