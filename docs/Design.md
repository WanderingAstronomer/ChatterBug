# 🔧 Backend Polish for GUI Readiness

**Target:** Complete backend stability before GUI implementation  
**Timeline:** ~1 week of focused work  
**Framework:** KivyMD (hot reload enabled by default via daemon)  
**Status:** Logging fix (v0.7.8) in progress with Opus 4.5

---

## 📋 Overview of Required Work

| Task | Priority | Duration | Dependencies |
|------|----------|----------|--------------|
| 1. Progress Callback System | 🔴 Critical | 2-3 days | None |
| 2. Error Serialization | 🔴 Critical | 1-2 days | None |
| 3. Audio File Validation | 🟡 High | 1-2 days | None |
| 4. Async Daemon Startup | 🟡 High | 1 day | Task 1 |
| 5. Config Schema for GUI | 🟡 High | 1 day | None |

**Total:** 6-9 days (can be parallelized)

---

## 🎯 Task 1: Progress Callback System

### Problem Statement

The current `TranscriptionProgress` class is tightly coupled to Rich (CLI library). GUI needs a **callback-based** progress system that can update widgets from background threads.

**Current architecture:**
```python
class TranscriptionProgress:
    def __init__(self, verbose: bool = True):
        self.progress = Progress(...)  # Rich-specific, CLI only
```

**Required architecture:**
```python
class TranscriptionProgress:
    def __init__(
        self,
        mode:  Literal["rich", "callback", "silent"] = "rich",
        callback: ProgressCallback | None = None,
    ):
        # Support CLI (Rich), GUI (callback), or silent (tests/batch)
```

---

### Implementation Plan

#### Step 1.1: Define Progress Callback Protocol

**File:** `vociferous/domain/protocols.py` (NEW)

```python
"""Protocol definitions for dependency injection and abstraction."""

from __future__ import annotations

from typing import Protocol, Callable

__all__ = [
    "ProgressCallback",
    "ProgressUpdate",
]


# Type alias for progress callbacks
ProgressCallback = Callable[["ProgressUpdate"], None]


class ProgressUpdate(Protocol):
    """Protocol for progress update data passed to callbacks."""
    
    stage: str
    """Current stage name (e.g., 'decode', 'vad', 'transcribe')."""
    
    progress: float | None
    """Progress from 0.0 to 1.0, or None for indeterminate."""
    
    message: str
    """Human-readable status message."""
    
    elapsed_s: float | None = None
    """Optional:  elapsed time in seconds."""
    
    remaining_s: float | None = None
    """Optional: estimated remaining time in seconds."""


# Concrete dataclass for passing to callbacks
from dataclasses import dataclass

@dataclass
class ProgressUpdateData:
    """Concrete implementation of ProgressUpdate protocol."""
    
    stage: str
    progress: float | None
    message:  str
    elapsed_s: float | None = None
    remaining_s: float | None = None
```

**Why this design:**
- ✅ Protocol allows type checking without hard dependency
- ✅ Dataclass makes it easy to construct updates
- ✅ Optional fields for flexibility (not all stages have time estimates)

---

#### Step 1.2: Update TranscriptionProgress for Multi-Mode Support

**File:** `vociferous/app/progress.py` (MAJOR UPDATE)

```python
"""Progress tracking abstraction for CLI and GUI."""

from __future__ import annotations

import time
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from vociferous.domain.protocols import ProgressCallback, ProgressUpdateData

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
)

__all__ = [
    "TranscriptionProgress",
    "transcription_progress",
]


class TranscriptionProgress:
    """Multi-mode progress tracker supporting CLI (Rich) and GUI (callbacks)."""
    
    def __init__(
        self,
        mode: Literal["rich", "callback", "silent"] = "rich",
        callback: ProgressCallback | None = None,
    ):
        """Initialize progress tracker. 
        
        Args:
            mode: Display mode
                - "rich": Use Rich library for CLI (default)
                - "callback":  Call callback function for GUI updates
                - "silent": No output (for tests/batch processing)
            callback: Function to call with progress updates (required if mode="callback")
        
        Raises:
            ValueError:  If mode="callback" but callback is None
        """
        self.mode = mode
        self. callback = callback
        self.console = Console()
        
        # Validate callback requirement
        if mode == "callback" and callback is None:
            raise ValueError("callback parameter required when mode='callback'")
        
        # Rich progress instance (only for CLI mode)
        self.progress: Progress | None = None
        if mode == "rich":
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=self.console,
            )
        
        # Track current stage for updates
        self._current_stage: str | None = None
        self._current_task_id: int | None = None
        self._stage_start_time: float | None = None
    
    def __enter__(self):
        if self.progress: 
            self.progress.__enter__()
        return self
    
    def __exit__(self, *args):
        if self.progress:
            self.progress.__exit__(*args)
    
    def start_stage(
        self,
        stage: str,
        message: str,
        total: int | None = None,
    ) -> None:
        """Start a new progress stage.
        
        Args:
            stage: Stage identifier (e.g., "decode", "vad", "transcribe")
            message: Human-readable message
            total: Total units for determinate progress, or None for indeterminate
        """
        self._current_stage = stage
        self._stage_start_time = time.time()
        
        if self.mode == "rich" and self.progress:
            # Add task to Rich progress display
            self._current_task_id = self.progress.add_task(message, total=total)
        
        elif self.mode == "callback" and self.callback:
            # Send initial update to callback
            from vociferous.domain.protocols import ProgressUpdateData
            update = ProgressUpdateData(
                stage=stage,
                progress=0.0 if total else None,
                message=message,
                elapsed_s=0.0,
            )
            self.callback(update)
    
    def update_stage(
        self,
        progress: float | None = None,
        message: str | None = None,
        advance:  float = 0.0,
    ) -> None:
        """Update current stage progress.
        
        Args:
            progress:  Absolute progress (0.0 to 1.0), or None for indeterminate
            message: Optional new status message
            advance: Amount to advance progress (alternative to absolute progress)
        """
        if self._current_stage is None:
            return  # No active stage
        
        elapsed = time.time() - self._stage_start_time if self._stage_start_time else None
        
        if self.mode == "rich" and self.progress and self._current_task_id is not None:
            # Update Rich progress bar
            if message:
                self.progress.update(self._current_task_id, description=message)
            if progress is not None:
                # Convert 0.0-1.0 to percentage
                self.progress.update(self._current_task_id, completed=progress * 100)
            if advance > 0:
                self. progress.advance(self._current_task_id, advance)
        
        elif self. mode == "callback" and self. callback:
            # Send update to callback
            from vociferous. domain.protocols import ProgressUpdateData
            update = ProgressUpdateData(
                stage=self._current_stage,
                progress=progress,
                message=message or f"Processing {self._current_stage}.. .",
                elapsed_s=elapsed,
            )
            self.callback(update)
    
    def complete_stage(self, message: str | None = None) -> None:
        """Mark current stage as complete."""
        if self._current_stage is None:
            return
        
        elapsed = time.time() - self._stage_start_time if self._stage_start_time else None
        
        if self.mode == "rich" and self.progress and self._current_task_id is not None:
            # Mark Rich task as complete
            self.progress. update(
                self._current_task_id,
                completed=100,
                description=message or f"✓ {self._current_stage} complete",
            )
            self. progress.remove_task(self._current_task_id)
        
        elif self.mode == "callback" and self.callback:
            # Send completion update
            from vociferous.domain. protocols import ProgressUpdateData
            update = ProgressUpdateData(
                stage=self._current_stage,
                progress=1.0,
                message=message or f"✓ {self._current_stage} complete",
                elapsed_s=elapsed,
            )
            self.callback(update)
        
        # Reset stage tracking
        self._current_stage = None
        self._current_task_id = None
        self._stage_start_time = None
    
    def print(self, message: str, style: str | None = None) -> None:
        """Print a message without disrupting progress display. 
        
        Args:
            message: Message to print
            style: Optional Rich style (e.g., "bold green", "yellow")
        """
        if self.mode == "rich": 
            if self.progress:
                self.progress.console.print(message, style=style)
            else:
                self.console.print(message, style=style)
        
        elif self.mode == "callback" and self.callback:
            # Send as a message update (no stage change)
            from vociferous. domain.protocols import ProgressUpdateData
            update = ProgressUpdateData(
                stage=self._current_stage or "info",
                progress=None,
                message=message,
            )
            self.callback(update)
        
        # Silent mode:  do nothing


def transcription_progress(
    mode: Literal["rich", "callback", "silent"] = "rich",
    callback: ProgressCallback | None = None,
) -> TranscriptionProgress:
    """Context manager for transcription progress tracking. 
    
    Usage:
        with transcription_progress(mode="rich") as progress:
            progress.start_stage("decode", "Decoding audio.. .", total=100)
            progress.update_stage(progress=0.5)
            progress.complete_stage()
    """
    return TranscriptionProgress(mode=mode, callback=callback)
```

**Key features:**
- ✅ Three modes: `rich` (CLI), `callback` (GUI), `silent` (tests)
- ✅ Stage-based tracking (decode → VAD → transcribe → refine)
- ✅ Determinate and indeterminate progress support
- ✅ Elapsed time tracking
- ✅ Type-safe with protocols
- ✅ Backward compatible (CLI still works)

---

#### Step 1.3: Update Workflow to Use New Progress API

**File:** `vociferous/app/workflow.py` (UPDATE)

Find all places where progress is used and update to new API:

**Before:**
```python
with progress: 
    decode_task = progress.add_step("Decoding audio.. .", total=None)
    decoded_path = decode_component.decode(source.path)
    progress.complete(decode_task)
```

**After:**
```python
with progress:
    progress.start_stage("decode", "Decoding audio to WAV...", total=None)
    decoded_path = decode_component.decode(source.path)
    progress.complete_stage("✓ Audio decoded")
```

**Changes needed in `transcribe_file_workflow()`:**

