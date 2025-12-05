"""
Backward compatibility shim for sinks.

Sinks have been moved to chatterbug.app.sinks to fix architecture layer violations.
This module provides imports for backward compatibility.
"""
from __future__ import annotations

from chatterbug.app.sinks import (  # noqa: F401
    ClipboardSink,
    CompositeSink,
    FileSink,
    HistorySink,
    StdoutSink,
)
