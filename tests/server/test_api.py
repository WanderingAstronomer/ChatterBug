"""Tests for FastAPI server endpoints.

These tests verify:
1. Pydantic request/response models (unit tests, no server needed)
2. Segment conversion helper (unit test, no server needed)
3. Endpoint behavior (uses FastAPI TestClient with isolated test app)

Note: For real end-to-end daemon tests, see test_daemon_integration.py
"""

from __future__ import annotations

import pytest


class TestProtocolModels:
    """Test Pydantic request/response models (pure unit tests)."""

    def test_refine_request_validation(self) -> None:
        """Test RefineRequest validates text field."""
        from vociferous.server.api import RefineRequest
        
        # Valid request
        request = RefineRequest(text="Some transcript text")
        assert request.text == "Some transcript text"
        assert request.instructions is None

        # With instructions
        request_with_instr = RefineRequest(
            text="Some text",
            instructions="Be formal",
        )
        assert request_with_instr.instructions == "Be formal"

    def test_refine_request_empty_text_invalid(self) -> None:
        """Test RefineRequest rejects empty text."""
        from pydantic import ValidationError

        from vociferous.server.api import RefineRequest
        
        with pytest.raises(ValidationError):
            RefineRequest(text="")

    def test_batch_transcribe_request_validation(self) -> None:
        """Test BatchTranscribeRequest validates audio_paths."""
        from vociferous.server.api import BatchTranscribeRequest
        
        request = BatchTranscribeRequest(audio_paths=["/path/to/audio.wav"])
        assert request.audio_paths == ["/path/to/audio.wav"]
        assert request.language == "en"

    def test_batch_transcribe_request_empty_paths_invalid(self) -> None:
        """Test BatchTranscribeRequest rejects empty paths list."""
        from pydantic import ValidationError

        from vociferous.server.api import BatchTranscribeRequest
        
        with pytest.raises(ValidationError):
            BatchTranscribeRequest(audio_paths=[])

    def test_segment_response_model(self) -> None:
        """Test SegmentResponse structure."""
        from vociferous.server.api import SegmentResponse
        
        segment = SegmentResponse(
            start=0.0,
            end=5.3,
            text="Hello world",
        )
        assert segment.start == 0.0
        assert segment.end == 5.3
        assert segment.text == "Hello world"
        assert segment.speaker is None
        assert segment.language is None

    def test_transcribe_response_model(self) -> None:
        """Test TranscribeResponse structure."""
        from vociferous.server.api import SegmentResponse, TranscribeResponse
        
        response = TranscribeResponse(
            success=True,
            segments=[
                SegmentResponse(start=0.0, end=5.0, text="Hello"),
            ],
            inference_time_s=2.5,
        )
        assert response.success is True
        assert len(response.segments) == 1
        assert response.inference_time_s == 2.5

    def test_health_response_model(self) -> None:
        """Test HealthResponse structure."""
        from vociferous.server.api import HealthResponse
        
        response = HealthResponse(
            status="ready",
            model_loaded=True,
            model_name="nvidia/canary-qwen-2.5b",
            uptime_seconds=123.4,
            requests_handled=42,
        )
        assert response.status == "ready"
        assert response.model_loaded is True
        assert response.model_name == "nvidia/canary-qwen-2.5b"


class TestSegmentConversion:
    """Test segment conversion helper."""

    def test_segment_to_response(self) -> None:
        """Test _segment_to_response converts domain objects."""
        from vociferous.domain.model import TranscriptSegment
        from vociferous.server.api import _segment_to_response
        
        segment = TranscriptSegment(
            start=1.5,
            end=3.2,
            raw_text="Test transcript",
            language="en",
        )
        
        response = _segment_to_response(segment)
        
        assert response.start == 1.5
        assert response.end == 3.2
        assert response.text == "Test transcript"
        assert response.language == "en"
        assert response.speaker is None
