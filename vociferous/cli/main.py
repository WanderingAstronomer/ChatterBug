from __future__ import annotations

from pathlib import Path
import logging
import subprocess
import shutil

from vociferous.app import TranscriptionSession, configure_logging
from vociferous.audio.sources import FileSource
from vociferous.app.sinks import PolishingSink
from vociferous.config import load_config
from vociferous.domain.model import TranscriptionPreset, EngineKind
from vociferous.domain.exceptions import (
    DependencyError, EngineError, AudioDecodeError, ConfigurationError
)
from vociferous.engines.factory import build_engine
from vociferous.polish.factory import build_polisher
from vociferous.cli.helpers import build_sink, build_transcribe_configs_from_cli

try:
    import typer
    from typer.core import TyperGroup
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    from rich.theme import Theme
    import click
except ImportError as exc:  # pragma: no cover - tooling dependency guard
    raise DependencyError("typer and rich are required for the CLI") from exc


configure_logging()

# Language support constants (ISO 639-1 codes)
WHISPER_LANGUAGES = {
    "af": "Afrikaans", "am": "Amharic", "ar": "Arabic", "as": "Assamese",
    "az": "Azerbaijani", "ba": "Bashkir", "be": "Belarusian", "bg": "Bulgarian",
    "bn": "Bengali", "bo": "Tibetan", "br": "Breton", "bs": "Bosnian",
    "ca": "Catalan", "cs": "Czech", "cy": "Welsh", "da": "Danish",
    "de": "German", "el": "Greek", "en": "English", "es": "Spanish",
    "et": "Estonian", "eu": "Basque", "fa": "Persian", "fi": "Finnish",
    "fo": "Faroese", "fr": "French", "gl": "Galician", "gu": "Gujarati",
    "ha": "Hausa", "haw": "Hawaiian", "he": "Hebrew", "hi": "Hindi",
    "hr": "Croatian", "ht": "Haitian Creole", "hu": "Hungarian", "hy": "Armenian",
    "id": "Indonesian", "is": "Icelandic", "it": "Italian", "ja": "Japanese",
    "jw": "Javanese", "ka": "Georgian", "kk": "Kazakh", "km": "Khmer",
    "kn": "Kannada", "ko": "Korean", "la": "Latin", "lb": "Luxembourgish",
    "ln": "Lingala", "lo": "Lao", "lt": "Lithuanian", "lv": "Latvian",
    "mg": "Malagasy", "mi": "Maori", "mk": "Macedonian", "ml": "Malayalam",
    "mn": "Mongolian", "mr": "Marathi", "ms": "Malay", "mt": "Maltese",
    "my": "Myanmar", "ne": "Nepali", "nl": "Dutch", "nn": "Norwegian Nynorsk",
    "no": "Norwegian", "oc": "Occitan", "pa": "Punjabi", "pl": "Polish",
    "ps": "Pashto", "pt": "Portuguese", "ro": "Romanian", "ru": "Russian",
    "sa": "Sanskrit", "sd": "Sindhi", "si": "Sinhala", "sk": "Slovak",
    "sl": "Slovenian", "sn": "Shona", "so": "Somali", "sq": "Albanian",
    "sr": "Serbian", "su": "Sundanese", "sv": "Swedish", "sw": "Swahili",
    "ta": "Tamil", "te": "Telugu", "tg": "Tajik", "th": "Thai",
    "tk": "Turkmen", "tl": "Tagalog", "tr": "Turkish", "tt": "Tatar",
    "uk": "Ukrainian", "ur": "Urdu", "uz": "Uzbek", "vi": "Vietnamese",
    "yi": "Yiddish", "yo": "Yoruba", "zh": "Chinese", "yue": "Cantonese",
}

# Voxtral core languages with best performance (subset of Whisper languages)
VOXTRAL_CORE_LANGUAGES = ["en", "es", "fr", "de", "it", "pt", "hi", "nl"]

# Custom theme with bright, readable colors
console = Console(theme=Theme({
    "option": "bright_cyan",
    "switch": "bright_green", 
    "metavar": "bright_yellow",
    "metavar_sep": "white",
    "usage": "bold white",
}))

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
    """TyperGroup with bright help colors."""
    def get_help(self, ctx: click.Context) -> str:
        formatter = ColorHelpFormatter()
        self.format_help(ctx, formatter)
        return formatter.getvalue()

