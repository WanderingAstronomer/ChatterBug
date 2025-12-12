"""Comprehensive tests for intelligent audio chunking algorithm.

Tests the FFmpegCondenser's splitting logic with synthetic VAD timestamps
to validate:
1. Normal speech with regular pauses
2. Dense speech with few pauses
3. Continuous speech requiring force-splits
4. Choppy VAD with many tiny segments
5. Edge cases (exactly at limit, over limit, single segment)
"""

from __future__ import annotations

import pytest

from vociferous.audio.ffmpeg_condenser import FFmpegCondenser
from vociferous.domain.exceptions import UnsplittableSegmentError


class TestChunkDurationCalculation:
    """Test _calculate_chunk_duration() method."""
    
    @pytest.fixture
    def condenser(self) -> FFmpegCondenser:
        return FFmpegCondenser()
    
    def test_empty_segments(self, condenser: FFmpegCondenser) -> None:
        """Empty segment list should return 0."""
        duration = condenser._calculate_chunk_duration([], 0.8, 0.3)
        assert duration == 0.0
    
    def test_single_segment(self, condenser: FFmpegCondenser) -> None:
        """Single segment: speech + 2 margins."""
        segments = [{'start': 0.0, 'end': 10.0}]
        duration = condenser._calculate_chunk_duration(segments, 0.8, 0.3)
        # 10s speech + 0.3s margin start + 0.3s margin end = 10.6s
        assert duration == pytest.approx(10.6)
    
    def test_two_segments_small_gap(self, condenser: FFmpegCondenser) -> None:
        """Two segments with gap smaller than max_intra_gap_s."""
        segments = [
            {'start': 0.0, 'end': 10.0},
            {'start': 10.5, 'end': 20.0},  # 0.5s gap
        ]
        duration = condenser._calculate_chunk_duration(segments, 0.8, 0.3)
        # 10s + 9.5s speech + 0.5s gap (preserved fully) + 2*0.3s margins = 20.6s
        assert duration == pytest.approx(20.6)
    
    def test_two_segments_large_gap(self, condenser: FFmpegCondenser) -> None:
        """Two segments with gap larger than max_intra_gap_s (capped)."""
        segments = [
            {'start': 0.0, 'end': 10.0},
            {'start': 15.0, 'end': 25.0},  # 5s gap, capped to 0.8s
        ]
        duration = condenser._calculate_chunk_duration(segments, 0.8, 0.3)
        # 10s + 10s speech + 0.8s gap (capped) + 2*0.3s margins = 21.4s
        assert duration == pytest.approx(21.4)
    
    def test_multiple_segments(self, condenser: FFmpegCondenser) -> None:
        """Multiple segments with varying gaps."""
        segments = [
            {'start': 0.0, 'end': 10.0},    # 10s
            {'start': 10.5, 'end': 20.0},   # 9.5s, 0.5s gap
            {'start': 21.0, 'end': 30.0},   # 9s, 1.0s gap (capped to 0.8s)
        ]
        duration = condenser._calculate_chunk_duration(segments, 0.8, 0.3)
        # Speech: 10 + 9.5 + 9 = 28.5s
        # Gaps: 0.5 + 0.8 = 1.3s
        # Margins: 0.6s
        # Total: 30.4s
        assert duration == pytest.approx(30.4)


