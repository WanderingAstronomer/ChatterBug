"""Tests for SegmentArbiter integration with WhisperTurboEngine."""

from unittest.mock import MagicMock, patch

import pytest

from vociferous.domain.model import EngineConfig, TranscriptSegment, TranscriptionOptions
from vociferous.engines.whisper_turbo import WhisperTurboEngine


def _config(**overrides) -> EngineConfig:
    """Helper to create EngineConfig."""
    return EngineConfig(**overrides)


def _segment(text: str, start: float, end: float) -> TranscriptSegment:
    """Helper to create test segments."""
    return TranscriptSegment(
        text=text,
        start_s=start,
        end_s=end,
        language="en",
        confidence=0.9,
    )


class TestSegmentArbiterIntegration:
    """Test SegmentArbiter integration with WhisperTurboEngine."""
    
    def test_arbiter_enabled_by_default(self) -> None:
        """Segment arbiter is enabled by default."""
        config = _config()
        engine = WhisperTurboEngine(config)
        
        assert engine.use_segment_arbiter is True
        assert engine._arbiter is not None
    
    def test_arbiter_can_be_disabled(self) -> None:
        """Segment arbiter can be disabled via params."""
        config = _config(params={"use_segment_arbiter": "false"})
        engine = WhisperTurboEngine(config)
        
        assert engine.use_segment_arbiter is False
        assert engine._arbiter is None
    
    def test_arbiter_parameters_configurable(self) -> None:
        """Arbiter parameters can be configured."""
        config = _config(
            params={
                "arbiter_min_duration_s": "2.0",
                "arbiter_min_words": "5",
                "arbiter_hard_break_s": "2.5",
                "arbiter_soft_break_s": "0.5",
            }
        )
        engine = WhisperTurboEngine(config)
        
        assert engine.arbiter_min_duration_s == 2.0
        assert engine.arbiter_min_words == 5
        assert engine.arbiter_hard_break_s == 2.5
        assert engine.arbiter_soft_break_s == 0.5
        assert engine._arbiter is not None
        assert engine._arbiter.min_segment_duration_s == 2.0
        assert engine._arbiter.min_segment_words == 5
        assert engine._arbiter.hard_break_silence_s == 2.5
        assert engine._arbiter.soft_break_silence_s == 0.5
    
    def test_poll_segments_applies_arbiter(self) -> None:
        """poll_segments applies arbiter to deduplicate overlapping segments."""
        config = _config()
        engine = WhisperTurboEngine(config)
        
        # Manually add overlapping segments to the engine's segment list
        engine._segments = [
            _segment("These services", 0.82, 2.82),
            _segment("services here. I am", 1.92, 3.92),
            _segment("woefully", 3.50, 4.20),
            _segment("woefully unprepared for this.", 4.00, 6.50),
        ]
        
        # Poll segments should apply arbiter
        result = engine.poll_segments()
        
        # Arbiter should reduce the number of segments by deduplicating
        assert len(result) < 4  # Less than original 4 segments
        assert len(result) >= 1  # At least some segments remain
        
        # Verify no obvious duplicates
        full_text = " ".join(r.text for r in result)
        assert "services services" not in full_text.lower()
        assert "woefully woefully" not in full_text.lower()
    
    def test_poll_segments_without_arbiter(self) -> None:
        """poll_segments returns raw segments when arbiter is disabled."""
        config = _config(params={"use_segment_arbiter": "false"})
        engine = WhisperTurboEngine(config)
        
        # Manually add overlapping segments
        test_segments = [
            _segment("These services", 0.82, 2.82),
            _segment("services here. I am", 1.92, 3.92),
        ]
        engine._segments = test_segments.copy()
        
        # Poll segments should return raw segments without processing
        result = engine.poll_segments()
        
        # Should return all segments unchanged
        assert len(result) == 2
        assert result[0].text == "These services"
        assert result[1].text == "services here. I am"
    
    def test_poll_segments_empty_list(self) -> None:
        """poll_segments handles empty segment list correctly."""
        config = _config()
        engine = WhisperTurboEngine(config)
        
        # No segments
        engine._segments = []
        
        result = engine.poll_segments()
        
        assert result == []
    
    def test_arbiter_preserves_segment_metadata(self) -> None:
        """Arbiter preserves language and confidence in merged segments."""
        config = _config()
        engine = WhisperTurboEngine(config)
        
        # Add segments with specific metadata
        engine._segments = [
            TranscriptSegment(
                text="First part",
                start_s=0.0,
                end_s=1.0,
                language="fr",
                confidence=0.95,
            ),
            TranscriptSegment(
                text="second part",
                start_s=1.2,
                end_s=2.0,
                language="fr",
                confidence=0.85,
            ),
        ]
        
        result = engine.poll_segments()
        
        # Should have merged due to short gap and lowercase ending
        assert len(result) == 1
        assert result[0].language == "fr"
        # Confidence should be minimum of merged segments
        assert result[0].confidence == 0.85
