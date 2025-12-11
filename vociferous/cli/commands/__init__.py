"""Composable CLI command registrations for Typer."""

from .decode import register_decode
from .vad import register_vad
from .condense import register_condense
from .record import register_record
from .refine import register_refine
from .deps import register_deps
from .bench import register_bench
from .daemon import register_daemon

__all__ = [
    "register_decode",
    "register_vad",
    "register_condense",
    "register_record",
    "register_refine",
    "register_deps",
    "register_bench",
    "register_daemon",
]
