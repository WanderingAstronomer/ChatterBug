"""Benchmark command for measuring ASR pipeline performance."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from vociferous.app.workflow import EngineWorker, transcribe_file_workflow
from vociferous.audio.utilities import get_audio_duration
from vociferous.config import get_engine_profile, get_segmentation_profile, load_config
from vociferous.domain.exceptions import ConfigurationError, DependencyError, EngineError
from vociferous.engines.factory import build_engine
from vociferous.sources import FileSource

console = Console()


def register_bench(app: typer.Typer) -> None:
    @app.command("bench", rich_help_panel="Utilities")
    def bench_cmd(
        corpus: Annotated[
            Path,
            typer.Argument(
                ...,
                help="Directory containing audio files to benchmark",
                metavar="CORPUS",
            ),
        ],
        engine_profile: Annotated[
            str,
            typer.Option(
                "canary_qwen_fp16",
                "--engine-profile",
                help="Engine profile name from config",
            ),
        ] = "canary_qwen_fp16",
        segmentation_profile: Annotated[
            str,
            typer.Option(
                "default",
                "--segmentation-profile",
                help="Segmentation profile name from config",
            ),
        ] = "default",
        pattern: Annotated[
            str,
            typer.Option(
                "*.wav",
                "--pattern",
                help="File pattern to match (e.g., '*.wav', '*.mp3', '*')",
            ),
        ] = "*.wav",
        refine: Annotated[
            bool,
            typer.Option(
                False,
                "--refine",
                help="Enable refinement pass (increases processing time)",
            ),
        ] = False,
        reference_dir: Annotated[
            Path | None,
            typer.Option(
                None,
                "--reference-dir",
                help="Directory with reference transcripts for WER calculation (not yet implemented)",
            ),
        ] = None,
    ) -> None:
        """Benchmark transcription pipeline performance.

        Measures Real-Time Factor (RTF) and throughput across a corpus of audio files.
        Lower RTF is better (e.g., RTF=0.1 means 10x faster than realtime).

        METRICS:
            RTF (Real-Time Factor) - wall_clock_time / audio_duration
            Throughput            - total_audio_seconds / wall_clock_time

        EXAMPLES:
            # Basic benchmark with Canary FP16
            vociferous bench ./test_corpus/

            # Benchmark with custom profiles
            vociferous bench ./corpus/ \\
              --engine-profile canary_qwen_bf16 \\
              --segmentation-profile aggressive

            # Benchmark with refinement enabled
            vociferous bench ./corpus/ --refine

            # Benchmark MP3 files only
            vociferous bench ./corpus/ --pattern "*.mp3"
        """
        if not corpus.exists():
            typer.echo(f"Error: Corpus directory not found: {corpus}", err=True)
            raise typer.Exit(code=2)

        if not corpus.is_dir():
            typer.echo(f"Error: {corpus} is not a directory", err=True)
            raise typer.Exit(code=2)

        # Find all matching audio files
        audio_files = sorted(corpus.glob(pattern))
        if not audio_files:
            typer.echo(f"Error: No files matching pattern '{pattern}' in {corpus}", err=True)
            raise typer.Exit(code=2)

        console.print(f"[cyan]Found {len(audio_files)} audio files matching '{pattern}'[/cyan]")

        # Load config and profiles
        config = load_config()
        try:
            seg_profile = get_segmentation_profile(config, segmentation_profile)
        except KeyError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=2) from exc

        try:
            eng_profile_obj = get_engine_profile(config, engine_profile)
        except KeyError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=2) from exc

        # Build engine once
        console.print(f"[yellow]Loading engine '{engine_profile}'...[/yellow]")
        try:
            engine = build_engine(eng_profile_obj.kind, eng_profile_obj.config)
            worker = EngineWorker(eng_profile_obj, engine=engine)
        except (DependencyError, EngineError, ConfigurationError) as exc:
            typer.echo(f"Engine initialization error: {exc}", err=True)
            raise typer.Exit(code=3) from exc

        console.print("[green]✓ Engine loaded[/green]\n")

        # Benchmark each file
        results: list[tuple[Path, float, float, float]] = []  # (file, duration, wall_time, rtf)
        total_audio_duration = 0.0
        total_wall_time = 0.0

        for i, audio_file in enumerate(audio_files, 1):
            console.print(f"[cyan][{i}/{len(audio_files)}] Processing: {audio_file.name}[/cyan]")

            try:
                # Get audio duration
                duration = get_audio_duration(audio_file)
                total_audio_duration += duration

                # Time the transcription
                start_time = time.perf_counter()
                transcribe_file_workflow(
                    FileSource(audio_file),
                    eng_profile_obj,
                    seg_profile,
                    refine=refine,
                    keep_intermediates=False,
                    artifact_config=config.artifacts,
                    engine_worker=worker,
                )
                wall_time = time.perf_counter() - start_time
                total_wall_time += wall_time

                # Calculate RTF
                rtf = wall_time / duration if duration > 0 else 0.0
                results.append((audio_file, duration, wall_time, rtf))

                console.print(
                    f"  Duration: {duration:.2f}s | Wall Time: {wall_time:.2f}s | RTF: {rtf:.3f}"
                )

            except Exception as exc:
                console.print(f"  [red]Error processing {audio_file.name}: {exc}[/red]")
                continue

        # Print summary table
        console.print("\n[bold green]Benchmark Results[/bold green]\n")

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("File", style="white")
        table.add_column("Duration (s)", justify="right")
        table.add_column("Wall Time (s)", justify="right")
        table.add_column("RTF", justify="right")

        for file, duration, wall_time, rtf in results:
            rtf_color = "green" if rtf < 0.1 else "yellow" if rtf < 0.5 else "red"
            table.add_row(
                file.name,
                f"{duration:.2f}",
                f"{wall_time:.2f}",
                f"[{rtf_color}]{rtf:.3f}[/{rtf_color}]",
            )

        console.print(table)

        # Print aggregate metrics
        if total_audio_duration > 0:
            aggregate_rtf = total_wall_time / total_audio_duration
            throughput = total_audio_duration / total_wall_time if total_wall_time > 0 else 0.0

            console.print("\n[bold]Aggregate Metrics:[/bold]")
            console.print(f"  Total Audio Duration:  {total_audio_duration:.2f}s ({total_audio_duration/60:.2f} min)")
            console.print(f"  Total Wall Time:       {total_wall_time:.2f}s ({total_wall_time/60:.2f} min)")
            console.print(f"  Aggregate RTF:         {aggregate_rtf:.3f}")
            console.print(f"  Throughput:            {throughput:.1f}x realtime")

            if aggregate_rtf < 0.1:
                console.print("\n[bold green]✓ Excellent performance (>10x realtime)[/bold green]")
            elif aggregate_rtf < 0.5:
                console.print("\n[bold yellow]✓ Good performance (>2x realtime)[/bold yellow]")
            else:
                console.print("\n[bold red]⚠ Performance below realtime[/bold red]")

        if reference_dir is not None:
            console.print("\n[yellow]Note: WER calculation not yet implemented[/yellow]")

    bench_cmd.dev_only = False  # type: ignore[attr-defined]
