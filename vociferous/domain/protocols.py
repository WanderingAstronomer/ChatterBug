"""Protocol definitions for dependency injection and abstraction.

This module defines the callback interfaces used for GUI integration,
allowing the backend to communicate progress without depending on any
specific UI framework.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

__all__ = [
    "ProgressCallback",
    "ProgressUpdate",
    "ProgressUpdateData",
]


class ProgressUpdate(Protocol):
    """Protocol for progress update data passed to callbacks.
    
    This defines the interface that progress updates must satisfy.
    Use ProgressUpdateData for concrete instances.
    """
    
    @property
    def stage(self) -> str:
        """Current stage name (e.g., 'decode', 'vad', 'transcribe')."""
        ...
    
    @property
    def progress(self) -> float | None:
        """Progress from 0.0 to 1.0, or None for indeterminate."""
        ...
    
    @property
    def message(self) -> str:
        """Human-readable status message."""
        ...
    
    @property
    def elapsed_s(self) -> float | None:
        """Optional elapsed time in seconds."""
        ...
    
    @property
    def remaining_s(self) -> float | None:
        """Optional estimated remaining time in seconds."""
        ...


@dataclass(frozen=True)
class ProgressUpdateData:
    """Concrete implementation of ProgressUpdate protocol.
    
    This is the data structure passed to progress callbacks, containing
    all information needed to update a GUI progress display.
    
    Attributes:
        stage: Stage identifier (e.g., "decode", "vad", "transcribe", "refine")
        progress: Progress from 0.0 to 1.0, or None for indeterminate operations
        message: Human-readable status message for display
        elapsed_s: Time elapsed since stage started (seconds)
        remaining_s: Estimated time remaining (seconds), if available
    
    Example:
        >>> update = ProgressUpdateData(
        ...     stage="transcribe",
        ...     progress=0.5,
        ...     message="Transcribing chunk 2/4...",
        ...     elapsed_s=15.2,
        ... )
        >>> print(f"{update.stage}: {update.message} ({update.progress:.0%})")
        transcribe: Transcribing chunk 2/4... (50%)
    """
    
    stage: str
    progress: float | None
    message: str
    elapsed_s: float | None = None
    remaining_s: float | None = None


# Type alias for progress callbacks
# The callback receives a ProgressUpdate (or ProgressUpdateData) and returns nothing
ProgressCallback = Callable[[ProgressUpdateData], None]
