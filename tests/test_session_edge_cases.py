"""Test TranscriptionSession edge cases and error handling (TDD approach)."""
import pytest
from typing import Iterable

from chatterbug.app.transcription_session import TranscriptionSession
from chatterbug.domain.model import (
    AudioChunk,
    TranscriptSegment,
    TranscriptionEngine,
    TranscriptionOptions,
    TranscriptionResult,
)
from chatterbug.domain.exceptions import SessionError, EngineError, ConfigurationError


class ErrorSource:
    """Fake audio source that raises an error."""

    def __init__(self, error: Exception):
        self.error = error

    def stream(self) -> Iterable[AudioChunk]:
        raise self.error


class ErrorEngine(TranscriptionEngine):
    """Fake engine that raises an error on start."""

    def __init__(self, error: Exception):
        self.error = error

    def start(self, options: TranscriptionOptions) -> None:
        raise self.error

    def push_audio(self, pcm16: bytes, timestamp_ms: int) -> None:  # pragma: no cover - never reached
        raise self.error

    def flush(self) -> None:
        pass

    def poll_segments(self) -> list[TranscriptSegment]:
        return []


class SlowSource:
    """Source that yields chunks with delays."""

    def __init__(self, count: int = 3, delay_s: float = 0.01):
        self.count = count
        self.delay_s = delay_s

    def stream(self) -> Iterable[AudioChunk]:
        import time

        for i in range(self.count):
            time.sleep(self.delay_s)
            yield AudioChunk(
                samples=b"\x00" * 100,
                sample_rate=16000,
                channels=1,
                start_s=float(i),
                end_s=float(i + 1),
            )


class CountingSink:
    """Sink that counts segments and completion calls."""

    def __init__(self):
        self.segment_count = 0
        self.complete_count = 0
        self.segments = []
        self.result = None

    def handle_segment(self, segment: TranscriptSegment) -> None:
        self.segment_count += 1
        self.segments.append(segment)

    def complete(self, result: TranscriptionResult) -> None:
        self.complete_count += 1
        self.result = result


class FakeSource:
    def stream(self) -> Iterable[AudioChunk]:
        yield AudioChunk(samples=b"test", sample_rate=16000, channels=1, start_s=0.0, end_s=0.1)


class FakeEngine(TranscriptionEngine):
    def __init__(self):
        self._segments: list[TranscriptSegment] = []

    def start(self, options: TranscriptionOptions) -> None:
        self._segments.clear()

    def push_audio(self, pcm16: bytes, timestamp_ms: int) -> None:
        start_s = timestamp_ms / 1000.0
        self._segments.append(
            TranscriptSegment(text="test", start_s=start_s, end_s=start_s + 0.1, language="en", confidence=1.0)
        )

    def flush(self) -> None:
        return None

    def poll_segments(self) -> list[TranscriptSegment]:
        segs = list(self._segments)
        self._segments.clear()
        return segs


def test_session_cannot_start_twice() -> None:
    """Test TranscriptionSession raises if started while already running."""
    session = TranscriptionSession()
    source = SlowSource(count=5, delay_s=0.1)
    engine = FakeEngine()
    sink = CountingSink()

    session.start(source, engine, sink, TranscriptionOptions())

    with pytest.raises(SessionError, match="already running"):
        session.start(source, engine, sink, TranscriptionOptions())

    session.stop()
    session.join()


def test_session_join_propagates_source_error() -> None:
    """Test session.join() raises exception from source."""
    session = TranscriptionSession()
    source = ErrorSource(ConfigurationError("Source error"))
    engine = FakeEngine()
    sink = CountingSink()

    session.start(source, engine, sink, TranscriptionOptions())

    with pytest.raises(ConfigurationError, match="Source error"):
        session.join()


def test_session_join_propagates_engine_error() -> None:
    """Test session.join() raises exception from engine."""
    session = TranscriptionSession()
    source = FakeSource()
    engine = ErrorEngine(EngineError("Engine error"))
    sink = CountingSink()

    session.start(source, engine, sink, TranscriptionOptions())

    with pytest.raises(EngineError, match="Engine error"):
        session.join()