class TestSilenceGapCalculation:
    """Test _calculate_silence_gaps() method."""
    
    @pytest.fixture
    def condenser(self) -> FFmpegCondenser:
        return FFmpegCondenser()
    
    def test_empty_timestamps(self, condenser: FFmpegCondenser) -> None:
        """Empty timestamps should return empty gaps."""
        gaps = condenser._calculate_silence_gaps([])
        assert gaps == []
    
    def test_single_segment(self, condenser: FFmpegCondenser) -> None:
        """Single segment has no gaps."""
        timestamps = [{'start': 0.0, 'end': 10.0}]
        gaps = condenser._calculate_silence_gaps(timestamps)
        assert gaps == []
    
    def test_two_segments_with_gap(self, condenser: FFmpegCondenser) -> None:
        """Two segments with positive gap."""
        timestamps = [
            {'start': 0.0, 'end': 10.0},
            {'start': 12.0, 'end': 20.0},
        ]
        gaps = condenser._calculate_silence_gaps(timestamps)
        assert len(gaps) == 1
        assert gaps[0] == (10.0, 12.0, 2.0, 0)  # (start, end, duration, after_idx)
    
    def test_touching_segments(self, condenser: FFmpegCondenser) -> None:
        """Touching segments have zero gap."""
        timestamps = [
            {'start': 0.0, 'end': 10.0},
            {'start': 10.0, 'end': 20.0},
        ]
        gaps = condenser._calculate_silence_gaps(timestamps)
        assert len(gaps) == 1
        assert gaps[0][2] == 0.0  # duration is 0
    
    def test_overlapping_segments(self, condenser: FFmpegCondenser) -> None:
        """Overlapping segments treated as zero gap."""
        timestamps = [
            {'start': 0.0, 'end': 10.0},
            {'start': 9.0, 'end': 20.0},  # overlaps by 1s
        ]
        gaps = condenser._calculate_silence_gaps(timestamps)
        assert len(gaps) == 1
        assert gaps[0][2] == 0.0


class TestSplitPointFinding:
    """Test _find_split_points() method."""
    
    @pytest.fixture
    def condenser(self) -> FFmpegCondenser:
        return FFmpegCondenser()
    
    def test_short_audio_no_splits(self, condenser: FFmpegCondenser) -> None:
        """Audio under search_start_s should not split."""
        timestamps = [
            {'start': 0.0, 'end': 25.0},  # 25s, under 30s search start
        ]
        gaps = condenser._calculate_silence_gaps(timestamps)
        splits = condenser._find_split_points(
            timestamps, gaps,
            min_gap_s=3.0, search_start_s=30.0, max_chunk_s=60.0,
            max_intra_gap_s=0.8, boundary_margin_s=0.3,
        )
        assert splits == []
    
    def test_natural_split_at_large_gap(self, condenser: FFmpegCondenser) -> None:
        """Should split at 3s+ gap after reaching search_start_s when approaching max."""
        # Create segments that will exceed 60s total, forcing a split at the natural gap
        timestamps = [
            {'start': 0.0, 'end': 35.0},    # 35s speech
            {'start': 38.5, 'end': 70.0},   # 31.5s speech, 3.5s gap before
            # Total without split: 35 + 31.5 + 0.8 + 0.6 = 67.9s > 60s
        ]
        gaps = condenser._calculate_silence_gaps(timestamps)
        splits = condenser._find_split_points(
            timestamps, gaps,
            min_gap_s=3.0, search_start_s=30.0, max_chunk_s=60.0,
            max_intra_gap_s=0.8, boundary_margin_s=0.3,
        )
        # After first segment: 35 + 0.6 = 35.6s, which is > 30s search start
        # There's a 3.5s gap after first segment, so we split there
        assert splits == [0]  # Split after first segment
    
    def test_no_split_under_max_chunk(self, condenser: FFmpegCondenser) -> None:
        """No split needed if total is under max_chunk_s."""
        timestamps = [
            {'start': 0.0, 'end': 25.0},
            {'start': 26.0, 'end': 50.0},
        ]
        gaps = condenser._calculate_silence_gaps(timestamps)
        splits = condenser._find_split_points(
            timestamps, gaps,
            min_gap_s=3.0, search_start_s=30.0, max_chunk_s=60.0,
            max_intra_gap_s=0.8, boundary_margin_s=0.3,
        )
        # Total: 25 + 24 + 0.8 (gap capped) + 0.6 (margins) = 50.4s < 60s
        assert splits == []
    
    def test_force_split_when_no_large_gaps(self, condenser: FFmpegCondenser) -> None:
        """Force-split when hitting max_chunk_s with no 3s+ gaps."""
        timestamps = [
            {'start': 0.0, 'end': 20.0},    # 20s
            {'start': 21.0, 'end': 40.0},   # 19s, 1s gap
            {'start': 41.5, 'end': 60.0},   # 18.5s, 1.5s gap
            {'start': 61.0, 'end': 80.0},   # 19s, 1s gap
        ]
        gaps = condenser._calculate_silence_gaps(timestamps)
        splits = condenser._find_split_points(
            timestamps, gaps,
            min_gap_s=3.0, search_start_s=30.0, max_chunk_s=60.0,
            max_intra_gap_s=0.8, boundary_margin_s=0.3,
        )
        # Should force-split at some point before hitting 60s
        assert len(splits) > 0
        
        # Verify all resulting chunks are under 60s
        all_chunks = condenser._split_timestamps_into_chunks(timestamps, splits)
        for chunk in all_chunks:
            duration = condenser._calculate_chunk_duration(chunk, 0.8, 0.3)
            assert duration <= 60.0