```python
def transcribe_file_workflow(
    source: Source,
    engine_profile: EngineProfile,
    segmentation_profile: SegmentationProfile,
    *,
    refine: bool = True,
    daemon_mode: str = "auto",
    progress: TranscriptionProgress | None = None,
    # ... other params
) -> TranscriptionResult:
    """Main transcription workflow with progress tracking."""
    
    # Create default progress if not provided
    if progress is None: 
        progress = TranscriptionProgress(mode="rich")
    
    with progress:
        # Stage 1: Decode
        progress.start_stage("decode", "Decoding audio to WAV...", total=None)
        decoded_path = decode_component.decode(source.path, output_dir=artifact_dir)
        progress.complete_stage("✓ Audio decoded")
        
        # Stage 2: VAD
        progress. start_stage("vad", "Detecting speech segments...", total=None)
        timestamps = vad_component.detect_speech(decoded_path)
        progress.complete_stage(f"✓ Found {len(timestamps)} speech segments")
        
        # Stage 3: Condense
        progress.start_stage("condense", "Condensing audio...", total=None)
        condensed_paths = condenser.condense(decoded_path, timestamps, segmentation_profile)
        progress.complete_stage(f"✓ Audio split into {len(condensed_paths)} chunks")
        
        # Stage 4: Transcribe
        progress.start_stage(
            "transcribe",
            f"Transcribing {len(condensed_paths)} chunks...",
            total=None,  # Indeterminate (batch is atomic)
        )
        
        # Use daemon or direct engine
        if daemon_mode in ["auto", "always"]:
            all_segments = transcribe_via_daemon(condensed_paths, ...)
            if all_segments is None and daemon_mode == "always":
                # Daemon required but unavailable
                raise DaemonError("Daemon not available")
        else:
            all_segments = transcribe_direct(condensed_paths, engine_profile)
        
        progress.complete_stage("✓ Transcription complete")
        
        # Stage 5: Refinement (if enabled)
        if refine:
            progress.start_stage("refine", "Refining transcript...", total=None)
            raw_text = "\n".join(seg.text for seg in all_segments)
            refined_text = refine_via_daemon(raw_text) if daemon_mode != "never" else refine_direct(raw_text)
            all_segments = apply_refinement(all_segments, refined_text)
            progress.complete_stage("✓ Transcript refined")
        
        progress.print("✓ Transcription complete", style="bold green")
    
    return TranscriptionResult(segments=all_segments, ...)
```

**Do this for ALL workflow functions:**
- `transcribe_file_workflow()`
- `batch_transcribe_workflow()` (if it exists)
- Any other functions that use progress

---

#### Step 1.4: Update CLI to Use New Progress API

**File:** `vociferous/cli/main.py` (UPDATE)

Ensure CLI creates progress with `mode="rich"`:

```python
@app.command("transcribe")
def transcribe_cmd(
    audio:  Path,
    verbose: bool = typer.Option(True, help="Show progress"),
    # ... other params
):
    """Transcribe audio file."""
    
    # Create Rich progress for CLI
    progress = TranscriptionProgress(mode="rich" if verbose else "silent")
    
    result = transcribe_file_workflow(
        source=FileSource(audio),
        engine_profile=engine_profile,
        segmentation_profile=segmentation_profile,
        progress=progress,
        # ... other params
    )
    
    # Display result
    typer.echo(result.text)
```

---

#### Step 1.5: Add Tests for Progress Callback Mode

**File:** `tests/app/test_progress_callbacks.py` (NEW)

```python
"""Tests for progress callback system (GUI mode)."""

import pytest
from pathlib import Path
from vociferous.app.progress import TranscriptionProgress
from vociferous.domain.protocols import ProgressUpdateData


def test_progress_callback_mode_basic():
    """Test basic callback mode operation."""
    updates = []
    
    def callback(update:  ProgressUpdateData):
        updates.append(update)
    
    progress = TranscriptionProgress(mode="callback", callback=callback)
    
    with progress:
        progress.start_stage("test", "Testing...", total=100)
        progress.update_stage(progress=0.5, message="Halfway")
        progress.complete_stage("Done")
    
    # Verify we got updates
    assert len(updates) == 3
    assert updates[0].stage == "test"
    assert updates[0].progress == 0.0
    assert updates[1].progress == 0.5
    assert updates[2].progress == 1.0


def test_progress_callback_mode_requires_callback():
    """Test that callback mode requires callback parameter."""
    with pytest.raises(ValueError, match="callback parameter required"):
        TranscriptionProgress(mode="callback", callback=None)


def test_progress_callback_indeterminate():
    """Test indeterminate progress (no total)."""
    updates = []
    
    def callback(update: ProgressUpdateData):
        updates.append(update)
    
    progress = TranscriptionProgress(mode="callback", callback=callback)
    
    with progress:
        progress.start_stage("test", "Processing...", total=None)
        progress.update_stage(message="Still processing...")
        progress.complete_stage()
    
    # Progress should be None for indeterminate
    assert updates[0].progress is None
    assert updates[1].progress is None
    assert updates[2]. progress == 1.0  # Complete is always 1.0


def test_progress_silent_mode():
    """Test silent mode produces no output."""
    progress = TranscriptionProgress(mode="silent")
    
    # Should not raise, should not output
    with progress:
        progress.start_stage("test", "Testing...")
        progress.update_stage(progress=0.5)
        progress.complete_stage()


def test_progress_elapsed_time_tracking():
    """Test that elapsed time is tracked."""
    import time
    
    updates = []
    
    def callback(update: ProgressUpdateData):
        updates.append(update)
    
    progress = TranscriptionProgress(mode="callback", callback=callback)
    
    with progress: 
        progress.start_stage("test", "Testing...", total=100)
        time.sleep(0.1)  # Wait a bit
        progress.update_stage(progress=0.5)
        progress.complete_stage()
    
    # Check elapsed time is tracked
    assert updates[0].elapsed_s == 0.0
    assert updates[1].elapsed_s >= 0.1
    assert updates[2].elapsed_s >= 0.1


@pytest.mark.slow
def test_progress_callback_in_real_workflow():
    """Integration test:  Use callback progress in real transcription."""
    from vociferous.app.workflow import transcribe_file_workflow
    from vociferous.sources import FileSource
    from vociferous.config. loader import load_config, get_engine_profile, get_segmentation_profile
    
    updates = []
    stages_seen = set()
    
    def callback(update: ProgressUpdateData):
        updates.append(update)
        stages_seen.add(update.stage)
    
    # Load config
    config = load_config()
    engine_profile = get_engine_profile(config, "default")
    seg_profile = get_segmentation_profile(config, "default")
    
    # Transcribe with callback progress
    audio_path = Path("tests/audio/sample_audio/ASR_Test. flac")
    progress = TranscriptionProgress(mode="callback", callback=callback)
    
    result = transcribe_file_workflow(
        source=FileSource(audio_path),
        engine_profile=engine_profile,
        segmentation_profile=seg_profile,
        progress=progress,
        refine=False,  # Skip refinement for speed
    )
    
    # Verify stages were tracked
    assert "decode" in stages_seen
    assert "vad" in stages_seen
    assert "condense" in stages_seen
    assert "transcribe" in stages_seen
    
    # Verify we got updates
    assert len(updates) > 0
    
    # Verify result is valid
    assert result.text
    assert len(result.segments) > 0
```

**Run tests:**
```bash
pytest tests/app/test_progress_callbacks.py -v
```

---

#### Step 1.6: Update Documentation

**File:** `docs/ARCHITECTURE.md` (UPDATE)

Add section under "App Module":

```markdown
### Progress Tracking

Vociferous supports three progress tracking modes:

1. **Rich Mode (CLI):**  Uses Rich library for beautiful terminal progress bars
2. **Callback Mode (GUI):** Calls a callback function with progress updates
3. **Silent Mode (Tests):** No output

**Example:  CLI Usage**
```python
from vociferous.app.progress import TranscriptionProgress

progress = TranscriptionProgress(mode="rich")
with progress:
    progress.start_stage("decode", "Decoding audio...", total=None)
    # ... work ...
    progress.complete_stage("✓ Decoded")
```

**Example: GUI Usage**
```python
def update_gui(update: ProgressUpdateData):
    # Update GUI widgets
    progress_bar.value = update.progress or 0
    status_label. text = update.message

progress = TranscriptionProgress(mode="callback", callback=update_gui)
with progress:
    progress. start_stage("decode", "Decoding audio...", total=None)
    # ... work ...
    progress.complete_stage("✓ Decoded")
```

**ProgressUpdateData Structure:**
- `stage`: Stage identifier (e.g., "decode", "vad", "transcribe")
- `progress`: Float from 0.0 to 1.0, or None for indeterminate
- `message`: Human-readable status message
- `elapsed_s`: Optional elapsed time in seconds
- `remaining_s`: Optional estimated remaining time
```

---

### Acceptance Criteria for Task 1

- [ ] `ProgressCallback` protocol defined in `domain/protocols.py`
- [ ] `TranscriptionProgress` supports three modes:  `rich`, `callback`, `silent`
- [ ] All workflow functions use new progress API
- [ ] CLI still works with Rich progress bars
- [ ] Tests pass with callback mode
- [ ] Documentation updated
- [ ] MyPy strict passes
- [ ] Integration test with real transcription works

---

## 🎯 Task 2: Error Serialization for GUI

### Problem Statement

Current errors use Rich formatting for CLI: 
```python
class VociferousError(Exception):
    def format_rich(self) -> Panel:
        # Returns Rich Panel - GUI can't use this
```

GUI needs **structured error data** for displaying in dialogs: 
```python
{
    "title": "Transcription Failed",
    "message": "FFmpeg failed to decode audio file",
    "details": {"file": "/path/audio.mp3", "exit_code": 1},
    "suggestions": ["Install ffmpeg", "Check file is valid"]
}
```

---

### Implementation Plan

#### Step 2.1: Add Error Serialization Method

**File:** `vociferous/domain/exceptions.py` (UPDATE)

Add `to_dict()` method to base `VociferousError` class:

