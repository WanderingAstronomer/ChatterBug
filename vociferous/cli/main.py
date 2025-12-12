from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Annotated

from vociferous.app import configure_logging, transcribe_file_workflow
from vociferous.app.progress import TranscriptionProgress
from vociferous.app.sinks import RefiningSink
from vociferous.cli.commands import (
    register_batch,
    register_bench,
    register_condense,
    register_daemon,
    register_decode,
    register_deps,
    register_record,
    register_refine,
    register_vad,
)
from vociferous.cli.helpers import build_sink, build_transcribe_configs_from_cli
from vociferous.config import get_segmentation_profile, load_config
from vociferous.config.languages import WHISPER_LANGUAGES
from vociferous.domain.exceptions import (
    AudioDecodeError,
    ConfigurationError,
    DependencyError,
    EngineError,
)
from vociferous.domain.model import EngineKind, EngineProfile
from vociferous.refinement.factory import build_refiner
from vociferous.sources import FileSource

try:
    import click
    import typer
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.theme import Theme
    from typer.core import TyperGroup
except ImportError as exc:  # pragma: no cover - tooling dependency guard
    raise DependencyError("typer and rich are required for the CLI") from exc


configure_logging()



# Custom theme with bright, readable colors
console = Console(
    theme=Theme({
        "option": "bright_cyan",
        "switch": "bright_green",
        "metavar": "bright_yellow",
        "metavar_sep": "white",
        "usage": "bold white",
    })
)


# Custom help colors for Click/Typer
class ColorHelpFormatter(click.HelpFormatter):
    """Help formatter with bright colors instead of dim grey."""

    def write_usage(self, prog: str, args: str = "", prefix: str | None = "Usage: ") -> None:
        colorized_prefix = click.style(prefix or "", fg="bright_yellow", bold=True)
        colorized_prog = click.style(prog, fg="bright_white", bold=True)
        self.write(f"{colorized_prefix}{colorized_prog} {args}\n")

    def write_heading(self, heading: str) -> None:
        self.write(f"\n{click.style(heading, fg='bright_yellow', bold=True)}\n")

    def write_text(self, text: str) -> None:
        # Make description text bright white instead of dim
        self.write(f"{click.style(text, fg='bright_white')}\n")


