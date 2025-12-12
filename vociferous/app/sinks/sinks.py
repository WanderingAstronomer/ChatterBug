from __future__ import annotations

from pathlib import Path

import typer

from vociferous.domain import TranscriptionResult, TranscriptSegment, TranscriptSink
from vociferous.domain.exceptions import DependencyError


class StdoutSink(TranscriptSink):
    """Simple sink that writes segments and final text to stdout."""

    def __init__(self, show_timestamps: bool = False) -> None:
        self._segments: list[TranscriptSegment] = []
        self._show_timestamps = show_timestamps

    def handle_segment(self, segment: TranscriptSegment) -> None:
        self._segments.append(segment)
        if self._show_timestamps:
            typer.echo(f"{segment.start_s:.2f}-{segment.end_s:.2f}: {segment.text}")

    def complete(self, result: TranscriptionResult) -> None:
        if self._show_timestamps:
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