```python
"""Exception hierarchy with rich error context."""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

__all__ = [
    "VociferousError",
    "AudioDecodeError",
    "VADError",
    "UnsplittableSegmentError",
    "TranscriptionError",
    "RefinementError",
    "DaemonError",
    "DependencyError",
    "ConfigurationError",
]


class VociferousError(Exception):
    """Base exception with rich error context and serialization."""
    
    def __init__(
        self,
        message: str,
        *,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ):
        """Initialize error with context. 
        
        Args:
            message: Human-readable error message
            context:  Additional context (file paths, durations, etc.)
            suggestions: List of actionable suggestions for user
            cause: Original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.suggestions = suggestions or []
        self. cause = cause
        self.timestamp = datetime.now()
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize error to dictionary for GUI/API consumption. 
        
        Returns:
            Dictionary with error details: 
                - error_type: Exception class name
                - message: Human-readable error message
                - context: Additional context dict
                - suggestions: List of actionable suggestions
                - timestamp: ISO 8601 timestamp
                - cause:  Stringified cause exception (if any)
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self. message,
            "context": self.context,
            "suggestions":  self.suggestions,
            "timestamp": self.timestamp.isoformat(),
            "cause": str(self.cause) if self.cause else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VociferousError:
        """Deserialize error from dictionary (for logging/testing).
        
        Args:
            data: Error dictionary from to_dict()
        
        Returns:
            VociferousError instance
        """
        return cls(
            message=data["message"],
            context=data.get("context"),
            suggestions=data.get("suggestions"),
        )
    
    def format_rich(self) -> Panel:
        """Format error as Rich Panel for CLI display."""
        output = Text()
        output.append("✗ Error:  ", style="bold red")
        output.append(self.message)
        
        # Context information
        if self.context:
            output.append("\n\nDetails:\n", style="bold")
            for key, value in self.context.items():
                output.append(f"  • {key}: {value}\n")
        
        # Suggestions
        if self.suggestions:
            output.append("\nPossible solutions:\n", style="bold yellow")
            for i, suggestion in enumerate(self.suggestions, 1):
                output. append(f"  {i}. {suggestion}\n", style="yellow")
        
        # Root cause
        if self.cause:
            output.append(f"\nCaused by: {type(self.cause).__name__}: {self.cause}\n", style="dim")
        
        return Panel(output, border_style="red", title="[bold]Error[/bold]")


# ...  rest of exception classes remain the same ...
```

**Add to all specific error classes** (AudioDecodeError, VADError, etc.):

No changes needed - they inherit `to_dict()` and `format_rich()` automatically.

---

#### Step 2.2: Add Error JSON Schema for Documentation

**File:** `vociferous/domain/error_schema.py` (NEW)

```python
"""JSON schema for error serialization (documentation)."""

from typing import TypedDict, NotRequired

__all__ = ["ErrorDict"]


class ErrorDict(TypedDict):
    """Type definition for serialized error dictionary. 
    
    This documents the structure returned by VociferousError.to_dict()
    for GUI and API consumers.
    """
    
    error_type: str
    """Exception class name (e.g., 'AudioDecodeError')."""
    
    message: str
    """Human-readable error message."""
    
    context: dict[str, str | int | float | bool]
    """Additional context (file paths, durations, error codes, etc.)."""
    
    suggestions: list[str]
    """List of actionable suggestions for user."""
    
    timestamp: str
    """ISO 8601 timestamp when error occurred."""
    
    cause: NotRequired[str | None]
    """Stringified original exception, if any."""
```

---

#### Step 2.3: Add GUI Error Display Helper

**File:** `vociferous/gui/errors.py` (NEW - for future GUI use)

```python
"""Error display helpers for GUI dialogs. 

This module will be used by GUI code to display errors in dialogs. 
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vociferous.domain.exceptions import VociferousError

__all__ = ["format_error_for_dialog"]


def format_error_for_dialog(error: VociferousError) -> dict[str, str]: 
    """Format VociferousError for GUI error dialog display.
    
    Args:
        error: VociferousError instance
    
    Returns:
        Dictionary with formatted strings for dialog: 
            - title: Dialog title
            - message: Main error message
            - details:  Formatted details section
            - suggestions: Formatted suggestions section
    
    Example:
        >>> error = AudioDecodeError. from_ffmpeg_error(...)
        >>> dialog_data = format_error_for_dialog(error)
        >>> show_error_dialog(
        ...     title=dialog_data["title"],
        ...     message=dialog_data["message"],
        ...     details=dialog_data["details"],
        ...  )
    """
    # Format title
    error_name = error.__class__.__name__. replace("Error", "")
    title = f"{error_name} Error"
    
    # Main message
    message = error.message
    
    # Format context details
    details_lines = []
    if error.context:
        for key, value in error.context.items():
            # Format key:  remove underscores, capitalize
            formatted_key = key.replace("_", " ").title()
            details_lines.append(f"{formatted_key}: {value}")
    details = "\n".join(details_lines) if details_lines else None
    
    # Format suggestions
    suggestions_lines = []
    if error.suggestions:
        for i, suggestion in enumerate(error.suggestions, 1):
            suggestions_lines.append(f"{i}. {suggestion}")
    suggestions = "\n".join(suggestions_lines) if suggestions_lines else None
    
    return {
        "title": title,
        "message": message,
        "details": details or "",
        "suggestions": suggestions or "",
    }
```

---

#### Step 2.4: Add Tests for Error Serialization

**File:** `tests/domain/test_error_serialization.py` (NEW)

```python
"""Tests for error serialization (to_dict/from_dict)."""

import pytest
from datetime import datetime
from vociferous.domain.exceptions import (
    VociferousError,
    AudioDecodeError,
    VADError,
    DaemonError,
)


def test_error_to_dict_basic():
    """Test basic error serialization."""
    error = VociferousError(
        "Test error",
        context={"file":  "/path/test.mp3", "duration": 120.5},
        suggestions=["Try this", "Or this"],
    )
    
    data = error.to_dict()
    
    assert data["error_type"] == "VociferousError"
    assert data["message"] == "Test error"
    assert data["context"]["file"] == "/path/test. mp3"
    assert data["context"]["duration"] == 120.5
    assert len(data["suggestions"]) == 2
    assert data["suggestions"][0] == "Try this"
    assert "timestamp" in data
    assert data["cause"] is None


def test_error_to_dict_with_cause():
    """Test error serialization with cause exception."""
    original = ValueError("Original error")
    error = VociferousError("Wrapper error", cause=original)
    
    data = error.to_dict()
    
    assert data["cause"] == "Original error"


def test_error_from_dict_roundtrip():
    """Test error can be deserialized from dict."""
    original = VociferousError(
        "Test error",
        context={"key": "value"},
        suggestions=["Suggestion"],
    )
    
    # Serialize then deserialize
    data = original.to_dict()
    restored = VociferousError.from_dict(data)
    
    assert restored.message == original. message
    assert restored.context == original.context
    assert restored. suggestions == original.suggestions


def test_audio_decode_error_serialization():
    """Test specific error type serialization."""
    error = AudioDecodeError. from_ffmpeg_error(
        audio_path=Path("/path/test.mp3"),
        returncode=1,
        stderr="ffmpeg:  error",
    )
    
    data = error.to_dict()
    
    assert data["error_type"] == "AudioDecodeError"
    assert "test.mp3" in data["message"]
    assert data["context"]["file"] == "/path/test. mp3"
    assert data["context"]["ffmpeg_exit_code"] == 1
    assert len(data["suggestions"]) > 0


def test_vad_error_serialization():
    """Test VAD error serialization."""
    error = VADError.no_speech_detected(
        audio_path=Path("/path/silent.wav"),
        audio_duration_s=30.0,
        threshold=0.5,
    )
    
    data = error. to_dict()
    
    assert data["error_type"] == "VADError"
    assert "No speech detected" in data["message"]
    assert data["context"]["duration"] == "30.0s"
    assert data["context"]["vad_threshold"] == 0.5
    assert any("--vad-threshold" in s for s in data["suggestions"])


def test_error_timestamp_format():
    """Test timestamp is ISO 8601 format."""
    error = VociferousError("Test")
    data = error.to_dict()
    
    # Should be parseable as ISO 8601
    timestamp = datetime.fromisoformat(data["timestamp"])
    assert isinstance(timestamp, datetime)


def test_gui_error_formatting():
    """Test error formatting for GUI dialogs."""
    from vociferous.gui.errors import format_error_for_dialog
    
    error = AudioDecodeError(
        "Failed to decode audio file",
        context={"file":  "/path/test.mp3", "exit_code": 1},
        suggestions=["Install ffmpeg", "Check file format"],
    )
    
    dialog_data = format_error_for_dialog(error)
    
    assert dialog_data["title"] == "AudioDecode Error"
    assert dialog_data["message"] == "Failed to decode audio file"
    assert "File: /path/test.mp3" in dialog_data["details"]
    assert "1.  Install ffmpeg" in dialog_data["suggestions"]
```

**Run tests:**
```bash
pytest tests/domain/test_error_serialization.py -v
```

---

#### Step 2.5: Update CLI Error Handler to Use Serialization

**File:** `vociferous/cli/main.py` (UPDATE)

Update error handler to use `format_rich()`:

```python
def main():
    """Main CLI entry point with error handling."""
    try:
        app()
    except VociferousError as e: 
        # Use Rich formatted error
        console = Console()
        console.print(e.format_rich())
        
        # Also log as JSON for debugging (optional)
        import json
        import logging
        logger = logging.getLogger("vociferous")
        logger.debug(f"Error details: {json.dumps(e.to_dict(), indent=2)}")
        
        raise typer.Exit(1)
    
    except KeyboardInterrupt:
        console = Console()
        console.print("\n⚠️  Operation cancelled by user", style="yellow")
        raise typer.Exit(130)
    
    except Exception as e:
        # Unexpected error
        console = Console()
        if os.getenv("VOCIFEROUS_VERBOSE"):
            console.print_exception()
        else:
            console. print(f"[red]✗ Unexpected error: {e}[/red]")
            console.print("[dim]Run with VOCIFEROUS_VERBOSE=1 for full traceback[/dim]")
        raise typer.Exit(1)
```

---

### Acceptance Criteria for Task 2

