"""Test deprecation warnings for audio.components imports.

This module verifies that importing from the old location (audio.components)
issues proper deprecation warnings while maintaining backward compatibility.
"""

from __future__ import annotations

import warnings

import pytest


def test_audio_components_package_deprecation() -> None:
    """Importing from audio.components issues a deprecation warning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", DeprecationWarning)
        
        # Import from old location
        from vociferous.audio.components import DecoderComponent  # noqa: F401
        
        # Filter for vociferous-related deprecation warnings
        vociferous_warnings = [
            warning for warning in w
            if issubclass(warning.category, DeprecationWarning)
            and "vociferous.audio.components is deprecated" in str(warning.message)
        ]
        
        # Verify deprecation warning was issued
        assert len(vociferous_warnings) >= 1
        assert "vociferous.cli.components" in str(vociferous_warnings[0].message)


def test_audio_components_individual_module_deprecation() -> None:
    """Importing from individual audio.components modules issues deprecation warnings."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", DeprecationWarning)
        
        # Import from old individual modules
        from vociferous.audio.components.decoder import DecoderComponent  # noqa: F401
        from vociferous.audio.components.vad import VADComponent  # noqa: F401
        from vociferous.audio.components.condenser import CondenserComponent  # noqa: F401
        from vociferous.audio.components.recorder_component import RecorderComponent  # noqa: F401
        
        # Each should issue a deprecation warning
        assert len(w) >= 4
        for warning in w:
            assert issubclass(warning.category, DeprecationWarning)
            assert "deprecated" in str(warning.message).lower()
            assert "vociferous.cli.components" in str(warning.message)


def test_old_and_new_imports_are_identical() -> None:
    """Components from old and new locations are the same classes."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        
        # Import from old location
        from vociferous.audio.components import (
            DecoderComponent as OldDecoder,
            VADComponent as OldVAD,
            CondenserComponent as OldCondenser,
            RecorderComponent as OldRecorder,
        )
    
    # Import from new location
    from vociferous.cli.components import (
        DecoderComponent as NewDecoder,
        VADComponent as NewVAD,
        CondenserComponent as NewCondenser,
        RecorderComponent as NewRecorder,
    )
    
    # Verify they are identical
    assert OldDecoder is NewDecoder
    assert OldVAD is NewVAD
    assert OldCondenser is NewCondenser
    assert OldRecorder is NewRecorder


def test_new_location_works_without_warnings() -> None:
    """Importing from new location (cli.components) does not issue warnings."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", DeprecationWarning)
        
        # Import from new location
        from vociferous.cli.components import (  # noqa: F401
            DecoderComponent,
            VADComponent,
            CondenserComponent,
            RecorderComponent,
        )
        
        # No deprecation warnings should be issued
        deprecation_warnings = [
            warning for warning in w
            if issubclass(warning.category, DeprecationWarning)
            and "vociferous" in str(warning.message).lower()
        ]
        assert len(deprecation_warnings) == 0
