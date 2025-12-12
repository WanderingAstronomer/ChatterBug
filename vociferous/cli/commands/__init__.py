"""Composable CLI command registrations for Typer."""

from .batch import register_batch
from .bench import register_bench
from .condense import register_condense
from .daemon import register_daemon
from .decode import register_decode
from .deps import register_deps
from .record import register_record
from .refine import register_refine
from .vad import register_vad

__all__ = [
    "register_batch",
    "register_bench",
    "register_condense",
    "register_daemon",
    "register_decode",
    "register_deps",
    "register_record",
    "register_refine",
    "register_vad",
]