- [ ] `to_dict()` method added to `VociferousError`
- [ ] `from_dict()` classmethod added for deserialization
- [ ] All specific error types inherit serialization
- [ ] `ErrorDict` TypedDict documents schema
- [ ] `format_error_for_dialog()` helper exists for GUI
- [ ] Tests for serialization/deserialization pass
- [ ] CLI error handler uses `format_rich()`
- [ ] Documentation updated
- [ ] MyPy strict passes

---

## 🎯 Task 3: Audio File Validation

### Problem Statement

Currently, audio file errors happen **during transcription** (after decode/VAD start), not upfront. GUI users need to know immediately if a file is invalid. 

**Current flow:**
```
User drops file → Start transcription → 10 seconds later → Error:  "Invalid format"
```

**Desired flow:**
```
User drops file → Validate → Show error dialog OR show file info → User clicks transcribe
```

---

### Implementation Plan

#### Step 3.1: Create Audio Validation Module

**File:** `vociferous/audio/validation.py` (NEW)

```python
"""Audio file validation and metadata extraction."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vociferous.domain.exceptions import AudioDecodeError

__all__ = [
    "AudioFileInfo",
    "validate_audio_file",
    "is_supported_format",
]


@dataclass
class AudioFileInfo:
    """Metadata about an audio file."""
    
    path: Path
    """Path to audio file."""
    
    duration_s: float
    """Duration in seconds."""
    
    sample_rate: int
    """Sample rate in Hz (e.g., 16000, 44100)."""
    
    channels: int
    """Number of audio channels (1=mono, 2=stereo)."""
    
    codec: str
    """Audio codec (e.g., 'mp3', 'pcm_s16le', 'flac')."""
    
    bitrate_kbps: int | None
    """Bitrate in kbps, if available."""
    
    format: str
    """Container format (e.g., 'mp3', 'wav', 'flac')."""
    
    file_size_mb: float
    """File size in megabytes."""
    
    def __str__(self) -> str:
        """Human-readable file info."""
        return (
            f"{self.path.name}\n"
            f"  Duration: {self.duration_s:.1f}s\n"
            f"  Format: {self.format. upper()}\n"
            f"  Codec: {self.codec}\n"
            f"  Sample Rate: {self.sample_rate} Hz\n"
            f"  Channels: {self.channels}\n"
            f"  Size: {self.file_size_mb:.2f} MB"
        )


def validate_audio_file(path: Path) -> AudioFileInfo:
    """Validate audio file and extract metadata.
    
    Args:
        path: Path to audio file
    
    Returns:
        AudioFileInfo with metadata
    
    Raises:
        AudioDecodeError: If file doesn't exist, isn't audio, or is invalid
    
    Example:
        >>> info = validate_audio_file(Path("audio.mp3"))
        >>> print(f"Duration: {info.duration_s:.1f}s")
        Duration: 180.5s
    """
    # Check file exists
    if not path.exists():
        raise AudioDecodeError(
            f"Audio file not found:  {path.name}",
            context={"file": str(path)},
            suggestions=[
                "Check the file path is correct",
                "Ensure the file hasn't been moved or deleted",
            ],
        )
    
    # Check file is readable
    if not path.is_file():
        raise AudioDecodeError(
            f"Path is not a file: {path.name}",
            context={"file": str(path)},
            suggestions=["Ensure the path points to a file, not a directory"],
        )
    
    # Use ffprobe to get metadata
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise AudioDecodeError(
            f"Failed to read audio file: {path.name}",
            context={"file": str(path), "exit_code": e.returncode},
            suggestions=[
                "File may be corrupted - try playing it with VLC",
                "File may not be a valid audio format",
                "Install ffmpeg if not already installed:  sudo apt install ffmpeg",
            ],
        ) from e
    except FileNotFoundError:
        raise AudioDecodeError(
            "ffmpeg/ffprobe not found",
            suggestions=[
                "Install ffmpeg:  sudo apt install ffmpeg (Linux)",
                "Install ffmpeg: brew install ffmpeg (macOS)",
                "Download from https://ffmpeg.org/download.html (Windows)",
            ],
        )
    
    # Parse JSON output
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AudioDecodeError(
            f"Failed to parse audio metadata: {path.name}",
            context={"file": str(path)},
            suggestions=["File may be corrupted"],
        ) from e
    
    # Find audio stream
    audio_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "audio":
            audio_stream = stream
            break
    
    if not audio_stream:
        raise AudioDecodeError(
            f"No audio stream found in file: {path.name}",
            context={"file": str(path)},
            suggestions=[
                "File may be video-only",
                "File may be corrupted",
                "Try a different file",
            ],
        )
    
    # Extract metadata
    format_info = data.get("format", {})
    
    try:
        duration = float(format_info.get("duration", 0))
        sample_rate = int(audio_stream.get("sample_rate", 0))
        channels = int(audio_stream.get("channels", 0))
        codec = audio_stream.get("codec_name", "unknown")
        bitrate = format_info.get("bit_rate")
        bitrate_kbps = int(bitrate) // 1000 if bitrate else None
        format_name = format_info.get("format_name", "unknown").split(",")[0]
        file_size = path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
    except (ValueError, KeyError) as e:
        raise AudioDecodeError(
            f"Invalid audio metadata: {path.name}",
            context={"file": str(path)},
            suggestions=["File may be corrupted or in an unusual format"],
        ) from e
    
    # Validate basic requirements
    if duration <= 0:
        raise AudioDecodeError(
            f"Audio file has zero duration: {path.name}",
            context={"file": str(path), "duration": duration},
            suggestions=["File may be empty or corrupted"],
        )
    
    if sample_rate == 0:
        raise AudioDecodeError(
            f"Invalid sample rate: {path.name}",
            context={"file":  str(path), "sample_rate": sample_rate},
            suggestions=["File may be corrupted"],
        )
    
    return AudioFileInfo(
        path=path,
        duration_s=duration,
        sample_rate=sample_rate,
        channels=channels,
        codec=codec,
        bitrate_kbps=bitrate_kbps,
        format=format_name,
        file_size_mb=file_size_mb,
    )


def is_supported_format(path: Path) -> bool:
    """Check if file extension is a supported audio format.
    
    This is a quick check before attempting validation with ffprobe.
    
    Args:
        path: Path to audio file
    
    Returns: 
        True if extension is known audio format
    
    Note:
        This is not definitive - files can have wrong extensions.
        Use validate_audio_file() for thorough validation.
    """
    supported_extensions = {
        ".mp3",
        ".wav",
        ". flac",
        ".m4a",
        ".aac",
        ".ogg",
        ".opus",
        ".wma",
        ".aiff",
        ". ape",
        ".wv",
    }
    
    return path. suffix.lower() in supported_extensions
```

---

#### Step 3.2: Add Validation to CLI

**File:** `vociferous/cli/main. py` (UPDATE)

Add validation before transcription:

```python
@app.command("transcribe")
def transcribe_cmd(
    audio:  Path,
    # ... other params
):
    """Transcribe audio file."""
    
    from vociferous.audio.validation import validate_audio_file
    
    # Validate file upfront
    try:
        audio_info = validate_audio_file(audio)
        
        # Show file info if verbose
        if verbose:
            typer.echo(f"\n{audio_info}\n")
    
    except VociferousError as e: 
        # Show error and exit early
        console = Console()
        console.print(e.format_rich())
        raise typer.Exit(1)
    
    # Proceed with transcription
    progress = TranscriptionProgress(mode="rich" if verbose else "silent")
    
    result = transcribe_file_workflow(
        source=FileSource(audio),
        # ... 
    )
    
    typer.echo(result. text)
```

---

#### Step 3.3: Add Validation Tests

**File:** `tests/audio/test_validation.py` (NEW)

```python
"""Tests for audio file validation."""

import pytest
from pathlib import Path
from vociferous.audio.validation import (
    validate_audio_file,
    is_supported_format,
    AudioFileInfo,
)
from vociferous.domain.exceptions import AudioDecodeError


# Use shared sample audio
SAMPLE_AUDIO = Path("tests/audio/sample_audio/ASR_Test. flac")


def test_validate_valid_audio_file():
    """Test validation of valid audio file."""
    info = validate_audio_file(SAMPLE_AUDIO)
    
    assert isinstance(info, AudioFileInfo)
    assert info.path == SAMPLE_AUDIO
    assert info. duration_s > 0
    assert info.sample_rate > 0
    assert info.channels > 0
    assert info.codec
    assert info.format
    assert info.file_size_mb > 0


def test_validate_nonexistent_file():
    """Test validation of nonexistent file raises error."""
    with pytest.raises(AudioDecodeError, match="not found"):
        validate_audio_file(Path("/nonexistent/file.mp3"))


def test_validate_directory_not_file(tmp_path):
    """Test validation of directory raises error."""
    directory = tmp_path / "not_a_file"
    directory. mkdir()
    
    with pytest.raises(AudioDecodeError, match="not a file"):
        validate_audio_file(directory)


def test_validate_empty_file(tmp_path):
    """Test validation of empty file raises error."""
    empty_file = tmp_path / "empty.wav"
    empty_file.touch()
    
    with pytest. raises(AudioDecodeError):
        validate_audio_file(empty_file)


def test_validate_corrupted_file(tmp_path):
    """Test validation of corrupted file raises error."""
    corrupted = tmp_path / "corrupted. mp3"
    corrupted.write_bytes(b"This is not audio data")
    
    with pytest.raises(AudioDecodeError):
        validate_audio_file(corrupted)


def test_is_supported_format():
    """Test supported format detection."""
    assert is_supported_format(Path("audio.mp3"))
    assert is_supported_format(Path("audio.wav"))
    assert is_supported_format(Path("audio.flac"))
    assert is_supported_format(Path("audio.m4a"))
    assert is_supported_format(Path("AUDIO.MP3"))  # Case insensitive
    
    assert not is_supported_format(Path("video.mp4"))
    assert not is_supported_format(Path("document.pdf"))
    assert not is_supported_format(Path("file.txt"))


def test_audio_file_info_str():
    """Test AudioFileInfo string representation."""
    info = validate_audio_file(SAMPLE_AUDIO)
    
    info_str = str(info)
    
    assert SAMPLE_AUDIO.name in info_str
    assert "Duration:" in info_str
    assert "Format:" in info_str
    assert "Sample Rate:" in info_str


def test_validation_error_contains_suggestions():
    """Test validation errors have helpful suggestions."""
    with pytest.raises(AudioDecodeError) as exc_info:
        validate_audio_file(Path("/nonexistent. mp3"))
    
    error = exc_info.value
    assert len(error.suggestions) > 0
    assert any("path" in s. lower() for s in error.suggestions)
```

