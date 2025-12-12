"""Source protocol for file-first workflows.

Sources must resolve to a concrete file path before the audio pipeline runs.
This keeps the app layer independent of how audio was acquired (file, mic, etc.).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Source(Protocol):
    """Resolve an input source to a real file on disk."""

    def resolve_to_path(self, work_dir: Path | None = None) -> Path:
        """Return a path to an audio file, creating/recording if necessary."""
        ...