class TestNormalSpeechPatterns:
    """Test splitting with normal conversational speech patterns."""
    
    @pytest.fixture
    def condenser(self) -> FFmpegCondenser:
        return FFmpegCondenser()
    
    def test_regular_pauses_every_30s(self, condenser: FFmpegCondenser) -> None:
        """Regular 3s+ pauses every ~30-40s should split naturally."""
        timestamps = [
            {'start': 0.0, 'end': 25.0},
            {'start': 28.0, 'end': 55.0},   # 3s gap
            {'start': 59.0, 'end': 82.0},   # 4s gap
            {'start': 85.5, 'end': 110.0},  # 3.5s gap
        ]
        gaps = condenser._calculate_silence_gaps(timestamps)
        splits = condenser._find_split_points(
            timestamps, gaps,
            min_gap_s=3.0, search_start_s=30.0, max_chunk_s=60.0,
            max_intra_gap_s=0.8, boundary_margin_s=0.3,
        )
        
        # Should have natural splits at the 3s+ gaps
        assert len(splits) >= 1
        
        # All chunks should be under 60s
        chunks = condenser._split_timestamps_into_chunks(timestamps, splits)
        for chunk in chunks:
            duration = condenser._calculate_chunk_duration(chunk, 0.8, 0.3)
            assert duration <= 60.0


class TestDenseSpeechPatterns:
    """Test splitting with dense lecture-style speech."""
    
    @pytest.fixture
    def condenser(self) -> FFmpegCondenser:
        return FFmpegCondenser()
    
    def test_few_pauses_accumulates_longer(self, condenser: FFmpegCondenser) -> None:
        """Dense speech with few 3s+ pauses should accumulate to larger chunks."""
        timestamps = [
            {'start': 0.0, 'end': 20.0},
            {'start': 21.0, 'end': 40.0},   # 1s gap
            {'start': 41.5, 'end': 60.0},   # 1.5s gap
            {'start': 63.5, 'end': 82.0},   # 3.5s gap - first valid split point
        ]
        gaps = condenser._calculate_silence_gaps(timestamps)
        splits = condenser._find_split_points(
            timestamps, gaps,
            min_gap_s=3.0, search_start_s=30.0, max_chunk_s=60.0,
            max_intra_gap_s=0.8, boundary_margin_s=0.3,
        )
        
        # Should split at the 3.5s gap (after segment 2, 0-indexed)
        assert 2 in splits


class TestContinuousSpeechPatterns:
    """Test splitting with continuous speech (no natural pauses)."""
    
    @pytest.fixture
    def condenser(self) -> FFmpegCondenser:
        return FFmpegCondenser()
    
    def test_no_large_pauses_force_splits(self, condenser: FFmpegCondenser) -> None:
        """Continuous speech with only short pauses requires force-splits."""
        timestamps = [
            {'start': 0.0, 'end': 25.0},
            {'start': 26.0, 'end': 50.0},   # 1s gap
            {'start': 51.5, 'end': 75.0},   # 1.5s gap
            {'start': 76.0, 'end': 100.0},  # 1s gap
        ]
        gaps = condenser._calculate_silence_gaps(timestamps)
        splits = condenser._find_split_points(
            timestamps, gaps,
            min_gap_s=3.0, search_start_s=30.0, max_chunk_s=60.0,
            max_intra_gap_s=0.8, boundary_margin_s=0.3,
        )
        
        # Should force-split
        assert len(splits) > 0
        
        # All chunks must be under 60s
        chunks = condenser._split_timestamps_into_chunks(timestamps, splits)
        for chunk in chunks:
            duration = condenser._calculate_chunk_duration(chunk, 0.8, 0.3)
            assert duration <= 60.0, f"Chunk exceeded 60s: {duration:.1f}s"


