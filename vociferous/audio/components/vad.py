"""DEPRECATED: VADComponent has moved to vociferous.cli.components.vad

This module provides backward compatibility. Will be removed in v1.0.0.
"""

import warnings

warnings.warn(
    "Importing VADComponent from vociferous.audio.components.vad is deprecated. "
    "Import from vociferous.cli.components.vad instead.",
    DeprecationWarning,
    stacklevel=2,
)

from vociferous.cli.components.vad import VADComponent

__all__ = ["VADComponent"]