**Run tests:**
```bash
pytest tests/audio/test_validation. py -v
```

---

### Acceptance Criteria for Task 3

- [ ] `validate_audio_file()` function exists
- [ ] Returns `AudioFileInfo` with all metadata
- [ ] Raises `AudioDecodeError` with context/suggestions
- [ ] `is_supported_format()` quick check exists
- [ ] CLI validates files before transcription
- [ ] Tests cover valid/invalid/corrupted files
- [ ] Documentation updated
- [ ] MyPy strict passes

---

## 🎯 Task 4: Async Daemon Startup

### Problem Statement

GUI cannot block for 16 seconds during daemon startup. Need **asynchronous** daemon initialization with progress callbacks.

**Current flow:**
```python
# This blocks for 16 seconds
daemon_manager.ensure_running(auto_start=True)
```

**Desired flow:**
```python
# This starts daemon in background
task = daemon_manager.start_async(progress_callback=update_gui)
# GUI remains responsive, shows "Loading model...  8s elapsed"
```

---

### Implementation Plan

#### Step 4.1: Add Async Daemon Startup

**File:** `vociferous/server/manager.py` (UPDATE)

Add async methods: 

```python
"""Daemon lifecycle management with async support."""

from __future__ import annotations

import asyncio
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from vociferous.server.client import DaemonClient
from vociferous.domain.exceptions import DaemonError

__all__ = [
    "DaemonManager",
    "ensure_daemon_running",
]


class DaemonManager: 
    """Manages daemon lifecycle with support for async GUI startup."""
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        timeout: float = 60.0,
    ):
        """Initialize daemon manager. 
        
        Args:
            host:  Daemon host (default: localhost)
            port: Daemon port (default: 8765)
            timeout: Startup timeout in seconds (default: 60s for model load)
        """
        self. host = host
        self.port = port
        self.timeout = timeout
        self.client = DaemonClient(host, port)
    
    def is_running(self) -> bool:
        """Check if daemon is currently running."""
        return self.client.ping()
    
    def ensure_running(self, auto_start: bool = True) -> bool:
        """Ensure daemon is running (synchronous).
        
        Args:
            auto_start: If True, start daemon if not running
        
        Returns:
            True if daemon is running, False otherwise
        """
        if self.is_running():
            return True
        
        if not auto_start:
            return False
        
        # Start daemon synchronously
        self.start_daemon_sync()
        return self.is_running()
    
    def start_daemon_sync(self) -> None:
        """Start daemon and wait for it to be ready (blocks for ~16s).
        
        Raises:
            DaemonError: If daemon fails to start within timeout
        """
        # Start daemon process
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "vociferous.server.api:app",
                "--host", self.host,
                "--port", str(self.port),
                "--log-level", "error",  # Quiet startup
            ],
            stdout=subprocess. DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        
        # Write PID file
        from vociferous.cli.commands. daemon import _write_pid_file
        _write_pid_file(proc. pid)
        
        # Wait for health check
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            time.sleep(1)
            if self.is_running():
                return
        
        # Timeout - daemon didn't start
        proc.kill()
        raise DaemonError(f"Daemon failed to start within {self.timeout}s")
    
    def start_async(
        self,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> threading.Thread:
        """Start daemon asynchronously in background thread (non-blocking).
        
        This is designed for GUI use where blocking the main thread is unacceptable.
        
        Args:
            progress_callback:  Optional callback for progress updates
                Called with (message, elapsed_seconds)
        
        Returns:
            Thread object (already started)
        
        Example:
            >>> def update_gui(msg, elapsed):
            ...     status_label.text = f"{msg} ({elapsed:.0f}s)"
            >>> 
            >>> manager = DaemonManager()
            >>> thread = manager.start_async(progress_callback=update_gui)
            >>> # GUI remains responsive
            >>> thread. join()  # Wait for completion if needed
        """
        def start_with_progress():
            """Background thread function."""
            start_time = time.time()
            
            if progress_callback:
                progress_callback("Starting daemon.. .", 0.0)
            
            # Start daemon process
            proc = subprocess.Popen(
                [
                    sys.executable, "-m", "uvicorn",
                    "vociferous.server.api:app",
                    "--host", self.host,
                    "--port", str(self.port),
                    "--log-level", "error",
                ],
                stdout=subprocess. DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            
            # Write PID file
            from vociferous.cli.commands.daemon import _write_pid_file
            _write_pid_file(proc.pid)
            
            if progress_callback:
                progress_callback("Loading model.. .", time.time() - start_time)
            
            # Poll until ready
            while time.time() - start_time < self.timeout:
                time. sleep(1)
                elapsed = time.time() - start_time
                
                if self. is_running():
                    if progress_callback:
                        progress_callback("✓ Daemon ready", elapsed)
                    return
                
                if progress_callback:
                    progress_callback(f"Loading model.. .", elapsed)
            
            # Timeout
            proc.kill()
            if progress_callback:
                progress_callback("✗ Daemon failed to start", time.time() - start_time)
        
        # Start in background thread
        thread = threading. Thread(target=start_with_progress, daemon=True)
        thread.start()
        return thread
    
    def stop(self) -> None:
        """Stop daemon gracefully."""
        from vociferous.cli.commands. daemon import stop_daemon
        stop_daemon()


def ensure_daemon_running(
    auto_start: bool = True,
    progress_callback:  Callable[[str, float], None] | None = None,
) -> bool:
    """Convenience function to ensure daemon is running. 
    
    Args:
        auto_start: If True, start daemon if not running
        progress_callback: Optional callback for async startup progress
    
    Returns:
        True if daemon is running, False otherwise
    
    Example:
        >>> if ensure_daemon_running(auto_start=True):
        ...     # Use daemon
        ...     segments = transcribe_via_daemon(audio_path)
    """
    manager = DaemonManager()
    
    if manager.is_running():
        return True
    
    if not auto_start:
        return False
    
    if progress_callback:
        # Async startup with progress
        thread = manager.start_async(progress_callback)
        thread.join()  # Wait for completion
    else: 
        # Sync startup
        manager.start_daemon_sync()
    
    return manager.is_running()
```

---

#### Step 4.2: Update Workflow to Support Async Daemon

**File:** `vociferous/app/workflow.py` (UPDATE)

Add parameter for daemon manager:

```python
def transcribe_file_workflow(
    source: Source,
    engine_profile: EngineProfile,
    segmentation_profile: SegmentationProfile,
    *,
    refine: bool = True,
    daemon_mode: str = "auto",
    daemon_manager: DaemonManager | None = None,  # NEW: Allow injection
    progress:  TranscriptionProgress | None = None,
    # ... other params
) -> TranscriptionResult:
    """Main transcription workflow. 
    
    Args:
        daemon_manager: Optional DaemonManager instance (for GUI use)
            If provided, this will be used instead of creating a new one. 
            Allows GUI to control daemon lifecycle and get startup progress.
    """
    # Create default daemon manager if not provided
    if daemon_manager is None and daemon_mode != "never":
        daemon_manager = DaemonManager()
    
    # Rest of workflow as before
    with progress or TranscriptionProgress():
        # Ensure daemon is running if needed
        if daemon_mode == "always" and daemon_manager: 
            if not daemon_manager. is_running():
                # Try to start (this may have already been done by GUI)
                daemon_manager.ensure_running(auto_start=True)
        
        # ... rest of transcription workflow ... 
```

---

#### Step 4.3: Add Tests for Async Startup

**File:** `tests/server/test_daemon_async.py` (NEW)

```python
"""Tests for async daemon startup."""

import pytest
import time
import threading
from vociferous.server.manager import DaemonManager


@pytest.mark.slow
def test_daemon_start_async_non_blocking():
    """Test that async startup doesn't block."""
    manager = DaemonManager()
    
    # Track if callback was called
    callbacks = []
    
    def progress_callback(msg:  str, elapsed: float):
        callbacks.append((msg, elapsed))
    
    # Start async (should return immediately)
    start_time = time.time()
    thread = manager.start_async(progress_callback=progress_callback)
    call_time = time.time() - start_time
    
    # Should return in < 1 second (not wait for 16s model load)
    assert call_time < 1.0
    
    # Thread should be running
    assert thread. is_alive()
    
    # Wait for completion
    thread.join(timeout=60)
    
    # Verify callbacks were called
    assert len(callbacks) > 0
    assert any("Starting" in msg for msg, _ in callbacks)
    assert any("Loading" in msg for msg, _ in callbacks)
    
    # Daemon should be running
    assert manager. is_running()
    
    # Cleanup
    manager.stop()


@pytest.mark.slow
def test_daemon_start_async_progress_updates():
    """Test that progress callback receives updates."""
    manager = DaemonManager()
    
    messages = []
    elapsed_times = []
    
    def progress_callback(msg: str, elapsed: float):
        messages.append(msg)
        elapsed_times. append(elapsed)
    
    # Start async
    thread = manager.start_async(progress_callback=progress_callback)
    thread.join(timeout=60)
    
    # Verify progress updates
    assert len(messages) >= 3  # At least:  Starting, Loading, Ready
    
    # Elapsed time should increase
    assert elapsed_times[-1] > elapsed_times[0]
    
    # Final message should indicate success
    assert "ready" in messages[-1]. lower() or "✓" in messages[-1]
    
    # Cleanup
    manager.stop()


def test_daemon_start_async_without_callback():
    """Test async startup works without callback."""
    manager = DaemonManager()
    
    # Start without callback (should still work)
    thread = manager.start_async(progress_callback=None)
    
    # Should return immediately
    assert thread.is_alive()
    
    # Don't wait for completion in this test
    # (cleanup will happen in other tests)
```