class TestChoppyVADPatterns:
    """Test splitting with choppy VAD output (many tiny segments)."""
    
    @pytest.fixture
    def condenser(self) -> FFmpegCondenser:
        return FFmpegCondenser()
    
    def test_many_tiny_segments(self, condenser: FFmpegCondenser) -> None:
        """50 segments of ~1s each with 0.5s gaps."""
        timestamps = []
        
        # Create 50 segments of ~1s each with 0.5s gaps
        for i in range(50):
            start = i * 1.5
            end = start + 1.0
            timestamps.append({'start': start, 'end': end})
        
        gaps = condenser._calculate_silence_gaps(timestamps)
        
        # Inject a few 3s+ gaps
        # Gap at index 19 (after segment 19): make it 3.2s
        if len(gaps) > 19:
            gaps[19] = (gaps[19][0], gaps[19][0] + 3.2, 3.2, 19)
        # Gap at index 39 (after segment 39): make it 4.0s
        if len(gaps) > 39:
            gaps[39] = (gaps[39][0], gaps[39][0] + 4.0, 4.0, 39)
        
        splits = condenser._find_split_points(
            timestamps, gaps,
            min_gap_s=3.0, search_start_s=30.0, max_chunk_s=60.0,
            max_intra_gap_s=0.8, boundary_margin_s=0.3,
        )
        
        # All chunks under 60s
        chunks = condenser._split_timestamps_into_chunks(timestamps, splits)
        for chunk in chunks:
            duration = condenser._calculate_chunk_duration(chunk, 0.8, 0.3)
            assert duration <= 60.0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.fixture
    def condenser(self) -> FFmpegCondenser:
        return FFmpegCondenser()
    
    def test_exactly_at_limit(self, condenser: FFmpegCondenser) -> None:
        """Chunk that's exactly at the 60s limit."""
        # 58s speech + 0.6s margins = 58.6s
        timestamps = [{'start': 0.0, 'end': 58.0}]
        gaps = condenser._calculate_silence_gaps(timestamps)
        
        splits = condenser._find_split_points(
            timestamps, gaps,
            min_gap_s=3.0, search_start_s=30.0, max_chunk_s=60.0,
            max_intra_gap_s=0.8, boundary_margin_s=0.3,
        )
        
        # Single segment under limit, no split needed
        assert splits == []
        
        duration = condenser._calculate_chunk_duration(timestamps, 0.8, 0.3)
        assert duration <= 60.0
    
    def test_single_segment_over_limit(self, condenser: FFmpegCondenser) -> None:
        """Single segment that exceeds limit should raise error."""
        # 62s speech + 0.6s margins = 62.6s > 60s
        timestamps = [{'start': 0.0, 'end': 62.0}]
        gaps = condenser._calculate_silence_gaps(timestamps)
        
        with pytest.raises(UnsplittableSegmentError) as exc_info:
            condenser._find_split_points(
                timestamps, gaps,
                min_gap_s=3.0, search_start_s=30.0, max_chunk_s=60.0,
                max_intra_gap_s=0.8, boundary_margin_s=0.3,
            )
        
        # New rich error format
        assert "is too long" in str(exc_info.value)
        assert "62.0s" in str(exc_info.value)
        assert "60.0s" in str(exc_info.value)
    
    def test_two_segments_both_under_limit_together(self, condenser: FFmpegCondenser) -> None:
        """Two segments that together are under limit should not split."""
        timestamps = [
            {'start': 0.0, 'end': 20.0},
            {'start': 21.0, 'end': 40.0},
        ]
        gaps = condenser._calculate_silence_gaps(timestamps)
        
        splits = condenser._find_split_points(
            timestamps, gaps,
            min_gap_s=3.0, search_start_s=30.0, max_chunk_s=60.0,
            max_intra_gap_s=0.8, boundary_margin_s=0.3,
        )
        
        # Total: 20 + 19 + 0.8 (gap capped) + 0.6 (margins) = 40.4s < 60s
        assert splits == []


