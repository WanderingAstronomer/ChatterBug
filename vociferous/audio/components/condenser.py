"""DEPRECATED: CondenserComponent has moved to vociferous.cli.components.condenser

This module provides backward compatibility. Will be removed in v1.0.0.
"""

import warnings

warnings.warn(
    "Importing CondenserComponent from vociferous.audio.components.condenser is deprecated. "
    "Import from vociferous.cli.components.condenser instead.",
    DeprecationWarning,
    stacklevel=2,
)

from vociferous.cli.components.condenser import CondenserComponent

__all__ = ["CondenserComponent"]
