"""Progress tracking for transcription workflows.

Provides a unified progress abstraction that works for both CLI (Rich) and GUI.
This eliminates silent waiting during long transcriptions.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)


class ProgressTracker(ABC):
    """Abstract base for progress tracking across different UI contexts."""

    @abstractmethod
    def add_step(self, description: str, total: int | None = None) -> Any:
        """Add a progress step. Returns a task ID for updates."""
        ...

    @abstractmethod
    def update(self, task_id: Any, *, description: str | None = None, completed: int | None = None) -> None:
        """Update a progress step."""
        ...

    @abstractmethod
    def advance(self, task_id: Any, amount: float = 1.0) -> None:
        """Advance progress by an amount."""
        ...

    @abstractmethod
    def complete(self, task_id: Any) -> None:
        """Mark a step as complete."""
        ...

    @abstractmethod
    def print(self, message: str, *, style: str | None = None) -> None:
        """Print a message without disrupting progress display."""
        ...

    def __enter__(self) -> ProgressTracker:
        return self

    def __exit__(self, *args) -> None:
        """Allow context manager usage without requiring cleanup."""
        return None


class NullProgressTracker(ProgressTracker):
    """No-op progress tracker for silent/batch mode."""

    def add_step(self, description: str, total: int | None = None) -> Any:
        return None

    def update(self, task_id: Any, *, description: str | None = None, completed: int | None = None) -> None:
        pass

    def advance(self, task_id: Any, amount: float = 1.0) -> None:
        pass

    def complete(self, task_id: Any) -> None:
        pass

    def print(self, message: str, *, style: str | None = None) -> None:
        pass


class SimpleProgressTracker(ProgressTracker):
    """Simple text-based progress for environments without Rich."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._active_tasks: dict[str, str] = {}
        self._task_counter = 0

    def add_step(self, description: str, total: int | None = None) -> str:
        if not self.verbose:
            return ""
        self._task_counter += 1
        task_id = f"task-{self._task_counter}"
        self._active_tasks[task_id] = description
        print(f"  → {description}", flush=True)
        return task_id

    def update(self, task_id: Any, *, description: str | None = None, completed: int | None = None) -> None:
        if not self.verbose or task_id not in self._active_tasks:
            return
        if description:
            print(f"    {description}", flush=True)

    def advance(self, task_id: Any, amount: float = 1.0) -> None:
        pass  # Simple tracker doesn't show incremental progress

    def complete(self, task_id: Any) -> None:
        if not self.verbose or task_id not in self._active_tasks:
            return
        desc = self._active_tasks.pop(task_id, "")
        print(f"  ✓ {desc}", flush=True)

    def print(self, message: str, *, style: str | None = None) -> None:
        if self.verbose:
            print(message, flush=True)


