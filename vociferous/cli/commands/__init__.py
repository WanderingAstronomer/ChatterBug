"""Composable CLI command registrations for Typer."""

from .decode import register_decode
from .vad import register_vad
from .condense import register_condense
from .record import register_record
from .transcribe_full import register_transcribe_full

__all__ = [
    "register_decode",
    "register_vad",
    "register_condense",
    "register_record",
    "register_transcribe_full",
]
