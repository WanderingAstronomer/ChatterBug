"""Tests for SegmentArbiter integration with engines."""

from __future__ import annotations

import pytest

from vociferous.domain.model import TranscriptSegment
from vociferous.app.arbiter import SegmentArbiter


def test_arbiter_removes_duplicates():
    """SegmentArbiter deduplicates overlapping segments."""
    raw_segments = [
        TranscriptSegment(text="hello", start_s=0.0, end_s=1.0, language="en", confidence=0.9),
        TranscriptSegment(text="hello", start_s=0.1, end_s=1.1, language="en", confidence=0.9),  # Duplicate
        TranscriptSegment(text="world", start_s=1.0, end_s=2.0, language="en", confidence=0.9),
    ]
    
    arbiter = SegmentArbiter()
    clean = arbiter.arbitrate(raw_segments)
    
    # Should have deduplicated the overlapping "hello" segments
    assert len(clean) <= 2
    # Check that output contains expected words (may be merged)
    all_text = " ".join(seg.text for seg in clean)
    assert "hello" in all_text
    assert "world" in all_text
    # Should not have multiple "hello" occurrences
    assert all_text.count("hello") <= 1


def test_arbiter_merges_tiny_fragments():
    """SegmentArbiter merges segments that are too short."""
    raw_segments = [
        TranscriptSegment(text="I", start_s=0.0, end_s=0.1, language="en", confidence=0.9),
        TranscriptSegment(text="am testing", start_s=0.2, end_s=1.5, language="en", confidence=0.9),
        TranscriptSegment(text="the", start_s=1.6, end_s=1.7, language="en", confidence=0.9),
        TranscriptSegment(text="system", start_s=1.8, end_s=2.5, language="en", confidence=0.9),
    ]
    
    arbiter = SegmentArbiter(
        min_segment_duration_s=0.5,
        min_segment_words=2,
    )
    clean = arbiter.arbitrate(raw_segments)
    
    # Tiny fragments should be merged
    assert len(clean) < len(raw_segments)
    
    # Check no overlaps
    for i in range(len(clean) - 1):
        assert clean[i].end_s <= clean[i+1].start_s


def test_arbiter_enforces_punctuation_boundaries():
    """SegmentArbiter merges segments at mid-phrase boundaries."""
    raw_segments = [
        TranscriptSegment(text="Today is", start_s=0.0, end_s=1.0, language="en", confidence=0.9),
        TranscriptSegment(text="Monday", start_s=1.1, end_s=2.0, language="en", confidence=0.9),
        TranscriptSegment(text="I am testing.", start_s=3.0, end_s=5.0, language="en", confidence=0.9),
    ]
    
    arbiter = SegmentArbiter(soft_break_silence_s=0.5)
    clean = arbiter.arbitrate(raw_segments)
    
    # "Today is" and "Monday" should be merged (mid-phrase)
    # The third segment should stay separate (complete sentence after gap)
    assert len(clean) <= 2


def test_arbiter_no_overlaps_in_output():
    """SegmentArbiter produces non-overlapping segments."""
    raw_segments = [
        TranscriptSegment(text="These services", start_s=0.82, end_s=2.82, language="en", confidence=0.9),
        TranscriptSegment(text="services here. I am", start_s=1.92, end_s=3.92, language="en", confidence=0.9),
        TranscriptSegment(text="woefully", start_s=3.50, end_s=4.20, language="en", confidence=0.9),
        TranscriptSegment(text="woefully unprepared for this.", start_s=4.00, end_s=6.50, language="en", confidence=0.9),
    ]
    
    arbiter = SegmentArbiter()
    clean = arbiter.arbitrate(raw_segments)
    
    # Verify no overlaps
    for i in range(len(clean) - 1):
        assert clean[i].end_s <= clean[i+1].start_s, \
            f"Overlap detected: segment {i} ends at {clean[i].end_s}, " \
            f"segment {i+1} starts at {clean[i+1].start_s}"


def test_arbiter_empty_input():
    """SegmentArbiter handles empty input."""
    arbiter = SegmentArbiter()
    clean = arbiter.arbitrate([])
    assert clean == []


def test_arbiter_single_segment():
    """SegmentArbiter handles single segment input."""
    raw_segments = [
        TranscriptSegment(text="Hello world", start_s=0.0, end_s=2.0, language="en", confidence=0.9),
    ]
    
    arbiter = SegmentArbiter()
    clean = arbiter.arbitrate(raw_segments)
    
    assert len(clean) == 1
    assert clean[0].text == "Hello world"


def test_arbiter_no_duplicate_text():
    """SegmentArbiter removes duplicate text."""
    # Simulate the repeating numbers issue
    raw_segments = [
        TranscriptSegment(text="14, 15, 16", start_s=36.48, end_s=38.40, language="en", confidence=0.9),
        TranscriptSegment(text="16, 16, 16, 16", start_s=38.00, end_s=40.00, language="en", confidence=0.9),
        TranscriptSegment(text="16, 17, 18", start_s=40.16, end_s=42.00, language="en", confidence=0.9),
    ]
    
    arbiter = SegmentArbiter()
    clean = arbiter.arbitrate(raw_segments)
    
    # Check that we don't have excessive repetition
    all_text = " ".join(seg.text for seg in clean)
    # Count occurrences of "16"
    count_16 = all_text.count("16")
    # Should not have 6+ occurrences (the original had many repeats)
    assert count_16 < 6, f"Too many repetitions of '16' in output: {all_text}"
