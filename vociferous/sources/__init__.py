"""System interaction layer - input sources that resolve to files."""

from .base import Source
from .file import FileSource
from .mic import MicSource
from .memory import MemorySource

__all__ = [
    "Source",
    "FileSource",
    "MicSource",
    "MemorySource",
]
