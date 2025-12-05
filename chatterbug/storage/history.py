from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Iterable

from chatterbug.domain.model import TranscriptionResult
from .repository import StorageRepository


class HistoryStorage(StorageRepository):
    """File-based history storage using line-delimited JSON."""

    def __init__(self, history_dir: Path, limit: int = 100) -> None:
        self.history_dir = history_dir
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.limit = limit
        self.history_file = self.history_dir / "history.jsonl"
        self._lock = Lock()

    def save_transcription(self, result: TranscriptionResult, target: Path | None = None) -> Path | None:
        with self._lock:
            if target:
                target.write_text(result.text, encoding="utf-8")
                return target
            line = json.dumps(result.model_dump(), default=str)
            with self.history_file.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            self._trim_history_locked()
            return None

    def load_history(self, limit: int) -> Iterable[TranscriptionResult]:
        with self._lock:
            if not self.history_file.exists():
                return iter(())
            items: list[TranscriptionResult] = []
            with self.history_file.open("r", encoding="utf-8") as f:
                for line in f.readlines()[-limit:]:
                    try:
                        data = json.loads(line)
                        items.append(TranscriptionResult(**data))
                    except Exception:
                        continue
        return iter(items)

    def clear_history(self) -> None:
        with self._lock:
            if self.history_file.exists():
                self.history_file.unlink()

    def _trim_history_locked(self) -> None:
        """Trim history file atomically using temp file + rename."""
        if not self.history_file.exists():
            return
        lines = self.history_file.read_text(encoding="utf-8").splitlines()
        if len(lines) > self.limit:
            trimmed = lines[-self.limit :]
            # Write to temporary file first
            temp_file = self.history_file.with_suffix(".tmp")
            temp_file.write_text("\n".join(trimmed) + "\n", encoding="utf-8")
            # Atomic rename on POSIX systems (overwrites destination)
            # On Windows, need to remove destination first
            if os.name == 'nt':
                try:
                    self.history_file.unlink()
                except FileNotFoundError:
                    pass  # File already gone, which is fine
            temp_file.replace(self.history_file)
