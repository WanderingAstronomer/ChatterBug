from __future__ import annotations

from pathlib import Path
from typing import Iterable, Protocol

from vociferous.domain.model import TranscriptionResult


class StorageRepository(Protocol):
    def save_transcription(self, result: TranscriptionResult, target: Path | None = None) -> Path | None:
        ...

    def load_history(self, limit: int) -> Iterable[TranscriptionResult]:
        ...

    def clear_history(self) -> None:
        ...


class FileSystemStorage(StorageRepository):
    """Filesystem-backed storage stub; persistence wiring is pending."""

    def __init__(self, history_dir: Path) -> None:
        self.history_dir = history_dir
        from vociferous.storage.history import HistoryStorage

        self._history = HistoryStorage(history_dir)

    def save_transcription(self, result: TranscriptionResult, target: Path | None = None) -> Path | None:
        return self._history.save_transcription(result, target=target)

    def load_history(self, limit: int) -> Iterable[TranscriptionResult]:
        return self._history.load_history(limit)

    def clear_history(self) -> None:
        self._history.clear_history()
