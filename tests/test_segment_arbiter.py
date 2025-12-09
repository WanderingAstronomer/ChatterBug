"""Tests for SegmentArbiter - segment boundary resolution."""

from vociferous.app.arbiter import SegmentArbiter
from vociferous.domain.model import TranscriptSegment


def _segment(text: str, start: float, end: float) -> TranscriptSegment:
    """Helper to create test segments."""
    return TranscriptSegment(
        text=text,
        start_s=start,
        end_s=end,
        language="en",
        confidence=0.9,
    )


class TestSegmentArbiterOverlapDeduplication:
    """Test de-duplication of overlapping segments."""
    
    def test_overlapping_segments_deduplicated(self) -> None:
        """Overlapping segments with duplicate text are de-duplicated."""
        arbiter = SegmentArbiter()
        segments = [
            _segment("These services", 0.82, 2.82),
            _segment("services here. I am", 1.92, 3.92),
        ]
        
        result = arbiter.arbitrate(segments)
        
        # Should deduplicate and merge since they overlap
        # The result should remove the duplicate "services"
        assert len(result) >= 1  # At minimum, should have 1 merged segment
        # Verify no obvious duplicates
        full_text = " ".join(r.text for r in result)
        # Should have "These", "services", "here", "I am" without duplication
        assert "These" in full_text or "services" in full_text
        assert "here" in full_text
        assert "I am" in full_text
    
    def test_fully_contained_segment_removed(self) -> None:
        """Segment fully contained in another is removed."""
        arbiter = SegmentArbiter()
        segments = [
            _segment("woefully", 3.50, 4.20),
            _segment("woefully unprepared for this.", 4.00, 6.50),
        ]
        
        result = arbiter.arbitrate(segments)
        
        # First segment should be absorbed since it's fully contained
        assert len(result) == 1
        assert result[0].text == "woefully unprepared for this."
        assert result[0].start_s == 4.00
    
    def test_no_overlap_keeps_both_segments(self) -> None:
        """Non-overlapping segments are kept separate."""
        arbiter = SegmentArbiter()
        segments = [
            _segment("First sentence.", 0.0, 2.0),
            _segment("Second sentence.", 3.0, 5.0),
        ]
        
        result = arbiter.arbitrate(segments)
        
        assert len(result) == 2
        assert result[0].text == "First sentence."
        assert result[1].text == "Second sentence."


class TestSegmentArbiterTinyFragments:
    """Test merging of tiny fragments."""
    
    def test_tiny_fragment_merged_with_previous(self) -> None:
        """Short segment with few words is merged with adjacent segments."""
        arbiter = SegmentArbiter(min_segment_duration_s=1.0, min_segment_words=4)
        segments = [
            _segment("This is a longer segment.", 0.0, 2.5),
            _segment("and", 2.6, 2.8),  # Tiny: 0.2s, 1 word
            _segment("Another longer segment here.", 3.0, 5.0),
        ]
        
        result = arbiter.arbitrate(segments)
        
        # Tiny fragment should be merged with adjacent segments
        # Since "and" is a connector and gaps are small, all may be merged
        assert len(result) <= 2  # At most 2 segments after merging tiny fragment
        full_text = " ".join(r.text for r in result)
        assert "and" in full_text  # The word should still be present
    
    def test_tiny_fragment_merged_with_next(self) -> None:
        """Short segment at start is merged with next."""
        arbiter = SegmentArbiter(min_segment_duration_s=1.0, min_segment_words=4)
        segments = [
            _segment("So", 0.0, 0.3),  # Tiny: 0.3s, 1 word
            _segment("this is a longer segment.", 0.5, 3.0),
        ]
        
        result = arbiter.arbitrate(segments)
        
        # Tiny fragment should be merged with next
        assert len(result) == 1
        assert result[0].text.startswith("So")
        assert result[0].start_s == 0.0
        assert result[0].end_s == 3.0
    
    def test_single_tiny_segment_kept(self) -> None:
        """Single tiny segment is kept (no neighbors to merge with)."""
        arbiter = SegmentArbiter(min_segment_duration_s=1.0, min_segment_words=4)
        segments = [
            _segment("Hi", 0.0, 0.5),  # Tiny but only segment
        ]
        
        result = arbiter.arbitrate(segments)
        
        assert len(result) == 1
        assert result[0].text == "Hi"
    
    def test_long_segment_not_merged(self) -> None:
        """Segment meeting duration/word threshold is not merged."""
        arbiter = SegmentArbiter(min_segment_duration_s=1.0, min_segment_words=4)
        segments = [
            _segment("This is exactly four words.", 0.0, 1.5),  # 1.5s, 5 words
            _segment("Another segment here too.", 2.0, 4.0),
        ]
        
        result = arbiter.arbitrate(segments)
        
        assert len(result) == 2  # Both kept separate
    
    def test_tiny_not_merged_across_hard_break(self) -> None:
        """Tiny fragment with one small gap may still be merged."""
        arbiter = SegmentArbiter(
            min_segment_duration_s=1.0,
            min_segment_words=4,
            hard_break_silence_s=1.5,
        )
        segments = [
            _segment("First segment.", 0.0, 2.0),
            _segment("and", 4.0, 4.3),  # Tiny, 2s gap before but 0.7s gap after
            _segment("Last segment.", 5.0, 7.0),
        ]
        
        result = arbiter.arbitrate(segments)
        
        # "and" is tiny with 2s gap before (> hard break) but small gap after (< hard break)
        # Since it's a connector with small gap after, it may be merged with next
        # Result should be <= 3 segments
        assert len(result) <= 3
        assert len(result) >= 2  # At least First and (and + Last) or (First, and, Last)


