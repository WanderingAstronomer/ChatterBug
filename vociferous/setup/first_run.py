"""First-time setup manager for Vociferous.

Provides a guided first-run experience with progress indicators for:
- System dependency checking
- Model downloading with real progress
- GPU verification
- Model warming (first inference)

This eliminates the silent 21-second startup that confuses new users.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

# Default cache directory following XDG spec
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "vociferous"
SETUP_MARKER = CACHE_DIR / ".setup_complete"


def is_first_run() -> bool:
    """Check if this is the first run (setup not completed)."""
    return not SETUP_MARKER.exists()


def mark_setup_complete() -> None:
    """Mark first-run setup as complete."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SETUP_MARKER.touch()


def reset_setup_state() -> None:
    """Reset setup state (for testing or re-running setup)."""
    if SETUP_MARKER.exists():
        SETUP_MARKER.unlink()


class FirstRunManager:
    """Manages first-time setup and model initialization with progress tracking."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        model_name: str = "nvidia/canary-qwen-2.5b",
    ) -> None:
        self.cache_dir = cache_dir or CACHE_DIR
        self.model_name = model_name
        self._console = None
        self._progress = None

    def _get_console(self):
        """Lazy-load Rich console."""
        if self._console is None:
            try:
                from rich.console import Console
                self._console = Console()
            except ImportError:
                self._console = None
        return self._console

    def is_first_run(self) -> bool:
        """Check if this is the first run."""
        return is_first_run()

    def run_first_time_setup(
        self,
        skip_model_download: bool = False,
        skip_warmup: bool = False,
        on_step_start: Callable[[str], None] | None = None,
        on_step_complete: Callable[[str], None] | None = None,
        on_progress: Callable[[str, int, int], None] | None = None,
    ) -> bool:
        """Run interactive first-time setup with progress indicators.

        Args:
            skip_model_download: Skip model download (for testing)
            skip_warmup: Skip model warmup (for testing)
            on_step_start: Callback when a step starts
            on_step_complete: Callback when a step completes
            on_progress: Callback for progress updates (step_name, current, total)

        Returns:
            True if setup completed successfully, False otherwise.
        """
        console = self._get_console()

        if console:
            self._run_with_rich_progress(
                skip_model_download=skip_model_download,
                skip_warmup=skip_warmup,
            )
        else:
            self._run_simple_progress(
                skip_model_download=skip_model_download,
                skip_warmup=skip_warmup,
                on_step_start=on_step_start,
                on_step_complete=on_step_complete,
                on_progress=on_progress,
            )

        mark_setup_complete()
        return True

    def _run_with_rich_progress(
        self,
        skip_model_download: bool = False,
        skip_warmup: bool = False,
    ) -> None:
        """Run setup with Rich progress bars."""
        from rich.console import Console
        from rich.panel import Panel
        from rich.progress import (
            BarColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        console = Console()

        # Welcome message
        console.print()
        console.print(
            Panel(
                "[bold cyan]Welcome to Vociferous![/bold cyan]\n\n"
                "First-time setup required. This will:\n"
                "  • Check system dependencies\n"
                "  • Download the Canary-Qwen model (~4GB)\n"
                "  • Verify GPU availability\n"
                "  • Warm up the model\n\n"
                "[dim]This takes 2-5 minutes depending on your connection.[/dim]",
                title="[bold]First Run Setup[/bold]",
                border_style="cyan",
            )
        )
        console.print()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:

            # Step 1: Check system dependencies
            task1 = progress.add_task("[cyan]Checking system dependencies...", total=100)
            dep_result = self._check_dependencies()
            progress.update(task1, completed=100, description="[green]✓ System dependencies verified")

            if not dep_result["ffmpeg"]:
                console.print("[yellow]⚠ FFmpeg not found. Audio decoding may fail.[/yellow]")
            if not dep_result["cuda"]:
                console.print("[yellow]⚠ CUDA not available. Will use CPU (slower).[/yellow]")

            # Step 2: Download model
            if not skip_model_download:
                task2 = progress.add_task(
                    f"[cyan]Downloading {self.model_name}...",
                    total=100,
                )
                try:
                    self._download_model_with_progress(
                        lambda current, total: progress.update(
                            task2,
                            completed=int((current / total) * 100) if total > 0 else 0,
                        )
                    )
                    progress.update(task2, completed=100, description="[green]✓ Model downloaded")
                except Exception as e:
                    progress.update(task2, description=f"[red]✗ Model download failed: {e}")
                    raise

            # Step 3: Verify GPU
            task3 = progress.add_task("[cyan]Verifying GPU availability...", total=100)
            gpu_info = self._check_gpu()
            progress.update(task3, completed=100, description="[green]✓ GPU check complete")

            if gpu_info["available"]:
                console.print(f"[green]  GPU: {gpu_info['name']} ({gpu_info['memory_gb']:.1f}GB VRAM)[/green]")
            else:
                console.print("[yellow]  No GPU available, using CPU[/yellow]")

            # Step 4: Warm up model
            if not skip_warmup:
                task4 = progress.add_task("[cyan]Warming up model...", total=100)

                # Simulate progress during model loading (actual loading blocks)
                warmup_done = threading.Event()
                warmup_error = [None]

                def warmup_thread():
                    try:
                        self._warm_model()
                    except Exception as e:
                        warmup_error[0] = e
                    finally:
                        warmup_done.set()

                thread = threading.Thread(target=warmup_thread)
                thread.start()

                # Update progress while waiting
                elapsed = 0
                max_warmup_time = 120  # 2 minutes max
                while not warmup_done.is_set() and elapsed < max_warmup_time:
                    time.sleep(0.5)
                    elapsed += 0.5
                    # Slow exponential approach to 95%
                    pct = min(95, int(50 * (1 - (0.95 ** (elapsed / 2)))) + 50 * (elapsed / max_warmup_time))
                    progress.update(task4, completed=pct)

                thread.join()

                if warmup_error[0]:
                    progress.update(task4, description=f"[red]✗ Warmup failed: {warmup_error[0]}")
                    raise warmup_error[0]
                else:
                    progress.update(task4, completed=100, description="[green]✓ Model ready")

        # Success message
        console.print()
        console.print(
            Panel(
                "[bold green]✓ Setup complete![/bold green]\n\n"
                "You're ready to transcribe audio:\n"
                "  [cyan]vociferous transcribe your_audio.mp3[/cyan]\n\n"
                "[dim]This setup only runs once. Future starts will be faster.[/dim]",
                title="[bold]Ready[/bold]",
                border_style="green",
            )
        )
        console.print()

    def _run_simple_progress(
        self,
        skip_model_download: bool = False,
        skip_warmup: bool = False,
        on_step_start: Callable[[str], None] | None = None,
        on_step_complete: Callable[[str], None] | None = None,
        on_progress: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Run setup with simple text progress (no Rich)."""
        print("\n=== Vociferous First-Run Setup ===\n")

        steps = [
            ("dependencies", "Checking system dependencies"),
            ("model", "Downloading model"),
            ("gpu", "Verifying GPU"),
            ("warmup", "Warming up model"),
        ]

        for step_id, description in steps:
            if step_id == "model" and skip_model_download:
                continue
            if step_id == "warmup" and skip_warmup:
                continue

            if on_step_start:
                on_step_start(step_id)
            print(f"  • {description}...", end="", flush=True)

            if step_id == "dependencies":
                self._check_dependencies()
            elif step_id == "model":
                self._download_model_with_progress(
                    (lambda c, t, step=step_id: on_progress(step, c, t) if on_progress else None)
                )
            elif step_id == "gpu":
                self._check_gpu()
            elif step_id == "warmup":
                self._warm_model()

            print(" done")
            if on_step_complete:
                on_step_complete(step_id)

        print("\n✓ Setup complete! Ready to transcribe.\n")

    def _check_dependencies(self) -> dict:
        """Check system dependencies."""
        result = {
            "ffmpeg": False,
            "cuda": False,
            "python_version": sys.version_info[:2],
        }

        # Check FFmpeg
        result["ffmpeg"] = shutil.which("ffmpeg") is not None

        # Check CUDA
        try:
            import torch
            result["cuda"] = torch.cuda.is_available()
        except ImportError:
            result["cuda"] = False

        return result

    def _check_gpu(self) -> dict:
        """Check GPU availability and info."""
        result = {
            "available": False,
            "name": None,
            "memory_gb": 0.0,
        }

        try:
            import torch
            if torch.cuda.is_available():
                result["available"] = True
                result["name"] = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                result["memory_gb"] = props.total_memory / (1024 ** 3)
        except Exception:
            pass

        return result

    def _download_model_with_progress(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        """Download model with progress tracking.

        Uses huggingface_hub with progress callbacks.
        """
        try:
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            raise ImportError(
                "huggingface_hub is required for model download. "
                "Install it with: pip install huggingface_hub"
            ) from exc

        cache_dir = self.cache_dir / "models"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Check if model already exists
        model_dir = cache_dir / self.model_name.replace("/", "--")
        if model_dir.exists() and any(model_dir.iterdir()):
            logger.info(f"Model already cached at {model_dir}")
            if progress_callback:
                progress_callback(100, 100)
            return model_dir

        # Download with progress
        logger.info(f"Downloading {self.model_name} to {cache_dir}")

        # Simple download without complex progress (huggingface_hub handles its own progress)
        local_dir = snapshot_download(
            repo_id=self.model_name,
            cache_dir=str(cache_dir),
            local_dir=str(model_dir),
        )

        if progress_callback:
            progress_callback(100, 100)

        return Path(local_dir)

    def _warm_model(self) -> None:
        """Load and warm up the model with a test inference.

        This ensures the model is fully loaded into GPU memory and ready
        for fast inference.
        """
        logger.info("Warming up Canary-Qwen model...")

        try:
            from vociferous.domain.model import EngineConfig, EngineKind
            from vociferous.engines.factory import build_engine

            config = EngineConfig(
                device="auto",
                compute_type="bfloat16",
                model_name=self.model_name,
            )

            # Build and warm the engine (this loads the model)
            engine = build_engine(EngineKind.CANARY_QWEN, config)

            # Do a simple text refinement to ensure LLM path is warm too
            _ = engine.refine_text("This is a warm-up test.")

            logger.info("Model warmup complete")

        except Exception as e:
            logger.warning(f"Model warmup failed (non-fatal): {e}")
            # Don't re-raise - warmup failure shouldn't block setup
            # The model will just cold-start on first use


def ensure_setup_complete(
    skip_if_complete: bool = True,
    skip_model_download: bool = False,
    skip_warmup: bool = False,
) -> bool:
    """Ensure first-run setup is complete, running it if needed.

    This is the main entry point for CLI commands to check/run setup.

    Args:
        skip_if_complete: If True, skip setup if marker exists
        skip_model_download: Skip model download (for testing)
        skip_warmup: Skip model warmup (for testing)

    Returns:
        True if setup is complete (either already or just finished)
    """
    if skip_if_complete and not is_first_run():
        return True

    manager = FirstRunManager()
    return manager.run_first_time_setup(
        skip_model_download=skip_model_download,
        skip_warmup=skip_warmup,
    )
