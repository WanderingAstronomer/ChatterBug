"""DEPRECATED: RecorderComponent has moved to vociferous.cli.components.recorder

This module provides backward compatibility. Will be removed in v1.0.0.
"""

import warnings

warnings.warn(
    "Importing RecorderComponent from vociferous.audio.components.recorder_component is deprecated. "
    "Import from vociferous.cli.components.recorder instead.",
    DeprecationWarning,
    stacklevel=2,
)

from vociferous.cli.components.recorder import RecorderComponent

__all__ = ["RecorderComponent"]