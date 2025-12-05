from __future__ import annotations

from pathlib import Path

import typer

from chatterbug.domain import TranscriptSegment, TranscriptSink, TranscriptionResult
from chatterbug.domain.exceptions import DependencyError
from chatterbug.storage.history import HistoryStorage


class StdoutSink(TranscriptSink):
    """Simple sink that writes segments and final text to stdout."""

    def __init__(self) -> None:
        self._segments: list[TranscriptSegment] = []

    def handle_segment(self, segment: TranscriptSegment) -> None:
        self._segments.append(segment)
        typer.echo(f"{segment.start_s:.2f}-{segment.end_s:.2f}: {segment.text}")

    def complete(self, result: TranscriptionResult) -> None:
        typer.echo("\n=== Transcript ===")
        typer.echo(result.text)


class FileSink(TranscriptSink):
    """Writes final transcript to a text file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._segments: list[TranscriptSegment] = []

    def handle_segment(self, segment: TranscriptSegment) -> None:
        self._segments.append(segment)

    def complete(self, result: TranscriptionResult) -> None:
        self.path.write_text(result.text, encoding="utf-8")
        typer.echo(f"Wrote transcript to {self.path}")


class ClipboardSink(TranscriptSink):
    """Copies final transcript to clipboard (requires pyperclip)."""

    def __init__(self) -> None:
        try:
            import pyperclip  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise DependencyError("pyperclip is required for clipboard sink") from exc
        self._pc = pyperclip
        self._segments: list[TranscriptSegment] = []

    def handle_segment(self, segment: TranscriptSegment) -> None:
        self._segments.append(segment)

    def complete(self, result: TranscriptionResult) -> None:
        self._pc.copy(result.text)
        typer.echo("Transcript copied to clipboard")


class HistorySink(TranscriptSink):
    """Writes transcripts to history storage (and optional file)."""

    def __init__(self, storage: HistoryStorage, target: Path | None = None) -> None:
        self.storage = storage
        self.target = target
        self._segments: list[TranscriptSegment] = []

    def handle_segment(self, segment: TranscriptSegment) -> None:
        self._segments.append(segment)

    def complete(self, result: TranscriptionResult) -> None:
        self.storage.save_transcription(result, target=self.target)
        typer.echo("Transcript saved to history")


class CompositeSink(TranscriptSink):
    """Fan-out sink to multiple sinks."""

    def __init__(self, sinks: list[TranscriptSink]) -> None:
        self.sinks = sinks

    def handle_segment(self, segment: TranscriptSegment) -> None:
        for sink in self.sinks:
            sink.handle_segment(segment)

    def complete(self, result: TranscriptionResult) -> None:
        for sink in self.sinks:
            sink.complete(result)
