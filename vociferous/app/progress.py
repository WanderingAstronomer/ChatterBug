"""Progress tracking for transcription workflows.

Provides a unified progress abstraction that works for both CLI (Rich) and GUI.
This eliminates silent waiting during long transcriptions.

Modes:
    - rich: Beautiful terminal progress bars using Rich library (CLI default)
    - callback: Call a callback function with progress updates (GUI mode)
    - silent: No output (batch processing, tests)
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from rich.console import Console
    from rich.progress import Progress
    from vociferous.domain.protocols import ProgressCallback

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

    def __exit__(self, *args: object) -> None:
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


class CallbackProgressTracker(ProgressTracker):
    """Callback-based progress tracker for GUI integration.
    
    Instead of displaying progress directly, this tracker calls a callback
    function with progress updates. This allows GUIs to update their own
    widgets without depending on any specific UI framework.
    
    Example:
        >>> def update_gui(update: ProgressUpdateData):
        ...     progress_bar.value = update.progress or 0
        ...     status_label.text = update.message
        >>> 
        >>> tracker = CallbackProgressTracker(callback=update_gui)
        >>> task = tracker.add_step("Processing...", total=100)
        >>> tracker.update(task, completed=50)  # Calls update_gui
        >>> tracker.complete(task)  # Calls update_gui with progress=1.0
    """

    def __init__(self, callback: ProgressCallback):
        """Initialize callback tracker.
        
        Args:
            callback: Function to call with progress updates.
                      Receives ProgressUpdateData instances.
        
        Raises:
            ValueError: If callback is None
        """
        if callback is None:
            raise ValueError("callback parameter required for CallbackProgressTracker")
        
        from vociferous.domain.protocols import ProgressUpdateData
        
        self._callback = callback
        self._task_counter = 0
        self._active_tasks: dict[str, _CallbackTaskState] = {}
    
    def add_step(self, description: str, total: int | None = None) -> str:
        from vociferous.domain.protocols import ProgressUpdateData
        
        self._task_counter += 1
        task_id = f"callback-task-{self._task_counter}"
        
        # Extract stage name from description (strip Rich markup)
        stage = self._extract_stage(description)
        
        # Create task state
        self._active_tasks[task_id] = _CallbackTaskState(
            stage=stage,
            description=description,
            total=total,
            completed=0,
            start_time=time.time(),
        )
        
        # Send initial update
        update = ProgressUpdateData(
            stage=stage,
            progress=0.0 if total else None,
            message=self._clean_description(description),
            elapsed_s=0.0,
        )
        self._callback(update)
        
        return task_id
    
    def update(self, task_id: Any, *, description: str | None = None, completed: int | None = None) -> None:
        if task_id not in self._active_tasks:
            return
        
        from vociferous.domain.protocols import ProgressUpdateData
        
        state = self._active_tasks[task_id]
        
        if description:
            state.description = description
        if completed is not None:
            state.completed = completed
        
        # Calculate progress percentage
        progress: float | None = None
        if state.total and state.total > 0:
            progress = state.completed / state.total
        
        elapsed = time.time() - state.start_time
        
        update = ProgressUpdateData(
            stage=state.stage,
            progress=progress,
            message=self._clean_description(state.description),
            elapsed_s=elapsed,
        )
        self._callback(update)
    
    def advance(self, task_id: Any, amount: float = 1.0) -> None:
        if task_id not in self._active_tasks:
            return
        
        state = self._active_tasks[task_id]
        state.completed += int(amount)
        self.update(task_id, completed=state.completed)
    
    def complete(self, task_id: Any) -> None:
        if task_id not in self._active_tasks:
            return
        
        from vociferous.domain.protocols import ProgressUpdateData
        
        state = self._active_tasks.pop(task_id)
        elapsed = time.time() - state.start_time
        
        update = ProgressUpdateData(
            stage=state.stage,
            progress=1.0,
            message=self._clean_description(state.description),
            elapsed_s=elapsed,
        )
        self._callback(update)
    
    def print(self, message: str, *, style: str | None = None) -> None:
        # Send as an info update (no specific stage)
        from vociferous.domain.protocols import ProgressUpdateData
        
        # Get current stage from any active task, or "info"
        current_stage = "info"
        if self._active_tasks:
            current_stage = next(iter(self._active_tasks.values())).stage
        
        update = ProgressUpdateData(
            stage=current_stage,
            progress=None,
            message=self._clean_description(message),
        )
        self._callback(update)
    
    def _extract_stage(self, description: str) -> str:
        """Extract stage name from description.
        
        Maps common descriptions to stage names:
            "Decoding audio..." -> "decode"
            "Detecting speech..." -> "vad"
            "Transcribing..." -> "transcribe"
        
        Note: Order matters - "transcribe" is checked before "condense"
        since "Transcribing 3 chunks" contains both keywords.
        """
        desc_lower = description.lower()
        if "decod" in desc_lower:
            return "decode"
        if "preprocess" in desc_lower:
            return "preprocess"
        if "vad" in desc_lower or "speech" in desc_lower or "segment" in desc_lower:
            return "vad"
        # Check transcribe BEFORE condense since "Transcribing chunks" has both
        if "transcrib" in desc_lower:
            return "transcribe"
        if "refin" in desc_lower:
            return "refine"
        if "condens" in desc_lower or "chunk" in desc_lower or "split" in desc_lower:
            return "condense"
        return "processing"
    
    def _clean_description(self, description: str) -> str:
        """Remove Rich markup from description for GUI display."""
        import re
        # Remove Rich markup like [cyan], [green], [/color]
        return re.sub(r"\[/?[^\]]+\]", "", description).strip()


class _CallbackTaskState:
    """Internal state for callback tracker tasks."""
    
    __slots__ = ("stage", "description", "total", "completed", "start_time")
    
    def __init__(
        self,
        stage: str,
        description: str,
        total: int | None,
        completed: int,
        start_time: float,
    ):
        self.stage = stage
        self.description = description
        self.total = total
        self.completed = completed
        self.start_time = start_time


class RichProgressTracker(ProgressTracker):
    """Rich-based progress tracker with spinners and progress bars."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._progress: Progress | None = None
        self._console: Console | None = None
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
                # Use a custom Progress that handles both determinate and indeterminate tasks
                # The bar/percentage/remaining columns gracefully hide when total=None
                self._progress = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(bar_width=40),
                    TaskProgressColumn(),
                    TimeElapsedColumn(),
                    TimeRemainingColumn(),
                    console=self._console,
                    expand=False,
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

    def __exit__(self, *args: object) -> None:
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

        # For indeterminate tasks (total=None), Rich will show spinner only
        # For determinate tasks, Rich will show full progress bar
        return self._progress.add_task(description, total=total)

    def update(self, task_id: Any, *, description: str | None = None, completed: int | None = None) -> None:
        if not self.verbose or task_id is None:
            return

        if self._progress is None:
            if description:
                print(f"    {description}", flush=True)
            return

        # Call update with explicit kwargs to satisfy type checker
        if description is not None and completed is not None:
            self._progress.update(task_id, description=description, completed=completed)
        elif description is not None:
            self._progress.update(task_id, description=description)
        elif completed is not None:
            self._progress.update(task_id, completed=completed)

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
    
    Supports three modes:
        - "rich": Beautiful terminal progress bars using Rich library (CLI default)
        - "callback": Call a callback function with progress updates (GUI mode)
        - "silent": No output (batch processing, tests)
    
    Example (CLI):
        >>> with TranscriptionProgress(mode="rich") as progress:
        ...     task = progress.start_decode()
        ...     # ... decode audio ...
        ...     progress.complete_decode(task)
    
    Example (GUI):
        >>> def update_gui(update: ProgressUpdateData):
        ...     progress_bar.value = update.progress or 0
        ...     status_label.text = update.message
        >>> 
        >>> with TranscriptionProgress(mode="callback", callback=update_gui) as progress:
        ...     task = progress.start_decode()
        ...     # ... decode audio ...
        ...     progress.complete_decode(task)
    """

    def __init__(
        self,
        verbose: bool = True,
        tracker: ProgressTracker | None = None,
        *,
        mode: Literal["rich", "callback", "silent"] | None = None,
        callback: ProgressCallback | None = None,
    ):
        """Initialize progress tracker.
        
        Args:
            verbose: Legacy parameter for CLI mode. Ignored if mode is specified.
            tracker: Pre-configured tracker instance (overrides mode).
            mode: Display mode - "rich" (CLI), "callback" (GUI), or "silent" (tests).
                  If not specified, inferred from verbose parameter for backward compatibility.
            callback: Callback function for GUI updates (required if mode="callback").
        
        Raises:
            ValueError: If mode="callback" but callback is None.
        """
        self.verbose = verbose
        
        # New mode-based initialization
        if mode is not None:
            if mode == "callback":
                if callback is None:
                    raise ValueError("callback parameter required when mode='callback'")
                self._tracker: ProgressTracker = CallbackProgressTracker(callback)
            elif mode == "silent":
                self._tracker = NullProgressTracker()
            else:  # mode == "rich"
                try:
                    self._tracker = RichProgressTracker(verbose=True)
                except ImportError:
                    self._tracker = SimpleProgressTracker(verbose=True)
        elif tracker is not None:
            # Legacy: explicit tracker provided
            self._tracker = tracker
        elif verbose:
            # Legacy: infer from verbose flag
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

    def __exit__(self, *args: object) -> None:
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
        """Start transcription step with known chunk count.
        
        Uses an indeterminate spinner because batch transcription is atomic
        and we cannot provide per-chunk progress updates.
        """
        return self._tracker.add_step(
            f"[cyan]Transcribing {chunk_count} chunk{'s' if chunk_count > 1 else ''}...",
            total=None,  # Indeterminate - batch transcription is atomic
        )

    def update_transcribe(self, task_id: Any, current: int, total: int) -> None:
        """Update transcription progress (for sequential transcription only)."""
        self._tracker.update(
            task_id,
            description=f"[cyan]Transcribing chunk {current}/{total}...",
            completed=current,
        )

    def advance_transcribe(self, task_id: Any) -> None:
        """Advance transcription by one chunk (for sequential transcription only)."""
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
def transcription_progress(
    verbose: bool = True,
    *,
    mode: Literal["rich", "callback", "silent"] | None = None,
    callback: ProgressCallback | None = None,
) -> Generator[TranscriptionProgress, None, None]:
    """Context manager for transcription progress tracking.

    Args:
        verbose: Legacy parameter for CLI mode. Ignored if mode is specified.
        mode: Display mode - "rich" (CLI), "callback" (GUI), or "silent" (tests).
        callback: Callback function for GUI updates (required if mode="callback").

    Usage (CLI):
        with transcription_progress(mode="rich") as progress:
            task = progress.start_decode()
            # ... do work ...
            progress.complete_decode(task)
    
    Usage (GUI):
        def update_gui(update):
            progress_bar.value = update.progress or 0
        
        with transcription_progress(mode="callback", callback=update_gui) as progress:
            task = progress.start_decode()
            # ... do work ...
            progress.complete_decode(task)
    """
    progress = TranscriptionProgress(verbose=verbose, mode=mode, callback=callback)
    with progress:
        yield progress
