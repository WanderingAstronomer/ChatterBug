"""Unit tests for PolishingSink decorator (TDD)."""
from __future__ import annotations

import pytest

from chatterbug.app.sinks import PolishingSink
from chatterbug.domain.model import TranscriptSegment, TranscriptionResult


class MockSink:
    """Mock sink that records what it receives."""
    
    def __init__(self):
        self.segments = []
        self.result = None
        
    def handle_segment(self, segment: TranscriptSegment) -> None:
        self.segments.append(segment)
        
    def complete(self, result: TranscriptionResult) -> None:
        self.result = result


class MockPolisher:
    """Mock polisher that uppercases text."""
    
    def __init__(self):
        self.calls = []
        
    def polish(self, text: str) -> str:
        self.calls.append(text)
        return text.upper()


def test_polishing_sink_forwards_segments_without_polishing():
    """Test that segments are forwarded directly without polishing."""
    inner_sink = MockSink()
    polisher = MockPolisher()
    sink = PolishingSink(inner_sink, polisher)
    
    segment = TranscriptSegment(
        text="hello world",
        start_s=0.0,
        end_s=1.0,
        language="en",
        confidence=0.95
    )
    
    sink.handle_segment(segment)
    
    assert len(inner_sink.segments) == 1
    assert inner_sink.segments[0] == segment
    assert len(polisher.calls) == 0  # Should not polish segments


def test_polishing_sink_polishes_final_result():
    """Test that final result text is polished before forwarding."""
    inner_sink = MockSink()
    polisher = MockPolisher()
    sink = PolishingSink(inner_sink, polisher)
    
    result = TranscriptionResult(
        text="hello world",
        segments=tuple(),
        model_name="test-model",
        device="cpu",
        precision="int8",
        engine="whisper_turbo",
        duration_s=1.0,
    )
    
    sink.complete(result)
    
    assert inner_sink.result is not None
    assert inner_sink.result.text == "HELLO WORLD"
    assert len(polisher.calls) == 1
    assert polisher.calls[0] == "hello world"


def test_polishing_sink_preserves_other_result_fields():
    """Test that polishing only modifies text field, preserving others."""
    inner_sink = MockSink()
    polisher = MockPolisher()
    sink = PolishingSink(inner_sink, polisher)
    
    segments = (
        TranscriptSegment(
            text="segment one",
            start_s=0.0,
            end_s=1.0,
            language="en",
            confidence=0.95
        ),
    )
    
    result = TranscriptionResult(
        text="original text",
        segments=segments,
        model_name="test-model",
        device="cuda",
        precision="float16",
        engine="voxtral",
        duration_s=5.5,
        warnings=("warning1", "warning2"),
    )
    
    sink.complete(result)
    
    polished = inner_sink.result
    assert polished is not None
    assert polished.text == "ORIGINAL TEXT"
    assert polished.segments == segments
    assert polished.model_name == "test-model"
    assert polished.device == "cuda"
    assert polished.precision == "float16"
    assert polished.engine == "voxtral"
    assert polished.duration_s == 5.5
    assert polished.warnings == ("warning1", "warning2")


def test_polishing_sink_handles_empty_text():
    """Test that polishing works with empty text."""
    inner_sink = MockSink()
    polisher = MockPolisher()
    sink = PolishingSink(inner_sink, polisher)
    
    result = TranscriptionResult(
        text="",
        segments=tuple(),
        model_name="test-model",
        device="cpu",
        precision="int8",
        engine="whisper_turbo",
        duration_s=0.0,
    )
    
    sink.complete(result)
    
    assert inner_sink.result is not None
    assert inner_sink.result.text == ""
    assert len(polisher.calls) == 1


def test_polishing_sink_handles_multiple_results():
    """Test that polisher is called for each complete() invocation."""
    inner_sink = MockSink()
    polisher = MockPolisher()
    sink = PolishingSink(inner_sink, polisher)
    
    for i in range(3):
        result = TranscriptionResult(
            text=f"text {i}",
            segments=tuple(),
            model_name="test-model",
            device="cpu",
            precision="int8",
            engine="whisper_turbo",
            duration_s=1.0,
        )
        sink.complete(result)
    
    assert len(polisher.calls) == 3
    assert polisher.calls == ["text 0", "text 1", "text 2"]
