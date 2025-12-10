from __future__ import annotations

from pathlib import Path
import logging
import shutil

from vociferous.app import TranscriptionSession, configure_logging
from vociferous.app.sinks import PolishingSink
from vociferous.sources import FileSource
from vociferous.config import load_config
from vociferous.config.languages import WHISPER_LANGUAGES, VOXTRAL_CORE_LANGUAGES
from vociferous.domain.model import TranscriptionPreset, EngineKind
from vociferous.domain.exceptions import (
    DependencyError, EngineError, AudioDecodeError, ConfigurationError
)
from vociferous.engines.factory import build_engine
from vociferous.polish.factory import build_polisher
from vociferous.cli.helpers import build_audio_source, build_sink, build_transcribe_configs_from_cli
from vociferous.cli.commands import (
    register_decode,
    register_vad,
    register_condense,
    register_record,
    register_transcribe_full,
    register_transcribe_canary,
)

try:
    import typer
    from typer.core import TyperGroup
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.theme import Theme
    import click
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

app = typer.Typer(
    help="""[bold cyan]Vociferous[/bold cyan] - Local-first speech transcription.
No cloud. No telemetry. Local engines only.
""",
    cls=BrightTyperGroup,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=False,
    invoke_without_command=True,
    add_completion=False,  # Hide completion commands
)
cli_app = app  # alias for embedding
register_decode(app)
register_vad(app)
register_condense(app)
register_record(app)
register_transcribe_full(app)
register_transcribe_canary(app)


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """Show a clean welcome panel when no subcommand is provided."""
    if ctx.invoked_subcommand is not None:
        return

    welcome = Panel(
        "[bold cyan]Vociferous[/bold cyan]\n"
        "Local-first speech transcription\n"
        "No cloud. No telemetry."
        "\n\n"
        "[bold]Quick start[/bold]\n"
        "  - vociferous decode audio.mp3\n"
        "  - vociferous vad audio_decoded.wav\n"
        "  - vociferous condense audio_decoded_vad_timestamps.json audio_decoded.wav\n"
        "  - vociferous transcribe-full audio.mp3\n"
        "\n"
        "[bold]More help[/bold]\n"
        "  - vociferous transcribe --help\n"
        "  - vociferous languages\n"
        "  - vociferous check",
        border_style="cyan",
        title="Vociferous",
    )
    console.print(welcome)
    console.print("[dim]Tip: run 'vociferous --help' for the full command list.[/dim]")
    raise typer.Exit(code=0)