def test_session_stop_interrupts_processing() -> None:
    """Test session.stop() interrupts a long-running transcription."""
    import time

    session = TranscriptionSession()
    source = SlowSource(count=100, delay_s=0.05)  # Would take 5 seconds
    engine = FakeEngine()
    sink = CountingSink()

    session.start(source, engine, sink, TranscriptionOptions())
    time.sleep(0.1)  # Let it process a bit
    session.stop()
    session.join()

    # Should have processed fewer than 100 chunks
    assert sink.segment_count < 100
    assert sink.complete_count == 0  # Complete not called due to early stop


def test_session_join_without_start() -> None:
    """Test session.join() when never started doesn't hang."""
    session = TranscriptionSession()
    session.join()  # Should return immediately


def test_session_join_timeout() -> None:
    """Test session.join() respects timeout parameter."""
    import time

    session = TranscriptionSession()
    source = SlowSource(count=100, delay_s=0.1)
    engine = FakeEngine()
    sink = CountingSink()

    session.start(source, engine, sink, TranscriptionOptions())
    start = time.time()
    session.join(timeout=0.2)
    elapsed = time.time() - start

    # Should timeout around 0.2 seconds, not wait for all 100 chunks
    assert elapsed < 0.5
    session.stop()


def test_session_multiple_stop_calls() -> None:
    """Test calling stop() multiple times doesn't cause issues."""
    session = TranscriptionSession()
    source = FakeSource()
    engine = FakeEngine()
    sink = CountingSink()

    session.start(source, engine, sink, TranscriptionOptions())
    session.stop()
    session.stop()  # Second stop should be safe
    session.stop()  # Third stop should be safe
    session.join()


def test_session_sink_receives_complete_on_success() -> None:
    """Test sink.complete() is called with correct result on success."""
    session = TranscriptionSession()
    source = FakeSource()
    engine = FakeEngine()
    sink = CountingSink()

    session.start(source, engine, sink, TranscriptionOptions(), engine_kind="whisper_turbo")
    session.join()

    assert sink.complete_count == 1
    assert sink.result is not None
    assert sink.result.engine == "whisper_turbo"
    assert len(sink.result.segments) == 1


def test_session_error_propagates_to_join() -> None:
    """Test that errors during transcription propagate to join()."""

    class ErrorDuringIterationEngine(TranscriptionEngine):
        """Engine that raises error during push."""

        def start(self, options: TranscriptionOptions) -> None:
            self._raised = False

        def push_audio(self, pcm16: bytes, timestamp_ms: int) -> None:
            if not self._raised:
                self._raised = True
                raise RuntimeError("Test error during iteration")

        def flush(self) -> None:
            pass

        def poll_segments(self) -> list[TranscriptSegment]:
            return []

    session = TranscriptionSession()
    source = FakeSource()
    engine = ErrorDuringIterationEngine()
    sink = CountingSink()

    session.start(source, engine, sink, TranscriptionOptions())

    with pytest.raises(EngineError, match="Test error during iteration"):
        session.join()

    # Note: Due to the exception handling in TranscriptionSession,
    # complete() may still be called before the exception is stored.
    # This documents current behavior.


def test_session_handles_empty_transcription() -> None:
    """Test session handles case where no segments are produced."""

    class EmptyEngine(TranscriptionEngine):
        def start(self, options: TranscriptionOptions) -> None:
            self._segments: list[TranscriptSegment] = []

        def push_audio(self, pcm16: bytes, timestamp_ms: int) -> None:
            pass

        def flush(self) -> None:
            pass

        def poll_segments(self) -> list[TranscriptSegment]:
            segs = list(self._segments)
            self._segments.clear()
            return segs

    session = TranscriptionSession()
    source = FakeSource()
    engine = EmptyEngine()
    sink = CountingSink()

    session.start(source, engine, sink, TranscriptionOptions())
    session.join()

    assert sink.segment_count == 0
    assert sink.complete_count == 1
    result = sink.result
    assert result is not None
    assert result.text == ""
    assert len(result.segments) == 0
    assert result.duration_s == 0.0