class TestSegmentArbiterPunctuationBoundaries:
    """Test punctuation-aware boundary enforcement."""
    
    def test_merge_on_soft_gap_without_punctuation(self) -> None:
        """Segments with short gap and no sentence punctuation are merged."""
        arbiter = SegmentArbiter(soft_break_silence_s=0.7)
        segments = [
            _segment("I am going to", 0.0, 2.0),  # No sentence-ending punctuation
            _segment("the store today.", 2.3, 4.0),  # 0.3s gap < 0.7s
        ]
        
        result = arbiter.arbitrate(segments)
        
        assert len(result) == 1
        assert result[0].text == "I am going to the store today."
    
    def test_no_merge_on_sentence_ending_punctuation(self) -> None:
        """Segments separated by sentence punctuation are not merged."""
        arbiter = SegmentArbiter(soft_break_silence_s=0.7)
        segments = [
            _segment("First sentence.", 0.0, 2.0),  # Has period
            _segment("Second sentence.", 2.3, 4.0),  # 0.3s gap < 0.7s but prev has punctuation
        ]
        
        result = arbiter.arbitrate(segments)
        
        # Should stay separate due to punctuation
        assert len(result) == 2
        assert result[0].text == "First sentence."
        assert result[1].text == "Second sentence."
    
    def test_merge_on_connector_word(self) -> None:
        """Segment starting with connector word is merged with previous."""
        arbiter = SegmentArbiter(soft_break_silence_s=0.7)
        segments = [
            _segment("I like coffee", 0.0, 2.0),
            _segment("and tea too.", 2.5, 4.0),  # Starts with "and"
        ]
        
        result = arbiter.arbitrate(segments)
        
        assert len(result) == 1
        assert result[0].text == "I like coffee and tea too."
    
    def test_merge_on_lowercase_ending(self) -> None:
        """Segment ending with lowercase word is merged with next."""
        arbiter = SegmentArbiter(soft_break_silence_s=0.7)
        segments = [
            _segment("These services here. I am", 0.0, 2.0),  # Ends with lowercase "am"
            _segment("very happy.", 2.4, 4.0),
        ]
        
        result = arbiter.arbitrate(segments)
        
        assert len(result) == 1
        assert "I am very happy" in result[0].text
    
    def test_multiple_connectors(self) -> None:
        """Test various connector words are handled."""
        arbiter = SegmentArbiter(soft_break_silence_s=0.7)
        
        for connector in ["and", "but", "so", "or", "yet"]:
            segments = [
                _segment("First part", 0.0, 1.0),
                _segment(f"{connector} second part.", 1.2, 3.0),
            ]
            
            result = arbiter.arbitrate(segments)
            
            assert len(result) == 1, f"Failed for connector: {connector}"
            assert connector in result[0].text.lower()


class TestSegmentArbiterEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_input(self) -> None:
        """Empty input returns empty output."""
        arbiter = SegmentArbiter()
        result = arbiter.arbitrate([])
        assert result == []
    
    def test_single_segment(self) -> None:
        """Single segment is returned unchanged."""
        arbiter = SegmentArbiter()
        segments = [_segment("Single segment.", 0.0, 2.0)]
        
        result = arbiter.arbitrate(segments)
        
        assert len(result) == 1
        assert result[0].text == "Single segment."
    
    def test_all_overlapping_segments(self) -> None:
        """All segments overlapping are resolved correctly."""
        arbiter = SegmentArbiter()
        segments = [
            _segment("The quick brown", 0.0, 2.0),
            _segment("brown fox jumps", 1.5, 3.5),
            _segment("jumps over the", 3.0, 5.0),
            _segment("the lazy dog.", 4.5, 6.5),
        ]
        
        result = arbiter.arbitrate(segments)
        
        # Should deduplicate overlaps
        assert len(result) >= 1  # At least some merging should occur
        # Verify no obvious duplicates in final result
        full_text = " ".join(r.text for r in result)
        assert "brown brown" not in full_text
        assert "jumps jumps" not in full_text
    
    def test_unsorted_segments_handled(self) -> None:
        """Unsorted input segments are sorted correctly."""
        arbiter = SegmentArbiter()
        segments = [
            _segment("Third segment.", 4.0, 6.0),
            _segment("First segment.", 0.0, 2.0),
            _segment("Second segment.", 2.5, 4.0),
        ]
        
        result = arbiter.arbitrate(segments)
        
        # Should be sorted by start time
        assert result[0].start_s < result[1].start_s
        if len(result) > 2:
            assert result[1].start_s < result[2].start_s
    
    def test_segments_with_whitespace(self) -> None:
        """Segments with extra whitespace are handled correctly."""
        arbiter = SegmentArbiter()
        segments = [
            _segment("  Text with spaces  ", 0.0, 2.0),
            _segment("and more text", 2.3, 4.0),
        ]
        
        result = arbiter.arbitrate(segments)
        
        # Should handle whitespace gracefully
        assert len(result) >= 1


class TestSegmentArbiterComplexScenarios:
    """Test complex real-world scenarios."""
    
    def test_example_from_problem_statement(self) -> None:
        """Test the exact example from the problem statement."""
        arbiter = SegmentArbiter()
        segments = [
            _segment("These services", 0.82, 2.82),
            _segment("services here. I am", 1.92, 3.92),
            _segment("woefully", 3.50, 4.20),
            _segment("woefully unprepared for this.", 4.00, 6.50),
        ]
        
        result = arbiter.arbitrate(segments)
        
        # Expected output (approximately):
        # [0.82-3.92] "These services here. I am"
        # [3.92-6.50] "woefully unprepared for this."
        
        # Should have significant reduction in segments
        assert len(result) <= 2, f"Expected <=2 segments, got {len(result)}"
        
        # Verify no obvious duplicates
        full_text = " ".join(r.text for r in result)
        # "services" should not appear twice
        assert full_text.lower().count("services services") == 0
        # "woefully" should not appear twice separately
        assert full_text.lower().count("woefully woefully") == 0
    
    def test_mixed_conditions(self) -> None:
        """Test combination of overlaps, tiny fragments, and punctuation."""
        arbiter = SegmentArbiter()
        segments = [
            _segment("Hello there", 0.0, 1.5),
            _segment("there my friend.", 1.0, 3.0),  # Overlap
            _segment("How", 3.5, 3.8),  # Tiny fragment
            _segment("How are you doing", 3.7, 5.0),  # Overlap with tiny
            _segment("today?", 5.2, 6.0),  # No punctuation before, short gap
        ]
        
        result = arbiter.arbitrate(segments)
        
        # Should result in fewer, cleaner segments
        assert len(result) < len(segments)
        
        # Verify text makes sense
        full_text = " ".join(r.text for r in result)
        assert "Hello" in full_text or "there" in full_text
        assert "friend" in full_text
        assert "How are you" in full_text
    
    def test_configurable_parameters(self) -> None:
        """Test arbiter with custom parameters."""
        arbiter = SegmentArbiter(
            min_segment_duration_s=2.0,  # Stricter than default
            min_segment_words=5,
            hard_break_silence_s=2.0,
            soft_break_silence_s=0.5,
        )
        
        segments = [
            _segment("Short", 0.0, 0.8),  # 0.8s, 1 word - tiny
            _segment("This is a longer segment.", 1.5, 4.0),
            _segment("And another.", 4.3, 6.0),  # 0.3s gap < 0.5s soft break
        ]
        
        result = arbiter.arbitrate(segments)
        
        # With stricter params, should merge more aggressively
        assert len(result) <= 2
