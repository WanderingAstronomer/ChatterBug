"""Tests for segment-based refinement preserving alignment."""

from __future__ import annotations

from vociferous.domain.model import TranscriptSegment
from vociferous.refinement import PROMPT_TEMPLATES, CanaryRefiner, NullRefiner


def test_null_refiner_preserves_segments() -> None:
    """NullRefiner returns segments unchanged."""
    refiner = NullRefiner()
    segments = [
        TranscriptSegment(id="1", start=0.0, end=2.0, raw_text="hello world"),
        TranscriptSegment(id="2", start=2.0, end=4.0, raw_text="test segment"),
    ]
    
    result = refiner.refine_segments(segments)
    
    assert len(result) == 2
    assert result[0].id == "1"
    assert result[0].raw_text == "hello world"
    assert result[0].refined_text is None


def test_prompt_templates_available() -> None:
    """All expected refinement modes have prompt templates."""
    assert "grammar_only" in PROMPT_TEMPLATES
    assert "summary" in PROMPT_TEMPLATES
    assert "bullet_points" in PROMPT_TEMPLATES
    
    for mode, template in PROMPT_TEMPLATES.items():
        assert template.strip(), f"Template for {mode} should not be empty"


def test_canary_refiner_segment_structure() -> None:
    """CanaryRefiner preserves segment count and IDs (mock test without real model)."""
    # This test only verifies the interface, not actual refinement
    # Real refinement requires model loading which we skip in unit tests
    refiner = CanaryRefiner()
    
    _segments = [
        TranscriptSegment(id="seg-1", start=0.0, end=3.5, raw_text="this is test"),
        TranscriptSegment(id="seg-2", start=3.5, end=7.0, raw_text="another segment"),
    ]
    
    # We can't actually refine without loading the model, but we can verify
    # the method exists and accepts the correct signature
    assert hasattr(refiner, "refine_segments")
    assert callable(refiner.refine_segments)