---

### Acceptance Criteria for Task 4

- [ ] `start_async()` method added to `DaemonManager`
- [ ] Returns immediately (doesn't block for 16s)
- [ ] Calls progress callback with updates
- [ ] `ensure_daemon_running()` supports callbacks
- [ ] Workflow accepts optional `daemon_manager` injection
- [ ] Tests verify non-blocking behavior
- [ ] Tests verify progress callbacks work
- [ ] Documentation updated

---

## 🎯 Task 5: Config Schema for GUI

### Problem Statement

GUI needs to expose configuration options to users (engine selection, preprocessing presets, language, etc.). Current config system works for CLI but needs: 
1. **Friendly validation errors** (not Pydantic's technical messages)
2. **Enum/choice descriptions** for dropdowns
3. **Default value documentation** for UI hints
4. **Schema introspection** for auto-generating settings panels

**Current state:**
```python
# Pydantic validation error (technical)
ValidationError: 1 validation error for EngineConfig
compute_type
  Input should be 'float32', 'float16', or 'int8' (type=literal_error)
```

**Desired for GUI:**
```python
# User-friendly error
{
    "field": "compute_type",
    "message":  "Invalid precision type",
    "help": "Choose:  FP32 (highest quality), FP16 (balanced), or INT8 (fastest)",
    "valid_options": ["float32", "float16", "int8"]
}
```

---

### Implementation Plan

#### Step 5.1: Add User-Friendly Field Metadata

**File:** `vociferous/domain/model. py` (UPDATE)

Add field metadata using Pydantic's `Field()` with descriptions:

```python
"""Domain models with GUI-friendly metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from pydantic import Field, field_validator

__all__ = [
    "EngineProfile",
    "SegmentationProfile",
]


@dataclass
class EngineProfile:
    """Engine configuration with user-friendly descriptions."""
    
    engine_name: str = Field(
        default="canary_qwen",
        description="ASR engine to use",
        json_schema_extra={
            "choices": ["canary_qwen", "whisper_turbo"],
            "choice_labels": {
                "canary_qwen": "Canary-Qwen (High Quality, CUDA only)",
                "whisper_turbo": "Whisper Turbo (Fast, CPU/CUDA)",
            },
            "help": "Canary-Qwen provides best quality but requires NVIDIA GPU.  Whisper Turbo is faster and works on CPU.",
        },
    )
    
    model_name: str | None = Field(
        default=None,
        description="Specific model variant",
        json_schema_extra={
            "help": "Leave blank to use default model for selected engine",
        },
    )
    
    device: str = Field(
        default="cuda",
        description="Compute device",
        json_schema_extra={
            "choices": ["cuda", "cpu"],
            "choice_labels": {
                "cuda":  "GPU (NVIDIA CUDA)",
                "cpu": "CPU (slower)",
            },
            "help": "GPU is 10-100x faster than CPU for transcription",
        },
    )
    
    compute_type: str = Field(
        default="float16",
        description="Precision type",
        json_schema_extra={
            "choices": ["float32", "float16", "bfloat16", "int8"],
            "choice_labels": {
                "float32": "FP32 (Highest Quality, Slowest)",
                "float16": "FP16 (Balanced - Recommended)",
                "bfloat16": "BF16 (Canary-Qwen optimized)",
                "int8":  "INT8 (Fastest, Lower Quality)",
            },
            "help": "Lower precision is faster but may reduce accuracy.  FP16 is recommended for most users.",
        },
    )
    
    language: str = Field(
        default="en",
        description="Target language",
        json_schema_extra={
            "help": "Language of the audio content.  Use 'en' for English, 'es' for Spanish, etc.",
        },
    )
    
    batch_size: int = Field(
        default=1,
        ge=1,
        le=16,
        description="Inference batch size",
        json_schema_extra={
            "help": "Higher batch sizes use more GPU memory but can be faster.  Start with 1 and increase if you have VRAM to spare.",
            "slider":  {"min": 1, "max":  16, "step": 1},
        },
    )


@dataclass
class SegmentationProfile:
    """VAD and chunking configuration with user-friendly descriptions."""
    
    # VAD parameters
    threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="VAD sensitivity",
        json_schema_extra={
            "help": "Lower values detect quieter speech but may include background noise. Higher values require clearer speech.",
            "slider": {"min": 0.0, "max": 1.0, "step": 0.05},
            "presets": {
                "sensitive": 0.3,
                "balanced": 0.5,
                "strict": 0.7,
            },
        },
    )
    
    min_silence_ms: int = Field(
        default=500,
        ge=100,
        le=2000,
        description="Minimum silence duration (ms)",
        json_schema_extra={
            "help": "Shorter values detect pauses faster but may split mid-sentence. Longer values wait for clearer breaks.",
            "slider": {"min": 100, "max": 2000, "step": 100},
        },
    )
    
    min_speech_ms: int = Field(
        default=250,
        ge=100,
        le=2000,
        description="Minimum speech duration (ms)",
        json_schema_extra={
            "help": "Filters out very short sounds like coughs or clicks. Lower values capture brief words.",
            "slider": {"min": 100, "max": 2000, "step": 50},
        },
    )
    
    # Chunking parameters
    max_chunk_s: float = Field(
        default=60.0,
        ge=10.0,
        le=120.0,
        description="Maximum chunk duration (seconds)",
        json_schema_extra={
            "help": "Audio is split into chunks to fit engine limits. 60s is optimal for Canary-Qwen.",
            "slider": {"min": 10.0, "max": 120.0, "step": 5.0},
        },
    )
    
    min_gap_for_split_s: float = Field(
        default=3.0,
        ge=0.5,
        le=10.0,
        description="Natural split gap threshold (seconds)",
        json_schema_extra={
            "help":  "Prefers splitting at silences longer than this.  Smaller values split more aggressively.",
            "slider":  {"min": 0.5, "max": 10.0, "step": 0.5},
        },
    )
```

**Key additions:**
- ✅ `description` for field purpose
- ✅ `json_schema_extra` with GUI hints: 
  - `choices`: Valid options
  - `choice_labels`: Human-readable names for dropdown
  - `help`: Detailed explanation for tooltips
  - `slider`: Range/step for sliders
  - `presets`: Common preset values

---

#### Step 5.2: Create Config Schema Extractor

**File:** `vociferous/gui/config_schema.py` (NEW)

```python
"""Config schema extraction for GUI auto-generation."""

from __future__ import annotations

from typing import Any, Literal, get_args, get_origin
from dataclasses import fields, is_dataclass
from pydantic import Field
from pydantic.fields import FieldInfo

__all__ = [
    "ConfigFieldSchema",
    "extract_config_schema",
    "get_field_metadata",
]


class ConfigFieldSchema:
    """Metadata about a config field for GUI rendering."""
    
    def __init__(
        self,
        name: str,
        type: str,
        default: Any,
        description: str = "",
        required: bool = False,
        choices: list[Any] | None = None,
        choice_labels: dict[Any, str] | None = None,
        help_text: str = "",
        widget_type: Literal["text", "number", "slider", "dropdown", "checkbox"] = "text",
        widget_params: dict[str, Any] | None = None,
    ):
        self.name = name
        self.type = type
        self.default = default
        self.description = description
        self. required = required
        self.choices = choices or []
        self.choice_labels = choice_labels or {}
        self.help_text = help_text
        self.widget_type = widget_type
        self. widget_params = widget_params or {}
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON/GUI consumption."""
        return {
            "name": self.name,
            "type": self.type,
            "default": self.default,
            "description": self.description,
            "required": self. required,
            "choices": self.choices,
            "choice_labels": self.choice_labels,
            "help_text": self.help_text,
            "widget_type": self.widget_type,
            "widget_params": self.widget_params,
        }


def extract_config_schema(config_class: type) -> list[ConfigFieldSchema]:
    """Extract GUI schema from config dataclass/Pydantic model. 
    
    Args:
        config_class:  Dataclass or Pydantic model with Field() metadata
    
    Returns:
        List of ConfigFieldSchema for each field
    
    Example:
        >>> from vociferous.domain.model import EngineProfile
        >>> schema = extract_config_schema(EngineProfile)
        >>> for field in schema:
        ...     print(f"{field.name}:  {field.widget_type}")
        engine_name: dropdown
        device: dropdown
        compute_type:  dropdown
        batch_size: slider
    """
    if not is_dataclass(config_class):
        raise ValueError(f"{config_class} is not a dataclass")
    
    field_schemas = []
    
    for field in fields(config_class):
        field_schema = get_field_metadata(
            field.name,
            field.type,
            field.default,
            field. metadata,
        )
        field_schemas.append(field_schema)
    
    return field_schemas


def get_field_metadata(
    field_name: str,
    field_type: type,
    default_value: Any,
    metadata:  dict[str, Any],
) -> ConfigFieldSchema: 
    """Extract metadata from a single field. 
    
    Args:
        field_name: Name of the field
        field_type: Python type annotation
        default_value: Default value
        metadata: Field metadata dict (from Pydantic Field())
    
    Returns:
        ConfigFieldSchema with inferred widget type
    """
    # Extract Pydantic Field metadata if present
    if isinstance(default_value, FieldInfo):
        pydantic_field = default_value
        description = pydantic_field.description or ""
        json_extra = pydantic_field.json_schema_extra or {}
        actual_default = pydantic_field.default
    else:
        description = metadata.get("description", "")
        json_extra = metadata.get("json_schema_extra", {})
        actual_default = default_value
    
    # Extract choices from Literal type
    choices = None
    choice_labels = None
    if get_origin(field_type) is Literal:
        choices = list(get_args(field_type))
    elif "choices" in json_extra: 
        choices = json_extra["choices"]
    
    # Extract choice labels
    if "choice_labels" in json_extra:
        choice_labels = json_extra["choice_labels"]
    
    # Extract help text
    help_text = json_extra.get("help", "")
    
    # Infer widget type
    widget_type = _infer_widget_type(
        field_type,
        choices,
        json_extra,
    )
    
    # Extract widget parameters
    widget_params = {}
    if "slider" in json_extra:
        widget_params = json_extra["slider"]
    
    # Determine if required
    required = actual_default is None or actual_default == Field. Required
    
    return ConfigFieldSchema(
        name=field_name,
        type=str(field_type),
        default=actual_default,
        description=description,
        required=required,
        choices=choices,
        choice_labels=choice_labels,
        help_text=help_text,
        widget_type=widget_type,
        widget_params=widget_params,
    )


def _infer_widget_type(
    field_type: type,
    choices:  list[Any] | None,
    json_extra: dict[str, Any],
) -> Literal["text", "number", "slider", "dropdown", "checkbox"]:
    """Infer appropriate widget type from field metadata."""
    
    # Explicit widget type
    if "widget" in json_extra:
        return json_extra["widget"]
    
    # Dropdown if choices exist
    if choices: 
        return "dropdown"
    
    # Slider if slider params exist
    if "slider" in json_extra:
        return "slider"
    
    # Bool -> checkbox
    if field_type is bool:
        return "checkbox"
    
    # Int/float -> number
    if field_type in (int, float):
        return "number"
    
    # Default to text
    return "text"
```

---

#### Step 5.3: Create User-Friendly Validation Errors

**File:** `vociferous/gui/validation.py` (NEW)

```python
"""User-friendly validation error formatting for GUI."""

from __future__ import annotations

from typing import Any
from pydantic import ValidationError

__all__ = [
    "ValidationErrorForGUI",
    "format_validation_errors",
]


class ValidationErrorForGUI: 
    """User-friendly validation error for GUI display."""
    
    def __init__(
        self,
        field:  str,
        message: str,
        input_value: Any,
        help_text: str = "",
        valid_options: list[Any] | None = None,
    ):
        self.field = field
        self.message = message
        self.input_value = input_value
        self.help_text = help_text
        self.valid_options = valid_options or []
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize for GUI consumption."""
        return {
            "field": self.field,
            "message": self.message,
            "input_value": self.input_value,
            "help_text": self.help_text,
            "valid_options": self.valid_options,
        }


def format_validation_errors(
    validation_error: ValidationError,
) -> list[ValidationErrorForGUI]: 
    """Convert Pydantic ValidationError to GUI-friendly format. 
    
    Args:
        validation_error: Pydantic ValidationError
    
    Returns: 
        List of user-friendly error objects
    
    Example:
        >>> try:
        ...     config = EngineConfig(compute_type="invalid")
        ...  except ValidationError as e:
        ...     errors = format_validation_errors(e)
        ...     for err in errors:
        ...         print(f"{err.field}: {err.message}")
        compute_type: Invalid precision type.  Choose FP32, FP16, or INT8.
    """
    gui_errors = []
    
    for error in validation_error.errors():
        field_path = ". ".join(str(loc) for loc in error["loc"])
        error_type = error["type"]
        input_value = error. get("input")
        
        # Create user-friendly message based on error type
        if error_type == "literal_error":
            # Literal type violation (invalid choice)
            expected = error.get("ctx", {}).get("expected")
            message = f"Invalid value.  Must be one of:  {expected}"
            valid_options = _parse_expected_values(expected)
        
        elif error_type in ("greater_than_equal", "less_than_equal"):
            # Range validation
            limit_value = error.get("ctx", {}).get("ge") or error.get("ctx", {}).get("le")
            if error_type == "greater_than_equal":
                message = f"Value must be at least {limit_value}"
            else: 
                message = f"Value must be at most {limit_value}"
            valid_options = []
        
        elif error_type == "missing":
            message = "This field is required"
            valid_options = []
        
        elif error_type == "string_type":
            message = "Must be text"
            valid_options = []
        
        elif error_type in ("int_type", "float_type"):
            message = "Must be a number"
            valid_options = []
        
        elif error_type == "bool_type":
            message = "Must be true or false"
            valid_options = []
        
        else:
            # Generic fallback
            message = error.get("msg", "Invalid value")
            valid_options = []
        
        gui_error = ValidationErrorForGUI(
            field=field_path,
            message=message,
            input_value=input_value,
            valid_options=valid_options,
        )
        
        gui_errors.append(gui_error)
    
    return gui_errors


def _parse_expected_values(expected_str: str) -> list[str]:
    """Parse expected values from Pydantic error message.
    
    Example:
        >>> _parse_expected_values("'float32', 'float16', or 'int8'")
        ['float32', 'float16', 'int8']
    """
    if not expected_str:
        return []
    
    # Remove quotes and "or"
    cleaned = expected_str.replace("'", "").replace('"', "").replace(" or ", ", ")
    
    # Split by comma
    values = [v.strip() for v in cleaned.split(",")]
    
    return values
```

---

#### Step 5.4: Add Config Presets

**File:** `vociferous/config/presets.py` (NEW)

```python
"""Configuration presets for common use cases."""

from __future__ import annotations

from vociferous.domain.model import EngineProfile, SegmentationProfile

__all__ = [
    "ENGINE_PRESETS",
    "SEGMENTATION_PRESETS",
    "get_engine_preset",
    "get_segmentation_preset",
]


# Engine configuration presets
ENGINE_PRESETS = {
    "balanced": EngineProfile(
        engine_name="canary_qwen",
        device="cuda",
        compute_type="float16",
        batch_size=1,
    ),
    
    "high_quality": EngineProfile(
        engine_name="canary_qwen",
        device="cuda",
        compute_type="bfloat16",
        batch_size=1,
    ),
    
    "fast": EngineProfile(
        engine_name="whisper_turbo",
        device="cuda",
        compute_type="float16",
        batch_size=4,
    ),
    
    "cpu_compatible": EngineProfile(
        engine_name="whisper_turbo",
        device="cpu",
        compute_type="float32",
        batch_size=1,
    ),
}


# Segmentation configuration presets
SEGMENTATION_PRESETS = {
    "balanced": SegmentationProfile(
        threshold=0.5,
        min_silence_ms=500,
        min_speech_ms=250,
        max_chunk_s=60.0,
        min_gap_for_split_s=3.0,
    ),
    
    "sensitive": SegmentationProfile(
        threshold=0.3,
        min_silence_ms=300,
        min_speech_ms=200,
        max_chunk_s=60.0,
        min_gap_for_split_s=2.0,
    ),
    
    "strict": SegmentationProfile(
        threshold=0.7,
        min_silence_ms=700,
        min_speech_ms=300,
        max_chunk_s=60.0,
        min_gap_for_split_s=4.0,
    ),
    
    "fast_split": SegmentationProfile(
        threshold=0.5,
        min_silence_ms=300,
        min_speech_ms=200,
        max_chunk_s=30.0,
        min_gap_for_split_s=1.5,
    ),
}


def get_engine_preset(name: str) -> EngineProfile:
    """Get engine configuration preset by name.
    
    Args:
        name:  Preset name
    
    Returns: 
        EngineProfile
    
    Raises:
        KeyError: If preset doesn't exist
    """
    if name not in ENGINE_PRESETS:
        available = ", ".join(ENGINE_PRESETS.keys())
        raise KeyError(f"Unknown engine preset: {name}. Available: {available}")
    
    return ENGINE_PRESETS[name]


def get_segmentation_preset(name: str) -> SegmentationProfile:
    """Get segmentation configuration preset by name.
    
    Args:
        name: Preset name
    
    Returns:
        SegmentationProfile
    
    Raises:
        KeyError:  If preset doesn't exist
    """
    if name not in SEGMENTATION_PRESETS:
        available = ", ".join(SEGMENTATION_PRESETS.keys())
        raise KeyError(f"Unknown segmentation preset: {name}. Available: {available}")
    
    return SEGMENTATION_PRESETS[name]
```

---

#### Step 5.5: Add Tests for Config Schema

**File:** `tests/gui/test_config_schema.py` (NEW)

```python
"""Tests for config schema extraction."""

import pytest
from vociferous.domain.model import EngineProfile, SegmentationProfile
from vociferous.gui.config_schema import extract_config_schema, ConfigFieldSchema


def test_extract_engine_profile_schema():
    """Test schema extraction from EngineProfile."""
    schema = extract_config_schema(EngineProfile)
    
    # Should have all fields
    field_names = [f.name for f in schema]
    assert "engine_name" in field_names
    assert "device" in field_names
    assert "compute_type" in field_names
    assert "batch_size" in field_names
    
    # Check engine_name field
    engine_field = next(f for f in schema if f.name == "engine_name")
    assert engine_field.widget_type == "dropdown"
    assert engine_field.choices == ["canary_qwen", "whisper_turbo"]
    assert "canary_qwen" in engine_field.choice_labels
    
    # Check batch_size field
    batch_field = next(f for f in schema if f.name == "batch_size")
    assert batch_field.widget_type == "slider"
    assert "min" in batch_field.widget_params
    assert "max" in batch_field.widget_params


def test_extract_segmentation_profile_schema():
    """Test schema extraction from SegmentationProfile."""
    schema = extract_config_schema(SegmentationProfile)
    
    # Check threshold field
    threshold_field = next(f for f in schema if f.name == "threshold")
    assert threshold_field.widget_type == "slider"
    assert threshold_field.default == 0.5
    assert "help" in threshold_field.help_text or threshold_field.help_text
    
    # Check widget params
    assert "min" in threshold_field.widget_params
    assert "max" in threshold_field.widget_params
    assert threshold_field.widget_params["min"] == 0.0
    assert threshold_field.widget_params["max"] == 1.0


def test_config_field_schema_serialization():
    """Test ConfigFieldSchema can be serialized."""
    field = ConfigFieldSchema(
        name="test_field",
        type="str",
        default="default_value",
        description="Test field",
        choices=["a", "b", "c"],
        choice_labels={"a":  "Option A", "b": "Option B"},
        help_text="This is help text",
        widget_type="dropdown",
    )
    
    data = field.to_dict()
    
    assert data["name"] == "test_field"
    assert data["type"] == "str"
    assert data["default"] == "default_value"
    assert data["widget_type"] == "dropdown"
    assert len(data["choices"]) == 3


def test_validation_error_formatting():
    """Test user-friendly validation error formatting."""
    from pydantic import ValidationError
    from vociferous.gui.validation import format_validation_errors
    
    # Create invalid config
    try:
        EngineProfile(compute_type="invalid_type")
    except ValidationError as e:
        errors = format_validation_errors(e)
        
        assert len(errors) > 0
        error = errors[0]
        
        assert error.field == "compute_type"
        assert "Invalid value" in error.message or "Must be one of" in error.message
        assert error.input_value == "invalid_type"


def test_config_presets_exist():
    """Test that config presets are defined."""
    from vociferous.config.presets import (
        ENGINE_PRESETS,
        SEGMENTATION_PRESETS,
        get_engine_preset,
        get_segmentation_preset,
    )
    
    # Check engine presets
    assert "balanced" in ENGINE_PRESETS
    assert "high_quality" in ENGINE_PRESETS
    assert "fast" in ENGINE_PRESETS
    
    # Check segmentation presets
    assert "balanced" in SEGMENTATION_PRESETS
    assert "sensitive" in SEGMENTATION_PRESETS
    assert "strict" in SEGMENTATION_PRESETS
    
    # Check getters work
    engine = get_engine_preset("balanced")
    assert isinstance(engine, EngineProfile)
    
    seg = get_segmentation_preset("balanced")
    assert isinstance(seg, SegmentationProfile)


def test_invalid_preset_raises_error():
    """Test that invalid preset name raises helpful error."""
    from vociferous.config.presets import get_engine_preset
    
    with pytest.raises(KeyError, match="Unknown engine preset"):
        get_engine_preset("nonexistent")
```

---

#### Step 5.6: Update Documentation

**File:** `docs/GUI_CONFIG. md` (NEW)

```markdown
# GUI Configuration System

Vociferous provides a self-describing configuration system designed for GUI auto-generation.

## Schema Extraction

Extract field metadata for rendering settings panels:

```python
from vociferous.gui.config_schema import extract_config_schema
from vociferous.domain.model import EngineProfile

schema = extract_config_schema(EngineProfile)

for field in schema:
    print(f"Field: {field.name}")
    print(f"  Widget:  {field.widget_type}")
    print(f"  Default:  {field.default}")
    print(f"  Help: {field.help_text}")
    
    if field.choices:
        print(f"  Choices:")
        for choice in field.choices:
            label = field.choice_labels.get(choice, choice)
            print(f"    - {choice}: {label}")
```

## Widget Types

Fields are auto-assigned widget types:

- **dropdown**: Fields with `choices` or Literal types
- **slider**:  Numeric fields with `slider` metadata
- **checkbox**: Boolean fields
- **number**: Int/float fields
- **text**:  String fields (default)

## Validation Errors

Convert Pydantic errors to GUI-friendly format:

```python
from pydantic import ValidationError
from vociferous.gui.validation import format_validation_errors

try: 
    profile = EngineProfile(compute_type="invalid")
except ValidationError as e:
    errors = format_validation_errors(e)
    
    for error in errors:
        # Show in GUI error dialog
        show_field_error(
            field=error.field,
            message=error.message,
            help=error.help_text,
        )
```

## Configuration Presets

Built-in presets for common use cases:

```python
from vociferous.config.presets import get_engine_preset, get_segmentation_preset

# Load preset
engine = get_engine_preset("balanced")  # Recommended defaults
seg = get_segmentation_preset("sensitive")  # Detects quiet speech

# Apply to workflow
result = transcribe_file_workflow(
    source=source,
    engine_profile=engine,
    segmentation_profile=seg,
)
```

**Available Engine Presets:**
- `balanced`: Canary-Qwen FP16 (recommended)
- `high_quality`: Canary-Qwen BF16 (best accuracy)
- `fast`: Whisper Turbo with batching
- `cpu_compatible`: Whisper on CPU

**Available Segmentation Presets:**
- `balanced`: Standard settings (0.5 threshold)
- `sensitive`: Detects quiet speech (0.3 threshold)
- `strict`: Only clear speech (0.7 threshold)
- `fast_split`: Smaller chunks for faster processing

## GUI Integration Example

```python
# KivyMD settings screen
class SettingsScreen(MDScreen):
    def build_settings(self):
        # Extract schema
        schema = extract_config_schema(EngineProfile)
        
        # Auto-generate widgets
        for field in schema: 
            if field.widget_type == "dropdown":
                self.add_dropdown(
                    label=field.description,
                    items=field.choice_labels,
                    default=field.default,
                    help=field.help_text,
                )
            elif field. widget_type == "slider": 
                self.add_slider(
                    label=field.description,
                    min=field.widget_params["min"],
                    max=field.widget_params["max"],
                    step=field.widget_params["step"],
                    default=field. default,
                    help=field.help_text,
                )
```
```

---

### Acceptance Criteria for Task 5

- [ ] Field metadata added to `EngineProfile` and `SegmentationProfile`
- [ ] `extract_config_schema()` function works
- [ ] `ConfigFieldSchema` documents widget type, choices, help text
- [ ] `format_validation_errors()` converts Pydantic errors
- [ ] Configuration presets defined
- [ ] Tests for schema extraction pass
- [ ] Documentation created (`docs/GUI_CONFIG.md`)
- [ ] MyPy strict passes

---

## 📊 Summary:  What Opus 4. 5 Should Implement

### Task 1: Progress Callback System (🔴 Critical)
- [ ] Create `vociferous/domain/protocols.py` with `ProgressCallback` protocol
- [ ] Update `vociferous/app/progress.py` to support 3 modes
- [ ] Update `vociferous/app/workflow.py` to use new progress API
- [ ] Update `vociferous/cli/main.py` to create Rich progress
- [ ] Create `tests/app/test_progress_callbacks.py`
- [ ] Update `docs/ARCHITECTURE.md`

### Task 2: Error Serialization (🔴 Critical)
- [ ] Add `to_dict()` and `from_dict()` to `VociferousError`
- [ ] Create `vociferous/domain/error_schema.py` with TypedDict
- [ ] Create `vociferous/gui/errors.py` with `format_error_for_dialog()`
- [ ] Update `vociferous/cli/main.py` error handler
- [ ] Create `tests/domain/test_error_serialization.py`

### Task 3: Audio File Validation (🟡 High)
- [ ] Create `vociferous/audio/validation.py` with `validate_audio_file()`
- [ ] Add `AudioFileInfo` dataclass
- [ ] Add `is_supported_format()` function
- [ ] Update `vociferous/cli/main.py` to validate before transcribe
- [ ] Create `tests/audio/test_validation.py`

### Task 4:  Async Daemon Startup (🟡 High)
- [ ] Add `start_async()` to `DaemonManager`
- [ ] Update `ensure_daemon_running()` to support callbacks
- [ ] Update `vociferous/app/workflow.py` to accept `daemon_manager` injection
- [ ] Create `tests/server/test_daemon_async.py`

### Task 5: Config Schema for GUI (🟡 High)
- [ ] Add field metadata to `EngineProfile` and `SegmentationProfile`
- [ ] Create `vociferous/gui/config_schema.py` with schema extraction
- [ ] Create `vociferous/gui/validation.py` for friendly errors
- [ ] Create `vociferous/config/presets. py` with configuration presets
- [ ] Create `tests/gui/test_config_schema.py`
- [ ] Create `docs/GUI_CONFIG.md`

---

## ✅ Verification Checklist

After Opus 4.5 completes all tasks: 

```bash
# 1. Type checking
mypy vociferous/ --strict
# Expected: Success, no issues

# 2. Run tests
pytest tests/ -x --ignore=tests/integration --ignore=tests/server
# Expected: All pass

# 3. Test CLI still works
vociferous transcribe tests/audio/sample_audio/ASR_Test.flac
# Expected: Clean output, no logging noise

# 4. Test progress callback mode
pytest tests/app/test_progress_callbacks.py -v
# Expected: All pass

# 5. Test error serialization
pytest tests/domain/test_error_serialization.py -v
# Expected: All pass

# 6. Test validation
pytest tests/audio/test_validation.py -v
# Expected: All pass

# 7. Test config schema
pytest tests/gui/test_config_schema.py -v
# Expected: All pass
```

---

## 🎯 Hot Reload for GUI (KivyMD)

Yes, you're correct - GUI should use the daemon by default for hot reload. Here's how:

**File:** `vociferous/gui/main.py` (FUTURE - for reference)

```python
"""KivyMD GUI main entry point."""

from kivy.app import App
from kivymd.app import MDApp
from vociferous.server. manager import DaemonManager

class VociferousApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.daemon_manager = DaemonManager()
    
    def on_start(self):
        """Called when app starts - start daemon with hot reload support."""
        
        # Show loading screen
        self.show_loading_screen()
        
        # Start daemon asynchronously
        def progress_callback(msg, elapsed):
            self.update_loading_screen(msg, elapsed)
        
        thread = self.daemon_manager.start_async(
            progress_callback=progress_callback
        )
        
        # Wait for daemon in background
        thread.join()
        
        # Hide loading screen, show main UI
        self.hide_loading_screen()
        self.show_main_screen()
    
    def on_stop(self):
        """Called when app closes - stop daemon."""
        self. daemon_manager.stop()
```

**Why this matters:**
- ✅ Model stays loaded between GUI interactions
- ✅ 16s startup cost paid once (when GUI opens)
- ✅ Every transcribe is instant (~2-5s)
- ✅ KivyMD hot reload works (daemon stays running)

---

## 🎁 Final Notes for Opus 4.5

1. **All code is type-safe** - MyPy strict must pass
2. **All functions have docstrings** - Include examples
3. **All tests must pass** - No skipped tests
4. **Update `__all__` exports** - Keep modules clean
5. **Follow existing code style** - Match the patterns you see

**When done, the backend will be 100% GUI-ready.  ** The GUI implementation becomes just wiring up widgets to these APIs.

Good luck!   🚀