"""DEPRECATED: DecoderComponent has moved to vociferous.cli.components.decoder

This module provides backward compatibility. Will be removed in v1.0.0.
"""

import warnings

warnings.warn(
    "Importing DecoderComponent from vociferous.audio.components.decoder is deprecated. "
    "Import from vociferous.cli.components.decoder instead.",
    DeprecationWarning,
    stacklevel=2,
)

from vociferous.cli.components.decoder import DecoderComponent

__all__ = ["DecoderComponent"]
