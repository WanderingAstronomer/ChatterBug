"""CLI adapter components for audio processing.

These components provide file-path/file-IO wrappers around audio primitives,
designed for use in CLI workflows and interface adapters.
"""

from .condenser import CondenserComponent
from .decoder import DecoderComponent
from .recorder import RecorderComponent
from .vad import VADComponent

__all__ = [
    "CondenserComponent",
    "DecoderComponent",
    "RecorderComponent",
    "VADComponent",
]