@app.command(rich_help_panel="Core Commands")
def transcribe(
    file: Path = typer.Argument(..., metavar="FILE", help="Audio file to transcribe"),
    engine: EngineKind = typer.Option(
        "whisper_turbo",
        "--engine",
        "-e",
        rich_help_panel="Core Options",
        help=(
            "Transcription engine to use. "
            "'whisper_turbo' is fast and accurate. "
            "'voxtral_local' uses Mistral for smart punctuation. "
            "'canary_qwen' provides a dual ASR + LLM path."
        ),
    ),
    language: str = typer.Option(
        "en",
        "--language",
        "-l",
        rich_help_panel="Core Options",
        help="Language code (ISO 639-1, e.g., 'en', 'es', 'fr') or 'auto' for detection.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        metavar="PATH",
        rich_help_panel="Core Options",
        help="Save transcript to file (default: stdout)",
    ),
    preset: TranscriptionPreset | None = typer.Option(
        None,
        "--preset",
        "-p",
        rich_help_panel="Core Options",
        help="Quality preset: 'fast' (speed), 'balanced' (default), 'high_accuracy' (best quality).",
        case_sensitive=False,
        show_default=False,
    ),
    polish: bool | None = typer.Option(
        None,
        "--polish/--no-polish",
        rich_help_panel="Core Options",
        help="Post-process final transcript text (enable to polish, disable to skip even if enabled in config).",
        show_default=False,
    ),
) -> None:
    """Transcribe an audio file to text using local ASR engines.

    ENGINES:
      whisper_turbo - Fast, accurate, works offline (default)
      voxtral_local - Smart punctuation & grammar (offline, slower)

    PRESETS:
      fast           - Speed optimized (small model, batch)
      balanced       - Quality/speed tradeoff (default)
      high_accuracy  - Quality optimized (large model, beam search)

    EXAMPLES:
      vociferous transcribe meeting.wav
      vociferous transcribe podcast.mp3 -e voxtral_local -o podcast.txt
      vociferous transcribe recording.wav -l es --preset high_accuracy

    ADVANCED:
      Edit ~/.config/vociferous/config.toml for:
                - Model selection, device (CPU/GPU), compute precision
                - Batching, VAD, chunk sizes, polish settings
                                - Toggle polishing per run with --polish / --no-polish
        
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
        preset=preset,
        polish=polish,
    )
    
    # Apply numexpr thread limit if configured
    if bundle.numexpr_threads is not None:
        import os
        os.environ["NUMEXPR_MAX_THREADS"] = str(bundle.numexpr_threads)

    # Build engine and polisher
    polisher = None
    try:
        engine_adapter = build_engine(engine, bundle.engine_config)
        if bundle.polisher_config.enabled:
            polisher = build_polisher(bundle.polisher_config)
    except (DependencyError, EngineError) as exc:
        typer.echo(f"Engine initialization error: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    except ConfigurationError as exc:
        typer.echo(f"Polisher error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    # Build audio source with optional preprocessing
    source = build_audio_source(file, config)
    
    # Build output sink
    sink = build_sink(output=output)
    if polisher is not None:
        sink = PolishingSink(sink, polisher)

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

    session = TranscriptionSession()

    try:
        session.start(source, engine_adapter, sink, bundle.options, engine_kind=engine)
        session.join()
    except FileNotFoundError as exc:
        console.print(Panel(f"[red]{exc}[/red]", title="File Not Found", border_style="red"))
        raise typer.Exit(code=2) from exc
    except EngineError as exc:
        console.print(Panel(f"[red]{exc}[/red]", title="Engine Error", border_style="red"))
        raise typer.Exit(code=4) from exc
    except (AudioDecodeError, ConfigurationError) as exc:
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

    # Check ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        table.add_row("ffmpeg", "[green]OK[/green]", ffmpeg_path)
    else:
        table.add_row("ffmpeg", "[red]FAIL[/red]", "Not found on PATH")
        ok = False

    # Check sounddevice
    if importlib.util.find_spec("sounddevice") is not None:
        table.add_row("sounddevice", "[green]OK[/green]", "Installed")
    else:
        table.add_row("sounddevice", "[yellow]WARN[/yellow]", "Not installed (mic capture disabled)")
        ok = False

    # Check model cache
    cfg = load_config()
    cache_path = Path(cfg.model_cache_dir) if cfg.model_cache_dir else None
    if cache_path and cache_path.exists():
        table.add_row("Model cache", "[green]OK[/green]", str(cache_path))
    elif cache_path:
        table.add_row("Model cache", "[yellow]WARN[/yellow]", f"{cache_path} (will be created)")
    else:
        table.add_row("Model cache", "[dim]N/A[/dim]", "Not configured")

    console.print(table)

    if ok:
        console.print("\n[bold green]All checks passed! Ready to transcribe.[/bold green]")
    else:
        console.print("\n[bold red]Some prerequisites missing. Install them for full functionality.[/bold red]")
        raise typer.Exit(code=1)


@app.command(rich_help_panel="Utilities")
def languages() -> None:
    """[bold cyan]List all supported language codes[/bold cyan] for transcription.

    Shows ISO 639-1 language codes supported by Whisper and Voxtral engines.
    Use these codes with the [cyan]--language[/cyan] or [cyan]-l[/cyan] flag.
    
    [bold]Examples:[/bold]
      vociferous transcribe audio.wav -l es      Spanish
      vociferous transcribe audio.mp3 -l fr      French
      vociferous transcribe audio.flac -l ja     Japanese
    """
    # Create main table for Whisper
    table = Table(title="Whisper (CTranslate2) - All Engines", 
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
    
    # Create Voxtral table
    voxtral_table = Table(title="Voxtral (Mistral-based) - Core Languages", 
                          show_header=True, header_style="bold cyan",
                          title_style="bold magenta")
    voxtral_table.add_column("Code", style="cyan", width=6)
    voxtral_table.add_column("Language", style="white")
    
    # All Voxtral core languages are guaranteed to be in WHISPER_LANGUAGES
    for code in VOXTRAL_CORE_LANGUAGES:
        voxtral_table.add_row(code, WHISPER_LANGUAGES[code])
    
    console.print()
    console.print(voxtral_table)
    console.print("[dim]Note: Voxtral supports 30+ languages with best performance on the above.[/dim]")
    
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
    """CLI entrypoint for Vociferous."""
    try:
        app()
    except KeyboardInterrupt:
        typer.echo("\nInterrupted by user.", err=True)
        raise typer.Exit(code=130)
    except Exception as exc:
        typer.echo(f"Fatal error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    main()