class BrightTyperGroup(TyperGroup):
    """TyperGroup with bright help colors and hidden help option display."""

    def format_options(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Format options, but skip the Options section if it only contains --help."""
        opts = []
        for param in self.get_params(ctx):
            rv = param.get_help_record(ctx)
            if rv is not None:
                opts.append(rv)
        
        # Only show Options section if there are options other than just help
        if opts and not (len(opts) == 1 and opts[0][0].startswith('--help')):
            with formatter.section("Options"):
                formatter.write_dl(opts)

    def get_help(self, ctx: click.Context) -> str:
        formatter = ColorHelpFormatter()
        self.format_help(ctx, formatter)
        return formatter.getvalue()

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Format commands with optional developer-tier visibility."""
        # Check sys.argv since ctx.params isn't populated during help rendering
        show_dev_help = "--dev-help" in sys.argv

        commands: list[tuple[str | None, str, str]] = []
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            if cmd is None or cmd.hidden:
                continue
            # Filter developer-only commands when showing user help
            if not show_dev_help and getattr(cmd.callback, "dev_only", False):
                continue
            help_text = cmd.get_short_help_str(limit=100)
            panel = getattr(cmd.callback, "rich_help_panel", None) if cmd.callback else None
            commands.append((panel, subcommand, help_text))

        if not commands:
            return

        if show_dev_help:
            # Developer help: show all commands organized by category
            sections: list[tuple[str, list[tuple[str, str]]]] = []
            panels = (
                "Core Commands",
                "Audio Components",
                "Refinement Components",
                "Utilities",
            )
            for panel_name in panels:
                grouped = [(name, help_text) for panel, name, help_text in commands if panel == panel_name]
                if grouped:
                    sections.append((panel_name, grouped))

            other = [(name, help_text) for panel, name, help_text in commands if panel not in panels]
            if other:
                sections.append(("Other Commands", other))

            for title, entries in sections:
                with formatter.section(title):
                    for name, help_text in entries:
                        formatter.write_text(f"  {name:<15} {help_text}")
            
            formatter.write_text("\n[Developer Mode] These commands include low-level components for manual pipeline debugging.")
            formatter.write_text("Most users should use 'transcribe' instead.")
        else:
            # User help: show only user-facing commands in simple list
            # No section needed since panels are already shown by Typer's rich mode
            pass  # Rich panels handle the grouping automatically

class DevHelpAwareGroup(BrightTyperGroup):
    """Extended TyperGroup that handles --dev-help command visibility."""
    
    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        """Override command retrieval to apply dev-only hiding."""
        cmd = super().get_command(ctx, cmd_name)
        if cmd is None:
            return None
        
        # Check if we should show developer commands
        show_dev_help = "--dev-help" in sys.argv
        
        # Hide developer-only commands unless --dev-help is present
        if hasattr(cmd.callback, "dev_only") and cmd.callback.dev_only:
            if not show_dev_help:
                cmd.hidden = True
            else:
                cmd.hidden = False
        
        return cmd

app = typer.Typer(
    help="""[bold cyan]Vociferous[/bold cyan] - Local-first speech transcription.
No cloud. No telemetry. Local engines only.
""",
    epilog="[dim]For developer tools (decode, vad, condense, record), use: vociferous --dev-help[/dim]",
    cls=DevHelpAwareGroup,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=False,
    invoke_without_command=True,
    add_completion=False,  # Hide completion commands
)
cli_app = app  # alias for embedding

# ============================================================================
# COMMAND REGISTRATION
# ============================================================================
# This section registers all CLI commands. Commands are organized into two tiers
# for the planned two-tier help system (see ARCHITECTURE.md):
#
# USER TIER (--help):
#   - High-level workflows: transcribe
#   - Utilities: languages, check
#   - Commands 90% of users need for everyday transcription
#
# DEVELOPER TIER (--dev-help):
#   - All user-tier commands PLUS:
#   - Low-level audio components: decode, vad, condense, record
#   - Manual pipeline debugging tools
#
# CATEGORIZATION CRITERIA:
#   - If users need to understand internal pipeline → Developer tier
#   - If users just want results without internals → User tier
#
# CURRENT STATUS (December 2025):
#   - Commands use rich_help_panel for visual grouping
#   - "Core Commands" = user-facing workflows
#   - "Utilities" = user-facing helpers
#   - "Audio Components" = developer-facing low-level tools
#
# FUTURE IMPLEMENTATION (Issue #15):
#   - Add --dev-help flag handling
#   - Use `hidden=True` on developer commands for default help
#   - Filter visible commands based on help flag
# ============================================================================

# Developer-tier: Audio processing components (manual pipeline debugging)
register_decode(app)        # rich_help_panel="Audio Components"
register_vad(app)           # rich_help_panel="Audio Components"
register_condense(app)      # rich_help_panel="Audio Components"
register_record(app)        # rich_help_panel="Audio Components"
register_refine(app)        # rich_help_panel="Refinement Components"

# Utility commands (available to all users)
register_deps(app)          # rich_help_panel="Utilities"
register_bench(app)         # rich_help_panel="Utilities"
register_daemon(app)        # rich_help_panel="Performance"
register_batch(app)         # rich_help_panel="Batch Processing"

# User-tier commands are defined below: transcribe, languages, check



@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    dev_help: bool = typer.Option(
        False,
        "--dev-help",
        help="Show developer commands and components",
        is_flag=True,
    ),
) -> None:
    """Show a clean welcome panel when no subcommand is provided."""
    # Command visibility is handled by DevHelpAwareGroup.get_command()
    # This callback only handles showing help or welcome when no subcommand given
    
    if dev_help and ctx.invoked_subcommand is None:
        # Show help with developer commands visible
        console.print(ctx.command.get_help(ctx))
        raise typer.Exit(code=0)

    if ctx.invoked_subcommand is not None:
        return

    welcome = Panel(
        "[bold cyan]Vociferous[/bold cyan]\n"
        "Local-first speech transcription\n"
        "No cloud. No telemetry."
        "\n\n"
        "[bold]Quick start[/bold]\n"
        "  - vociferous transcribe audio.mp3\n"
        "  - vociferous transcribe audio.wav -o transcript.txt\n"
        "  - vociferous languages\n"
        "  - vociferous check\n"
        "\n"
        "[bold]Get help[/bold]\n"
        "  - vociferous --help         (user commands)\n"
        "  - vociferous --dev-help     (all commands)\n"
        "  - vociferous transcribe --help",
        border_style="cyan",
        title="Vociferous",
    )
    console.print(welcome)
    console.print("[dim]Tip: Use 'vociferous --help' for user commands or '--dev-help' for developer tools.[/dim]")
    raise typer.Exit(code=0)


