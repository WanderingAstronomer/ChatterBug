"""Sink implementations for transcription output."""

from .polishing import RefiningSink
from .sinks import (
    ClipboardSink,
    CompositeSink,
    FileSink,
    StdoutSink,
)

__all__ = [
    "ClipboardSink",
    "CompositeSink",
    "FileSink",
    "RefiningSink",
    "StdoutSink",
]
