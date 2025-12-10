"""Sink implementations for transcription output."""

from .sinks import (  # noqa: F401
    ClipboardSink,
    CompositeSink,
    FileSink,
    HistorySink,
    StdoutSink,
)
from .polishing import PolishingSink  # noqa: F401

__all__ = [
    "ClipboardSink",
    "CompositeSink",
    "FileSink",
    "HistorySink",
    "StdoutSink",
    "PolishingSink",
]
