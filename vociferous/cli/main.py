from __future__ import annotations

from pathlib import Path
import logging
import subprocess
import shutil
import typing

from vociferous.app import TranscriptionSession, configure_logging
from vociferous.audio.sources import FileSource
from vociferous.app.sinks import PolishingSink
from vociferous.config import load_config
from vociferous.domain import EngineConfig, TranscriptionOptions
from vociferous.domain.model import DEFAULT_WHISPER_MODEL, TranscriptionPreset, EngineKind
from vociferous.domain.exceptions import (
    DependencyError, EngineError, AudioDecodeError, ConfigurationError
)
from vociferous.engines.factory import build_engine
from vociferous.engines.model_registry import normalize_model_name
from vociferous.polish.base import PolisherConfig
from vociferous.polish.factory import build_polisher
from vociferous.tui import run_tui
from vociferous.cli.helpers import build_sink

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
    help="Vociferous - Local-first speech transcription",
    cls=BrightTyperGroup,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
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
    # Common options
    model: str | None = typer.Option(None, help="Override model name", hidden=True),
    device: str | None = typer.Option(None, help="Device: cpu or cuda", hidden=True),
    vad_filter: bool = typer.Option(True, help="Apply voice activity detection", hidden=True),
    clipboard: bool = typer.Option(False, help="Copy transcript to clipboard", hidden=True),
    save_history: bool = typer.Option(False, help="Save to history", hidden=True),
    # Advanced options (hidden from main help)
    compute_type: str | None = typer.Option(None, help="Compute type (int8, float16, etc.)", hidden=True),
    numexpr_max_threads: int | None = typer.Option(None, help="Limit NumExpr threads", hidden=True),
    word_timestamps: bool = typer.Option(False, help="Enable word-level timestamps", hidden=True),
    enable_batching: bool = typer.Option(True, help="Enable batched inference", hidden=True),
    batch_size: int = typer.Option(16, help="Batch size for inference", hidden=True),
    beam_size: int = typer.Option(1, help="Beam size for decoding", hidden=True),
    chunk_ms: int = typer.Option(30000, help="Audio chunk size (ms)", hidden=True),
    trim_tail_ms: int = typer.Option(800, help="Trim trailing silence (ms)", hidden=True),
    noise_gate_db: float | None = typer.Option(None, help="Noise gate threshold (dBFS)", hidden=True),
    whisper_temperature: float = typer.Option(0.0, help="Whisper sampling temperature", hidden=True),
    prompt: str | None = typer.Option(None, help="Prompt for Voxtral", hidden=True),
    max_new_tokens: int = typer.Option(0, help="Voxtral max tokens", hidden=True),
    gen_temperature: float = typer.Option(0.0, help="Voxtral temperature", hidden=True),
    vllm_endpoint: str = typer.Option("http://localhost:8000", help="vLLM server URL", hidden=True),
    clean_disfluencies: bool = typer.Option(False, help="Remove stutters/fillers", hidden=True),
    no_clean_disfluencies: bool = typer.Option(False, help="Disable disfluency cleaning", hidden=True),
    fast: bool = typer.Option(False, help="Alias for --preset fast", hidden=True),
    polish: bool | None = typer.Option(None, help="Enable transcript polishing", hidden=True),
    polish_model: str | None = typer.Option(None, help="Polisher model name", hidden=True),
    polish_max_tokens: int = typer.Option(128, help="Polisher max tokens", hidden=True),
    polish_temperature: float = typer.Option(0.2, help="Polisher temperature", hidden=True),
    polish_gpu_layers: int = typer.Option(0, help="Polisher GPU layers", hidden=True),
    polish_context_length: int = typer.Option(2048, help="Polisher context length", hidden=True),
) -> None:
    """Transcribe an audio file to text using local ASR engines.

    ENGINES:
      whisper_turbo - Fast, accurate, works offline (default)
      voxtral_local - Smart punctuation, Mistral-based
      whisper_vllm  - Use vLLM server for Whisper
      voxtral_vllm  - Use vLLM server for Voxtral

    EXAMPLES:
      vociferous transcribe audio.mp3
      vociferous transcribe audio.wav --language fr --preset high_accuracy
      vociferous transcribe audio.flac --engine voxtral_local --output transcript.txt
    """
    logging.basicConfig(level=logging.INFO)
    config = load_config()
    # Apply preset overrides (new presets)
    preset_lower = (preset or "").replace("-", "_").lower()
    if fast and not preset_lower:
        preset_lower = "fast"

    # Default to balanced if no preset specified for whisper_vllm
    if not preset_lower and engine in {"whisper_vllm", "voxtral_vllm"}:
        preset_lower = "balanced"

    if preset_lower in {"high_accuracy", "balanced", "fast"}:
        target_device = device or config.device
        if engine == "whisper_vllm":
            if preset_lower == "high_accuracy":
                model = model or "openai/whisper-large-v3"
                compute_type = compute_type or ("bfloat16" if target_device == "cuda" else "float32")
                beam_size = 2
            elif preset_lower == "fast":
                model = model or "openai/whisper-large-v3-turbo"
                compute_type = compute_type or ("float16" if target_device == "cuda" else "int8")
                beam_size = 1
            else:  # balanced
                model = model or "openai/whisper-large-v3-turbo"
                compute_type = compute_type or ("bfloat16" if target_device == "cuda" else "float32")
                beam_size = max(beam_size, 1)
            enable_batching = True
            vad_filter = True
        elif engine == "whisper_turbo":
            # Keep legacy CT2 presets for local engine
            if preset_lower == "high_accuracy":
                model = model or "openai/whisper-large-v3"
                compute_type = compute_type or ("float16" if target_device == "cuda" else "int8")
                beam_size = max(beam_size, 2)
                batch_size = max(batch_size, 8)
            elif preset_lower == "fast":
                model = model or DEFAULT_WHISPER_MODEL
                compute_type = compute_type or "int8_float16"
                beam_size = 1
                batch_size = max(batch_size, 16)
            else:  # balanced
                model = model or DEFAULT_WHISPER_MODEL
                compute_type = compute_type or ("float16" if target_device == "cuda" else "int8")
                beam_size = max(beam_size, 1)
                batch_size = max(batch_size, 12)
            enable_batching = True
            vad_filter = True

    if numexpr_max_threads is None:
        env_threads = config.numexpr_max_threads
    else:
        env_threads = numexpr_max_threads
    if env_threads is not None:
        import os
        os.environ["NUMEXPR_MAX_THREADS"] = str(env_threads)

    polish_enabled = config.polish_enabled if polish is None else polish
    polisher_config = PolisherConfig(
        enabled=polish_enabled,
        model=polish_model or config.polish_model,
        params={
            **config.polish_params,
            "max_tokens": str(polish_max_tokens),
            "temperature": str(polish_temperature),
            "gpu_layers": str(polish_gpu_layers),
            "context_length": str(polish_context_length),
        },
    )

    engine_config = EngineConfig(
        model_name=normalize_model_name(engine, model or config.model_name if engine == config.engine else model),
        compute_type=compute_type or config.compute_type,
        device=device or config.device,
        model_cache_dir=config.model_cache_dir,
        params={
            **config.params,
            "preset": preset_lower,
            "word_timestamps": str(word_timestamps).lower(),
            "enable_batching": str(enable_batching).lower(),
            "batch_size": str(batch_size),
            "vad_filter": str(vad_filter).lower(),
            # Default is true in engine; flags override: explicit enable OR (no explicit disable)
            "clean_disfluencies": str(clean_disfluencies or not no_clean_disfluencies).lower(),
            # vLLM endpoint for vLLM engines
            "vllm_endpoint": vllm_endpoint,
        },
    )
    options = TranscriptionOptions(
        language=language,
        preset=typing.cast(TranscriptionPreset | None, preset_lower) if preset_lower in {"high_accuracy", "balanced", "fast"} else None,
        prompt=prompt,
        params={
            "max_new_tokens": str(max_new_tokens) if max_new_tokens > 0 else "",
            "temperature": str(gen_temperature) if gen_temperature > 0 else "",
        },
        beam_size=beam_size if beam_size > 0 else None,
        temperature=whisper_temperature if whisper_temperature > 0 else None,
    )

    try:
        engine_adapter = build_engine(engine, engine_config)
        polisher = build_polisher(polisher_config)
    except (DependencyError, EngineError) as exc:
        typer.echo(f"Engine initialization error: {exc}", err=True)
        raise typer.Exit(code=3) from exc
    except ConfigurationError as exc:
        typer.echo(f"Polisher error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    source = FileSource(
        file,
        chunk_ms=chunk_ms,
        trim_tail_ms=trim_tail_ms,
        noise_gate_db=noise_gate_db,
    )
    
    # Build composed sink from CLI flags
    sink = build_sink(
        output=output,
        clipboard=clipboard,
        save_history=save_history,
        history_dir=Path(config.history_dir),
        history_limit=config.history_limit,
    )
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
        session.start(source, engine_adapter, sink, options, engine_kind=engine)
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


@app.command(rich_help_panel="Interfaces")
def tui(
    file: Path | None = typer.Option(None, help="Optional audio file; default is microphone"),
    engine: EngineKind = "whisper_turbo",
    language: str = "en",
) -> None:
    """[bold magenta]Full-screen TUI[/bold magenta] for live transcription. [yellow](Experimental)[/yellow]"""
    try:
        run_tui(file=file, engine=engine, language=language)
    except Exception as exc:
        typer.echo(f"TUI error: {exc}", err=True)
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
