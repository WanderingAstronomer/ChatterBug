"""System interaction layer - input sources that resolve to files."""

from .base import Source
from .file import FileSource
from .memory import MemorySource
from .mic import MicSource

__all__ = [
    "FileSource",
    "MemorySource",
    "MicSource",
    "Source",
]
