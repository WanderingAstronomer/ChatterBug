"""System interaction layer - AudioSource implementations.

This module provides application-level facades that compose audio primitives
into AudioSource implementations for different input sources.
"""

from .file import FileSource
from .microphone import MicrophoneSource
from .memory import MemorySource

__all__ = [
    "FileSource",
    "MicrophoneSource",
    "MemorySource",
]