class RichProgressTracker(ProgressTracker):
    """Rich-based progress tracker with spinners and progress bars."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._progress = None
        self._console = None
        self._started = False

    def _ensure_started(self) -> None:
        """Lazily initialize Rich progress."""
        if self._started:
            return

        try:
            from rich.console import Console
            from rich.progress import (
                BarColumn,
                Progress,
                SpinnerColumn,
                TaskProgressColumn,
                TextColumn,
                TimeElapsedColumn,
                TimeRemainingColumn,
            )

            self._console = Console()

            if self.verbose:
                self._progress = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    TimeElapsedColumn(),
                    TimeRemainingColumn(),
                    console=self._console,
                )
                self._progress.start()

            self._started = True

        except ImportError:
            # Fall back to simple tracker behavior
            logger.warning("Rich not available, using simple progress")
            self._started = True

    def __enter__(self) -> RichProgressTracker:
        self._ensure_started()
        return self

    def __exit__(self, *args) -> None:
        if self._progress is not None:
            self._progress.stop()
            self._progress = None
        self._started = False

    def add_step(self, description: str, total: int | None = None) -> Any:
        if not self.verbose:
            return None

        self._ensure_started()

        if self._progress is None:
            # Fallback to simple print
            print(f"  → {description}", flush=True)
            return description

        return self._progress.add_task(description, total=total or 100)

    def update(self, task_id: Any, *, description: str | None = None, completed: int | None = None) -> None:
        if not self.verbose or task_id is None:
            return

        if self._progress is None:
            if description:
                print(f"    {description}", flush=True)
            return

        kwargs = {}
        if description is not None:
            kwargs["description"] = description
        if completed is not None:
            kwargs["completed"] = completed

        if kwargs:
            self._progress.update(task_id, **kwargs)

    def advance(self, task_id: Any, amount: float = 1.0) -> None:
        if not self.verbose or task_id is None or self._progress is None:
            return
        self._progress.advance(task_id, amount)

    def complete(self, task_id: Any) -> None:
        if not self.verbose or task_id is None:
            return

        if self._progress is None:
            if isinstance(task_id, str):
                print(f"  ✓ {task_id}", flush=True)
            return

        # Mark as complete by setting to 100%
        task = self._progress._tasks.get(task_id)
        if task is not None:
            self._progress.update(task_id, completed=task.total or 100)

    def print(self, message: str, *, style: str | None = None) -> None:
        if not self.verbose:
            return

        if self._console is not None:
            self._console.print(message, style=style)
        else:
            print(message, flush=True)


class TranscriptionProgress:
    """High-level progress tracker for transcription workflows.

    This is the main interface for workflow code. It provides semantic
    methods for common transcription steps.
    """

    def __init__(
        self,
        verbose: bool = True,
        tracker: ProgressTracker | None = None,
    ):
        self.verbose = verbose

        if tracker is not None:
            self._tracker = tracker
        elif verbose:
            try:
                self._tracker = RichProgressTracker(verbose=True)
            except ImportError:
                self._tracker = SimpleProgressTracker(verbose=True)
        else:
            self._tracker = NullProgressTracker()

        self._current_task: Any = None

    def __enter__(self) -> TranscriptionProgress:
        self._tracker.__enter__()
        return self

    def __exit__(self, *args) -> None:
        self._tracker.__exit__(*args)

    # High-level workflow steps

    def start_decode(self) -> Any:
        """Start the decode step."""
        return self._tracker.add_step("[cyan]Decoding audio to WAV...", total=None)

    def complete_decode(self, task_id: Any) -> None:
        """Complete the decode step."""
        self._tracker.update(task_id, description="[green]✓ Audio decoded")
        self._tracker.complete(task_id)

    def start_preprocess(self) -> Any:
        """Start the preprocessing step."""
        return self._tracker.add_step("[cyan]Preprocessing audio...", total=None)

    def complete_preprocess(self, task_id: Any, preset: str) -> None:
        """Complete the preprocessing step."""
        self._tracker.update(task_id, description=f"[green]✓ Audio preprocessed ({preset})")
        self._tracker.complete(task_id)

    def start_vad(self) -> Any:
        """Start VAD step."""
        return self._tracker.add_step("[cyan]Detecting speech segments...", total=None)

    def complete_vad(self, task_id: Any, segment_count: int) -> None:
        """Complete VAD step."""
        self._tracker.update(task_id, description=f"[green]✓ Found {segment_count} speech segments")
        self._tracker.complete(task_id)

    def start_condense(self) -> Any:
        """Start condense step."""
        return self._tracker.add_step("[cyan]Condensing audio...", total=None)

    def complete_condense(self, task_id: Any, chunk_count: int) -> None:
        """Complete condense step."""
        self._tracker.update(task_id, description=f"[green]✓ Audio split into {chunk_count} chunks")
        self._tracker.complete(task_id)

    def start_transcribe(self, chunk_count: int) -> Any:
        """Start transcription step with known chunk count."""
        return self._tracker.add_step(
            f"[cyan]Transcribing {chunk_count} chunks...",
            total=chunk_count,
        )

    def update_transcribe(self, task_id: Any, current: int, total: int) -> None:
        """Update transcription progress."""
        self._tracker.update(
            task_id,
            description=f"[cyan]Transcribing chunk {current}/{total}...",
            completed=current,
        )

    def advance_transcribe(self, task_id: Any) -> None:
        """Advance transcription by one chunk."""
        self._tracker.advance(task_id, 1.0)

    def complete_transcribe(self, task_id: Any) -> None:
        """Complete transcription step."""
        self._tracker.update(task_id, description="[green]✓ Transcription complete")
        self._tracker.complete(task_id)

    def start_refine(self) -> Any:
        """Start refinement step."""
        return self._tracker.add_step("[cyan]Refining transcript...", total=None)

    def complete_refine(self, task_id: Any) -> None:
        """Complete refinement step."""
        self._tracker.update(task_id, description="[green]✓ Transcript refined")
        self._tracker.complete(task_id)

    # Generic step methods (for extensibility)

    def add_step(self, description: str, total: int | None = None) -> Any:
        """Add a generic step."""
        return self._tracker.add_step(description, total=total)

    def update(self, task_id: Any, *, description: str | None = None, completed: int | None = None) -> None:
        """Update a step."""
        self._tracker.update(task_id, description=description, completed=completed)

    def advance(self, task_id: Any, amount: float = 1.0) -> None:
        """Advance progress."""
        self._tracker.advance(task_id, amount)

    def complete(self, task_id: Any) -> None:
        """Complete a step."""
        self._tracker.complete(task_id)

    def print(self, message: str, *, style: str | None = None) -> None:
        """Print a message."""
        self._tracker.print(message, style=style)

    def success(self, message: str = "Transcription complete") -> None:
        """Print success message."""
        self._tracker.print(f"[bold green]✓ {message}[/bold green]", style="bold green")

    def warning(self, message: str) -> None:
        """Print warning message."""
        self._tracker.print(f"[yellow]⚠ {message}[/yellow]", style="yellow")

    def error(self, message: str) -> None:
        """Print error message."""
        self._tracker.print(f"[red]✗ {message}[/red]", style="red")


@contextmanager
def transcription_progress(verbose: bool = True) -> Generator[TranscriptionProgress, None, None]:
    """Context manager for transcription progress tracking.

    Usage:
        with transcription_progress() as progress:
            task = progress.start_decode()
            # ... do work ...
            progress.complete_decode(task)
    """
    progress = TranscriptionProgress(verbose=verbose)
    with progress:
        yield progress