app = typer.Typer(
    help="""[bold cyan]Vociferous[/bold cyan] — Local-first speech transcription

Transcribe audio files using Whisper or Voxtral entirely on your machine.
No cloud. No telemetry. Just your GPU/CPU.

[bold]Getting Started:[/bold]
  vociferous transcribe audio.mp3              Basic transcription
  vociferous transcribe audio.wav -e voxtral_local  Smart punctuation
  vociferous transcribe audio.flac -l es       Spanish audio
  
[bold]Learn More:[/bold]
  vociferous transcribe --help                 Transcription options
  vociferous languages                         Supported languages
  vociferous check                             Verify your system
    """,
    cls=BrightTyperGroup,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
    add_completion=False,  # Hide completion commands
)
cli_app = app  # alias for embedding


@app.command(rich_help_panel="Core Commands")
def transcribe(
    file: Path = typer.Argument(..., metavar="FILE", help="Audio file to transcribe"),
    engine: EngineKind = typer.Option(
        "whisper_turbo",
        "--engine",
        "-e",
        rich_help_panel="Core Options",
        help="Transcription engine to use. 'whisper_turbo' is fast and accurate. 'voxtral_local' uses Mistral for smart punctuation.",
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
) -> None:
    """Transcribe an audio file to text using local ASR engines.

    ENGINES:
      whisper_turbo - Fast, accurate, works offline (default)
      voxtral_local - Smart punctuation & grammar (slower)
      whisper_vllm  - Server-based (requires separate vLLM server)
      voxtral_vllm  - Server-based smart mode

    PRESETS:
      fast           - Speed optimized (small model, batch)
      balanced       - Quality/speed tradeoff (default for vLLM)
      high_accuracy  - Quality optimized (large model, beam search)

    EXAMPLES:
      vociferous transcribe meeting.wav
      vociferous transcribe podcast.mp3 -e voxtral_local -o podcast.txt
      vociferous transcribe recording.wav -l es --preset high_accuracy

    ADVANCED:
      Edit ~/.config/vociferous/config.toml for:
        • Model selection, device (CPU/GPU), compute precision
        • Batching, VAD, chunk sizes, polish settings
        
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
    )
    
    # Apply numexpr thread limit if configured
    if bundle.numexpr_threads is not None:
        import os
        os.environ["NUMEXPR_MAX_THREADS"] = str(bundle.numexpr_threads)

    # Build engine and polisher
    try:
        engine_adapter = build_engine(engine, bundle.engine_config)
        polisher = build_polisher(bundle.polisher_config)
    except (DependencyError, EngineError) as exc:
        typer.echo(f"Engine initialization error: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    except ConfigurationError as exc:
        typer.echo(f"Polisher error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    # Build audio source with default chunk settings
    source = FileSource(
        file,
        chunk_ms=config.chunk_ms,
    )
    
    # Build output sink
    sink = build_sink(output=output)
    if polisher is not None:
        sink = PolishingSink(sink, polisher)

    # Validate file exists before showing banner
    if not file.exists():
        console.print(Panel(f"[red]File not found: {file}[/red]", title="❌ File Not Found", border_style="red"))
        raise typer.Exit(code=2)

    if file.is_dir():
        console.print(
            Panel(
                f"[red]{file} is a directory, not an audio file.\n"
                f"Example: vociferous transcribe {file / 'your_audio_file.wav'}",
                title="❌ Directory, Not File",
                border_style="red",
            )
        )
        raise typer.Exit(code=2)

    if output is not None and output.is_dir():
        console.print(
            Panel(
                f"[red]{output} is a directory. Provide a filename (e.g., {output / 'transcript.txt'}).",
                title="⚠️  Invalid Output",
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
        console.print(Panel(f"[red]{exc}[/red]", title="❌ File Not Found", border_style="red"))
        raise typer.Exit(code=2) from exc
    except EngineError as exc:
        console.print(Panel(f"[red]{exc}[/red]", title="⚠️  Engine Error", border_style="red"))
        raise typer.Exit(code=4) from exc
    except (AudioDecodeError, ConfigurationError) as exc:
        console.print(Panel(f"[red]{exc}[/red]", title="⚠️  Configuration Error", border_style="red"))
        raise typer.Exit(code=2) from exc
    except Exception as exc:  # pragma: no cover - safety net
        console.print(Panel(f"[red]{exc}[/red]", title="Unexpected Error", border_style="red"))
        raise typer.Exit(code=1) from exc


@app.command(rich_help_panel="Utilities")
def check() -> None:
    """[bold blue]✅ Verify system prerequisites[/bold blue] before transcribing.

    Checks for:
      • [cyan]ffmpeg[/cyan] - Audio decoding (install: apt install ffmpeg)
      • [cyan]sounddevice[/cyan] - Microphone capture (install: pip install sounddevice)
      • [cyan]Model cache[/cyan] - Storage location for downloaded models

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
        table.add_row("ffmpeg", "[green]✅[/green]", ffmpeg_path)
    else:
        table.add_row("ffmpeg", "[red]❌[/red]", "Not found on PATH")
        ok = False

    # Check sounddevice
    if importlib.util.find_spec("sounddevice") is not None:
        table.add_row("sounddevice", "[green]✅[/green]", "Installed")
    else:
        table.add_row("sounddevice", "[yellow]⚠️[/yellow]", "Not installed (mic capture disabled)")
        ok = False

    # Check model cache
    cfg = load_config()
    cache_path = Path(cfg.model_cache_dir) if cfg.model_cache_dir else None
    if cache_path and cache_path.exists():
        table.add_row("Model cache", "[green]✅[/green]", str(cache_path))
    elif cache_path:
        table.add_row("Model cache", "[yellow]⚠️[/yellow]", f"{cache_path} (will be created)")
    else:
        table.add_row("Model cache", "[dim]➖[/dim]", "Not configured")

    console.print(table)

    if ok:
        console.print("\n[bold green]✅ All checks passed! Ready to transcribe.[/bold green]")
    else:
        console.print("\n[bold red]❌ Some prerequisites missing. Install them for full functionality.[/bold red]")
        raise typer.Exit(code=1)


@app.command(rich_help_panel="Utilities")
def languages() -> None:
    """[bold cyan]📋 List all supported language codes[/bold cyan] for transcription.

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
        title="💡 How to Use",
        border_style="green",
    ))


@app.command(rich_help_panel="vLLM Server")
def check_vllm(
    endpoint: str | None = typer.Option(None, help="vLLM server endpoint (default from config)"),
) -> None:
    """[bold yellow]Check vLLM server connection[/bold yellow] and list available models.

    Use this to verify your vLLM server is running and accessible.
    The server must be started separately with [cyan]vociferous serve-vllm[/cyan].
    """
    config = load_config()
    target = endpoint or config.vllm_endpoint

    try:
        import openai
    except ImportError as exc:  # pragma: no cover - optional dependency guard
        raise DependencyError("openai package is required for vLLM checks; pip install openai") from exc

    client = openai.OpenAI(base_url=f"{target}/v1", api_key="EMPTY")
    try:
        models = client.models.list()
    except Exception as exc:  # pragma: no cover - network dependent
        typer.echo(f"vLLM check failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    served = [m.id for m in models.data]
    if not served:
        typer.echo(f"Connected to {target} but no models are served.")
        raise typer.Exit(code=1)

    typer.echo(f"vLLM endpoint: {target}")
    typer.echo("Models:")
    for mid in served:
        typer.echo(f" - {mid}")


@app.command(rich_help_panel="vLLM Server")
def serve_vllm(
    model: str = typer.Option("openai/whisper-large-v3-turbo", help="Model to serve with vLLM"),
    dtype: str = typer.Option("bfloat16", help="Model dtype (bfloat16|float16|auto)"),
    port: int = typer.Option(8000, help="Port to bind vLLM server"),
) -> None:
    """[bold yellow]Start a vLLM server[/bold yellow] for batch transcription.

    [bold]vLLM provides:[/bold]
      • High-throughput batch processing
      • GPU-optimized inference
      • OpenAI-compatible API

    [bold]Example:[/bold]
      [cyan]vociferous serve-vllm --model openai/whisper-large-v3-turbo[/cyan]

    [white]Note: Requires ~24GB VRAM. Use --engine whisper_turbo for local fallback.[/white]
    """
    if shutil.which("vllm") is None:
        typer.echo("vllm CLI not found on PATH. Install vllm and ensure it's available.", err=True)
        raise typer.Exit(code=1)

    cmd = [
        "vllm",
        "serve",
        model,
        "--dtype",
        dtype,
        "--port",
        str(port),
    ]

    typer.echo(f"Starting vLLM: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - runtime dependent
        typer.echo(f"vLLM serve exited with code {exc.returncode}", err=True)
        raise typer.Exit(code=exc.returncode) from exc


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
