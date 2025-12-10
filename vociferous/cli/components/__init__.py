"""CLI adapter components for audio processing.

These components provide file-path/file-IO wrappers around audio primitives,
designed for use in CLI workflows and interface adapters.
"""

from .decoder import DecoderComponent
from .vad import VADComponent
from .condenser import CondenserComponent
from .recorder import RecorderComponent

__all__ = [
    "DecoderComponent",
    "VADComponent",
    "CondenserComponent",
    "RecorderComponent",
]