class TestSplitTimestampsIntoChunks:
    """Test _split_timestamps_into_chunks() helper."""
    
    @pytest.fixture
    def condenser(self) -> FFmpegCondenser:
        return FFmpegCondenser()
    
    def test_no_splits(self, condenser: FFmpegCondenser) -> None:
        """Empty split indices returns original as single chunk."""
        timestamps = [{'start': 0.0, 'end': 10.0}, {'start': 11.0, 'end': 20.0}]
        chunks = condenser._split_timestamps_into_chunks(timestamps, [])
        assert len(chunks) == 1
        assert chunks[0] == timestamps
    
    def test_single_split(self, condenser: FFmpegCondenser) -> None:
        """Single split divides into two chunks."""
        timestamps = [
            {'start': 0.0, 'end': 10.0},   # 0
            {'start': 11.0, 'end': 20.0},  # 1
            {'start': 21.0, 'end': 30.0},  # 2
        ]
        chunks = condenser._split_timestamps_into_chunks(timestamps, [1])
        
        assert len(chunks) == 2
        assert chunks[0] == timestamps[0:2]  # [seg0, seg1]
        assert chunks[1] == timestamps[2:3]  # [seg2]
    
    def test_multiple_splits(self, condenser: FFmpegCondenser) -> None:
        """Multiple splits divide into multiple chunks."""
        timestamps = [
            {'start': 0.0, 'end': 10.0},   # 0
            {'start': 11.0, 'end': 20.0},  # 1
            {'start': 21.0, 'end': 30.0},  # 2
            {'start': 31.0, 'end': 40.0},  # 3
            {'start': 41.0, 'end': 50.0},  # 4
        ]
        chunks = condenser._split_timestamps_into_chunks(timestamps, [1, 3])
        
        assert len(chunks) == 3
        assert chunks[0] == timestamps[0:2]  # [seg0, seg1]
        assert chunks[1] == timestamps[2:4]  # [seg2, seg3]
        assert chunks[2] == timestamps[4:5]  # [seg4]


class TestForceSplitLocation:
    """Test _find_force_split_location() method."""
    
    @pytest.fixture
    def condenser(self) -> FFmpegCondenser:
        return FFmpegCondenser()
    
    def test_finds_optimal_split_under_60s(self, condenser: FFmpegCondenser) -> None:
        """Should find split point that keeps chunk under 60s."""
        chunk_segments = [
            {'start': 0.0, 'end': 20.0},
            {'start': 21.0, 'end': 40.0},
            {'start': 41.5, 'end': 65.0},  # This would push over 60s
        ]
        
        split_idx = condenser._find_force_split_location(
            chunk_segments,
            chunk_start_idx=0,
            max_chunk_s=60.0,
            max_intra_gap_s=0.8,
            boundary_margin_s=0.3,
        )
        
        # Should split before the segment that pushes over
        assert split_idx in [0, 1]  # Either after seg0 or seg1
        
        # Verify the resulting chunk is under 60s
        test_segments = chunk_segments[:split_idx - 0 + 1]
        duration = condenser._calculate_chunk_duration(test_segments, 0.8, 0.3)
        assert duration <= 60.0
    
    def test_single_oversized_segment_raises(self, condenser: FFmpegCondenser) -> None:
        """Single segment over limit should raise error."""
        chunk_segments = [{'start': 0.0, 'end': 65.0}]  # 65.6s with margins
        
        with pytest.raises(UnsplittableSegmentError):
            condenser._find_force_split_location(
                chunk_segments,
                chunk_start_idx=0,
                max_chunk_s=60.0,
                max_intra_gap_s=0.8,
                boundary_margin_s=0.3,
            )
