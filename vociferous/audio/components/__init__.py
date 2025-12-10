"""DEPRECATED: Audio components have moved to vociferous.cli.components.

This module provides backward compatibility imports with deprecation warnings.
These imports will be removed in v1.0.0.

Please update your imports:
    OLD: from vociferous.audio.components import DecoderComponent
    NEW: from vociferous.cli.components import DecoderComponent
"""

import warnings

# Import from new location
from vociferous.cli.components import (
    DecoderComponent,
    VADComponent,
    CondenserComponent,
    RecorderComponent,
)

# Issue deprecation warning on module import
warnings.warn(
    "vociferous.audio.components is deprecated and will be removed in v1.0.0. "
    "Please import from vociferous.cli.components instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "DecoderComponent",
    "VADComponent",
    "CondenserComponent",
    "RecorderComponent",
]