# ============================================================================
# USER-TIER COMMANDS
# ============================================================================
# These commands appear in both --help and --dev-help.
# They represent the primary user-facing interface.
# ============================================================================

@app.command(rich_help_panel="Core Commands")
def transcribe(
    file: Annotated[Path, typer.Argument(..., metavar="FILE", help="Audio file to transcribe")],
    engine: Annotated[
        EngineKind,
        typer.Option(
            "canary_qwen",
            "--engine",
            "-e",
            rich_help_panel="Core Options",
            help=(
                "Transcription engine to use. "
                "'canary_qwen' (GPU-optimized, default) or 'whisper_turbo' (CPU-friendly fallback)."
            ),
        ),
    ] = "canary_qwen",
    language: Annotated[
        str,
        typer.Option(
            "en",
            "--language",
            "-l",
            rich_help_panel="Core Options",
            help="Language code (ISO 639-1, e.g., 'en', 'es', 'fr') or 'auto' for detection.",
        ),
    ] = "en",
    output: Annotated[
        Path | None,
        typer.Option(
            None,
            "--output",
            "-o",
            metavar="PATH",
            rich_help_panel="Core Options",
            help="Save transcript to file (default: stdout)",
        ),
    ] = None,
    keep_intermediates: Annotated[
        bool | None,
        typer.Option(
            None,
            "--keep-intermediates/--no-keep-intermediates",
            help="Keep decoded/vad/condensed files (default follows config).",
            rich_help_panel="Core Options",
            show_default=False,
        ),
    ] = None,
    refine: Annotated[
        bool | None,
        typer.Option(
            None,
            "--refine/--no-refine",
            help="Enable or disable second-pass refinement when the engine supports it.",
            show_default=False,
            rich_help_panel="Core Options",
        ),
    ] = None,
    refine_instructions: Annotated[
        str | None,
        typer.Option(
            None,
            "--refine-instructions",
            help="Custom refinement instructions (engines that support dual-pass).",
            show_default=False,
            rich_help_panel="Core Options",
        ),
    ] = None,
) -> None:
    """Transcribe an audio file to text using local ASR engines.

    ENGINES:
        canary_qwen   - GPU-optimized dual-mode ASR + refinement (default, requires CUDA)
        whisper_turbo - CPU-friendly fallback (official OpenAI Whisper, works without GPU)

    EXAMPLES:
      vociferous transcribe meeting.wav
      vociferous transcribe podcast.mp3 -e whisper_turbo -o podcast.txt
      vociferous transcribe recording.wav -l es --refine "Fix grammar and add punctuation"

    ADVANCED:
    Edit ~/.config/vociferous/config.toml for:
        - Model selection, device (CPU/GPU), compute precision
        - Refinement settings (Canary-Qwen LLM mode)
        - Toggle refinement per run with --refine / --no-refine
        
    SEE ALSO:
      vociferous languages  - List supported language codes
      vociferous check      - Verify system prerequisites
    """
    logging.basicConfig(level=logging.INFO)
    config = load_config()
    
    # Build all configs from user-facing CLI options + config file
    bundle = build_transcribe_configs_from_cli(
        app_config=config,
        engine=engine,
        language=language,
        refine=refine,
    )

    # Resolve intermediate retention (CLI overrides config artifact cleanup setting)
    keep_intermediates_choice = (
        keep_intermediates
        if keep_intermediates is not None
        else not config.artifacts.cleanup_intermediates
    )
    
    # Apply numexpr thread limit if configured
    if bundle.numexpr_threads is not None:
        import os
        os.environ["NUMEXPR_MAX_THREADS"] = str(bundle.numexpr_threads)

    # Derive refinement preference
    # CLI --refine/--no-refine overrides engine default (Canary-Qwen supports refinement by default)
    refine_enabled = refine if refine is not None else (engine == "canary_qwen")

    # Build engine profile and optional refiner
    # NOTE: We DON'T load the engine here anymore - EngineWorker handles lazy loading
    # and will use the daemon if available
    refiner = None
    engine_profile = EngineProfile(engine, bundle.engine_config, bundle.options)
    try:
        if bundle.refiner_config.enabled:
            refiner = build_refiner(bundle.refiner_config)
    except ConfigurationError as exc:
        typer.echo(f"Refiner error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    # Build output sink
    sink = build_sink(output=output)
    if refiner is not None:
        sink = RefiningSink(sink, refiner)

    # Validate file exists before showing banner
    if not file.exists():
        console.print(Panel(f"[red]File not found: {file}[/red]", title="File Not Found", border_style="red"))
        raise typer.Exit(code=2)

    if file.is_dir():
        console.print(
            Panel(
                f"[red]{file} is a directory, not an audio file.\n"
                f"Example: vociferous transcribe {file / 'your_audio_file.wav'}",
                title="Directory, Not File",
                border_style="red",
            )
        )
        raise typer.Exit(code=2)

    if output is not None and output.is_dir():
        console.print(
            Panel(
                f"[red]{output} is a directory. Provide a filename (e.g., {output / 'transcript.txt'}).",
                title="Invalid Output",
                border_style="yellow",
            )
        )
        raise typer.Exit(code=2)

    segmentation_profile = get_segmentation_profile(config)

    # Check for first-run setup (only for Canary-Qwen which requires model download)
    if engine == "canary_qwen":
        try:
            from vociferous.setup import FirstRunManager, is_first_run
            if is_first_run():
                manager = FirstRunManager()
                manager.run_first_time_setup()
        except Exception as exc:
            # Don't block transcription if setup check fails
            console.print(f"[dim]Setup check skipped: {exc}[/dim]")

    # Pretty startup banner
    file_size_mb = file.stat().st_size / (1024 * 1024)
    banner = Panel(
        f"[cyan]File:[/cyan] {file.name}\n"
        f"[cyan]Size:[/cyan] {file_size_mb:.2f} MB\n"
        f"[cyan]Engine:[/cyan] [yellow]{engine}[/yellow]\n"
        f"[cyan]Language:[/cyan] {language}",
        title="[bold green]Starting Transcription[/bold green]",
        border_style="green",
    )
    console.print(banner)

    # Create progress tracker for live feedback
    progress = TranscriptionProgress(verbose=True)

    try:
        with progress:
            result = transcribe_file_workflow(
                FileSource(file),
                engine_profile,
                segmentation_profile,
                refine=refine_enabled,
                refine_instructions=refine_instructions if refine_enabled else None,
                keep_intermediates=keep_intermediates_choice,
                artifact_config=config.artifacts,
                progress=progress,
            )
        for segment in result.segments:
            sink.handle_segment(segment)
        sink.complete(result)

        if result.warnings:
            for warning in result.warnings:
                console.print(Panel(f"[yellow]{warning}[/yellow]", title="Warning", border_style="yellow"))
    except FileNotFoundError as exc:
        console.print(Panel(f"[red]{exc}[/red]", title="File Not Found", border_style="red"))
        raise typer.Exit(code=2) from exc
    except EngineError as exc:
        console.print(Panel(f"[red]{exc}[/red]", title="Engine Error", border_style="red"))
        raise typer.Exit(code=4) from exc
    except (AudioDecodeError, ConfigurationError, ValueError) as exc:
        console.print(Panel(f"[red]{exc}[/red]", title="Configuration Error", border_style="red"))
        raise typer.Exit(code=2) from exc
    except Exception as exc:  # pragma: no cover - safety net
        console.print(Panel(f"[red]{exc}[/red]", title="Unexpected Error", border_style="red"))
        raise typer.Exit(code=1) from exc


@app.command(rich_help_panel="Utilities")
def check() -> None:
    """[bold cyan]Verify system prerequisites[/bold cyan] before transcribing.

        Checks for:
            - [cyan]ffmpeg[/cyan] - Audio decoding (install: apt install ffmpeg)
            - [cyan]sounddevice[/cyan] - Microphone capture (install: pip install sounddevice)
            - [cyan]Model cache[/cyan] - Storage location for downloaded models

    [white]Run this after installing Vociferous to ensure everything works.[/white]
    """
    import importlib.util

    table = Table(title="System Check", show_header=True, header_style="bold cyan")
    table.add_column("Component", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Details", style="dim")

    ok = True
    sounddevice_warn = False
    force_missing_sounddevice = os.environ.get("VOCIFEROUS_FORCE_MISSING_SOUNDDEVICE", "0") == "1"

    # Check ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        table.add_row("ffmpeg", "[green]OK[/green]", ffmpeg_path)
    else:
        table.add_row("ffmpeg", "[red]FAIL[/red]", "Not found on PATH")
        ok = False

    # Check sounddevice
    if (importlib.util.find_spec("sounddevice") is not None) and not force_missing_sounddevice:
        table.add_row("sounddevice", "[green]OK[/green]", "Installed")
    else:
        table.add_row("sounddevice", "[yellow]WARN[/yellow]", "Not installed (mic capture disabled)")
        sounddevice_warn = True

    # Check model cache
    cfg = load_config()
    cache_path = Path(cfg.model_cache_dir) if cfg.model_cache_dir else None
    models_missing = False
    if cache_path and cache_path.exists():
        table.add_row("Model cache", "[green]OK[/green]", str(cache_path))
        
        # Check if default engine model is fully downloaded
        canary_model_path = cache_path / "models--nvidia--canary-qwen-2.5b"
        if canary_model_path.exists():
            # Check for essential files in snapshots (model weights, preprocessor config, etc.)
            snapshots = list(canary_model_path.glob("snapshots/*/"))
            if snapshots:
                snapshot_dir = snapshots[0]
                # Check for key files that indicate complete download
                has_preprocessor = (snapshot_dir / "preprocessor_config.json").exists()
                has_model = any(snapshot_dir.glob("*.safetensors")) or any(snapshot_dir.glob("*.bin"))
                
                if has_preprocessor and has_model:
                    table.add_row("Canary-Qwen", "[green]OK[/green]", "Model downloaded")
                else:
                    table.add_row("Canary-Qwen", "[yellow]INCOMPLETE[/yellow]", "Partial download detected")
                    models_missing = True
            else:
                table.add_row("Canary-Qwen", "[yellow]MISSING[/yellow]", "Model not downloaded")
                models_missing = True
        else:
            table.add_row("Canary-Qwen", "[yellow]MISSING[/yellow]", "Model not downloaded")
            models_missing = True
    elif cache_path:
        table.add_row("Model cache", "[yellow]WARN[/yellow]", f"{cache_path} (will be created)")
        table.add_row("Canary-Qwen", "[yellow]MISSING[/yellow]", "Model not downloaded")
        models_missing = True
    else:
        table.add_row("Model cache", "[dim]N/A[/dim]", "Not configured")
        models_missing = True

    console.print(table)

    if ok and not models_missing:
        console.print("\n[bold green]All checks passed! Ready to transcribe.[/bold green]")
        if sounddevice_warn:
            console.print("[yellow]Note: sounddevice not installed; microphone capture disabled.[/yellow]")
    elif ok:
        console.print("\n[bold yellow]Core checks passed, but models need downloading.[/bold yellow]")
        console.print("[yellow]Run 'vociferous transcribe <file>' to auto-download models on first use.[/yellow]")
        if sounddevice_warn:
            console.print("[yellow]Note: sounddevice not installed; microphone capture disabled.[/yellow]")
    else:
        console.print("\n[bold red]Some prerequisites missing. Install them for full functionality.[/bold red]")
        if sounddevice_warn:
            console.print("[yellow]Note: sounddevice not installed; microphone capture disabled.[/yellow]")
        raise typer.Exit(code=1)


@app.command(rich_help_panel="Utilities")
def languages() -> None:
    """[bold cyan]List supported language codes[/bold cyan] by engine.

    Language support varies by ASR engine:
    - [yellow]Canary-Qwen[/yellow] (GPU-optimized): English only
    - [yellow]Whisper Turbo[/yellow] (CPU-friendly): 99 languages (multilingual + translation)

    Use language codes with the [cyan]--language[/cyan] or [cyan]-l[/cyan] flag.
    
    [bold]Examples:[/bold]
      vociferous transcribe audio.wav -e whisper_turbo -l es      Spanish (Whisper only)
      vociferous transcribe english.wav                            English (default, works with both)
    """
    from vociferous.config.languages import CANARY_SUPPORTED_LANGUAGES
    
    console.print("\n[bold yellow]Engine Language Support[/bold yellow]\n")
    
    # Canary section
    console.print("[bold cyan]Canary-Qwen 2.5B[/bold cyan] (GPU-optimized, requires CUDA)")
    console.print(f"  Supported: {', '.join(CANARY_SUPPORTED_LANGUAGES)}\n")
    
    # Whisper section with table
    console.print("[bold cyan]Whisper Turbo[/bold cyan] (CPU-friendly, official OpenAI Whisper)")
    console.print(f"  Total supported: {len(WHISPER_LANGUAGES)} languages\n")
    
    table = Table(title="Whisper Turbo Supported Languages", 
                  show_header=True, header_style="bold cyan",
                  title_style="bold yellow")
    table.add_column("Code", style="cyan", width=6)
    table.add_column("Language", style="white")
    table.add_column("Code", style="cyan", width=6)
    table.add_column("Language", style="white")
    table.add_column("Code", style="cyan", width=6)
    table.add_column("Language", style="white")
    
    # Split languages into 3 columns for compact display
    sorted_langs = sorted(WHISPER_LANGUAGES.items())
    chunk_size = (len(sorted_langs) + 2) // 3  # Calculate chunk size for 3-column layout
    
    for i in range(chunk_size):
        row = []
        for col in range(3):
            idx = i + col * chunk_size
            if idx < len(sorted_langs):
                code, name = sorted_langs[idx]
                row.extend([code, name])
            else:
                row.extend(["", ""])
        table.add_row(*row)
    
    console.print()
    console.print(table)
    console.print(f"\n[dim]Total: {len(WHISPER_LANGUAGES)} languages[/dim]")
    
    # Usage examples
    console.print()
    console.print(Panel(
        "[bold]Usage:[/bold]\n"
        "  vociferous transcribe audio.wav --language [cyan]<code>[/cyan]\n"
        "  vociferous transcribe audio.mp3 [cyan]-l es[/cyan]  (Spanish)\n"
        "  vociferous transcribe audio.flac [cyan]-l auto[/cyan]  (Auto-detect)\n\n"
        "[bold]Tip:[/bold] Use 'auto' to automatically detect the language.",
        title="How to Use",
        border_style="green",
    ))


def main() -> None:
    """CLI entrypoint for Vociferous with rich error handling."""
    from vociferous.domain.exceptions import VociferousError

    try:
        app()
    except KeyboardInterrupt as exc:
        console.print("\n⚠️  Operation cancelled by user", style="yellow")
        raise typer.Exit(code=130) from exc
    except VociferousError as e:
        # Rich formatted error with context and suggestions
        console.print(e.format_rich())
        raise typer.Exit(code=1) from e
    except Exception as exc:
        # Unexpected error - show full traceback in verbose mode
        if os.getenv("VOCIFEROUS_VERBOSE") or os.getenv("VOCIFEROUS_DEBUG"):
            console.print_exception()
        else:
            console.print(f"[red]✗ Unexpected error: {exc}[/red]")
            console.print("[dim]Run with VOCIFEROUS_VERBOSE=1 for full traceback[/dim]")
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    main()
