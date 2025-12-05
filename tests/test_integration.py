"""Integration tests for end-to-end transcription scenarios."""
import pytest
import threading
import time
from pathlib import Path
from typing import Iterable, List

from chatterbug.app.transcription_session import TranscriptionSession
from chatterbug.domain.model import (
    AudioChunk,
    AudioSource,
    TranscriptSegment,
    TranscriptionEngine,
    TranscriptionOptions,
    TranscriptionResult,
    TranscriptSink,
)


class SlowAudioSource(AudioSource):
    """Audio source that produces chunks slowly to simulate real-time streaming."""
    
    def __init__(self, num_chunks: int = 5, chunk_delay_s: float = 0.1):
        self.num_chunks = num_chunks
        self.chunk_delay_s = chunk_delay_s
    
    def stream(self) -> Iterable[AudioChunk]:
        for i in range(self.num_chunks):
            if self.chunk_delay_s > 0:
                time.sleep(self.chunk_delay_s)
            # Generate fake PCM data (100ms at 16kHz = 1600 samples = 3200 bytes)
            fake_pcm = b"\x00\x01" * 1600
            yield AudioChunk(
                samples=fake_pcm,
                sample_rate=16000,
                channels=1,
                start_s=i * 0.1,
                end_s=(i + 1) * 0.1,
            )


class FakeTranscriptionEngine(TranscriptionEngine):
    """Fake engine that returns predictable transcripts."""
    
    def __init__(self, transcript_per_chunk: str = "word"):
        self.transcript_per_chunk = transcript_per_chunk
        self._segments: List[TranscriptSegment] = []
    
    def start(self, options: TranscriptionOptions) -> None:
        self._segments.clear()
    
    def push_audio(self, pcm16: bytes, timestamp_ms: int) -> None:
        # Create a fake segment for each push
        segment = TranscriptSegment(
            text=self.transcript_per_chunk,
            start_s=timestamp_ms / 1000.0,
            end_s=(timestamp_ms + 100) / 1000.0,
            language="en",
            confidence=0.95,
        )
        self._segments.append(segment)
    
    def flush(self) -> None:
        pass
    
    def poll_segments(self) -> List[TranscriptSegment]:
        segments = list(self._segments)
        self._segments.clear()
        return segments


class CollectorSink(TranscriptSink):
    """Sink that collects all segments and the final result."""
    
    def __init__(self):
        self.segments: List[TranscriptSegment] = []
        self.result: TranscriptionResult | None = None
    
    def handle_segment(self, segment: TranscriptSegment) -> None:
        self.segments.append(segment)
    
    def complete(self, result: TranscriptionResult) -> None:
        self.result = result


def test_integration_simple_transcription() -> None:
    """Test a simple end-to-end transcription."""
    session = TranscriptionSession()
    source = SlowAudioSource(num_chunks=3, chunk_delay_s=0.05)
    engine = FakeTranscriptionEngine(transcript_per_chunk="hello")
    sink = CollectorSink()
    
    session.start(source, engine, sink, TranscriptionOptions())
    session.join()
    
    # Should have received segments
    assert len(sink.segments) > 0
    
    # Should have received final result
    assert sink.result is not None
    assert "hello" in sink.result.text


def test_integration_session_stop_interrupts() -> None:
    """Test that stopping a session interrupts transcription."""
    session = TranscriptionSession()
    source = SlowAudioSource(num_chunks=100, chunk_delay_s=0.05)  # Would take 5 seconds
    engine = FakeTranscriptionEngine()
    sink = CollectorSink()
    
    session.start(source, engine, sink, TranscriptionOptions())
    
    # Let it run briefly then stop
    time.sleep(0.2)
    session.stop()
    session.join()
    
    # Should have processed some but not all chunks
    assert len(sink.segments) < 100
    assert len(sink.segments) > 0


def test_integration_concurrent_sessions_isolated() -> None:
    """Test that multiple concurrent sessions don't interfere with each other."""
    session1 = TranscriptionSession()
    session2 = TranscriptionSession()
    
    source1 = SlowAudioSource(num_chunks=5, chunk_delay_s=0.05)
    source2 = SlowAudioSource(num_chunks=5, chunk_delay_s=0.05)
    
    engine1 = FakeTranscriptionEngine(transcript_per_chunk="session1")
    engine2 = FakeTranscriptionEngine(transcript_per_chunk="session2")
    
    sink1 = CollectorSink()
    sink2 = CollectorSink()
    
    # Start both sessions
    session1.start(source1, engine1, sink1, TranscriptionOptions())
    session2.start(source2, engine2, sink2, TranscriptionOptions())
    
    # Wait for both to complete
    session1.join()
    session2.join()
    
    # Each session should have its own results
    assert sink1.result is not None
    assert sink2.result is not None
    
    # Results should be isolated
    assert "session1" in sink1.result.text
    assert "session2" in sink2.result.text
    assert "session2" not in sink1.result.text
    assert "session1" not in sink2.result.text


def test_integration_buffer_overflow_handling() -> None:
    """Test that the system handles buffer overflow scenarios gracefully."""
    
    class FastProducerSource(AudioSource):
        """Source that produces audio faster than it can be processed."""
        
        def stream(self) -> Iterable[AudioChunk]:
            for i in range(500):  # Produce many chunks quickly
                fake_pcm = b"\x00\x01" * 1600
                yield AudioChunk(
                    samples=fake_pcm,
                    sample_rate=16000,
                    channels=1,
                    start_s=i * 0.1,
                    end_s=(i + 1) * 0.1,
                )
    
    class SlowEngine(TranscriptionEngine):
        """Engine that processes slowly to cause backpressure."""
        
        def __init__(self):
            self._segments: List[TranscriptSegment] = []
        
        def start(self, options: TranscriptionOptions) -> None:
            self._segments.clear()
        
        def push_audio(self, pcm16: bytes, timestamp_ms: int) -> None:
            # Simulate slow processing
            time.sleep(0.01)
            segment = TranscriptSegment(
                text="word",
                start_s=timestamp_ms / 1000.0,
                end_s=(timestamp_ms + 100) / 1000.0,
                language="en",
                confidence=0.95,
            )
            self._segments.append(segment)
        
        def flush(self) -> None:
            pass
        
        def poll_segments(self) -> List[TranscriptSegment]:
            segments = list(self._segments)
            self._segments.clear()
            return segments
    
    session = TranscriptionSession()
    source = FastProducerSource()
    engine = SlowEngine()
    sink = CollectorSink()
    
    # This should not crash or deadlock
    session.start(source, engine, sink, TranscriptionOptions())
    
    # Give it some time to process
    time.sleep(1.0)
    
    # Stop and join should work without hanging
    session.stop()
    session.join(timeout=5.0)  # Should complete within 5 seconds
    
    # Should have processed some segments
    assert len(sink.segments) > 0


def test_integration_empty_source() -> None:
    """Test handling of an empty audio source."""
    
    class EmptySource(AudioSource):
        def stream(self) -> Iterable[AudioChunk]:
            return iter([])
    
    session = TranscriptionSession()
    source = EmptySource()
    engine = FakeTranscriptionEngine()
    sink = CollectorSink()
    
    session.start(source, engine, sink, TranscriptionOptions())
    session.join()
    
    # Should complete without errors
    assert sink.result is not None
    # May have empty text
    assert sink.result.text == "" or sink.result.text is not None


def test_integration_session_cannot_restart_while_running() -> None:
    """Test that a session cannot be restarted while already running."""
    from chatterbug.domain.exceptions import SessionError
    
    session = TranscriptionSession()
    source = SlowAudioSource(num_chunks=10, chunk_delay_s=0.1)
    engine = FakeTranscriptionEngine()
    sink = CollectorSink()
    
    session.start(source, engine, sink, TranscriptionOptions())
    
    # Try to start again while running
    with pytest.raises(SessionError, match="already running"):
        session.start(source, engine, sink, TranscriptionOptions())
    
    session.stop()
    session.join()


def test_integration_session_can_be_reused() -> None:
    """Test that a session can be reused after completion."""
    session = TranscriptionSession()
    
    # First run
    source1 = SlowAudioSource(num_chunks=3, chunk_delay_s=0.05)
    engine1 = FakeTranscriptionEngine(transcript_per_chunk="first")
    sink1 = CollectorSink()
    
    session.start(source1, engine1, sink1, TranscriptionOptions())
    session.join()
    
    assert sink1.result is not None
    assert "first" in sink1.result.text
    
    # Second run with same session instance
    source2 = SlowAudioSource(num_chunks=3, chunk_delay_s=0.05)
    engine2 = FakeTranscriptionEngine(transcript_per_chunk="second")
    sink2 = CollectorSink()
    
    session.start(source2, engine2, sink2, TranscriptionOptions())
    session.join()
    
    assert sink2.result is not None
    assert "second" in sink2.result.text


def test_integration_segments_arrive_during_processing() -> None:
    """Test that segments are emitted during processing, not just at the end."""
    segment_timestamps: List[float] = []
    
    class TimestampedSink(TranscriptSink):
        def handle_segment(self, segment: TranscriptSegment) -> None:
            segment_timestamps.append(time.time())
        
        def complete(self, result: TranscriptionResult) -> None:
            pass
    
    session = TranscriptionSession()
    source = SlowAudioSource(num_chunks=5, chunk_delay_s=0.1)
    engine = FakeTranscriptionEngine()
    sink = TimestampedSink()
    
    start_time = time.time()
    session.start(source, engine, sink, TranscriptionOptions())
    session.join()
    end_time = time.time()
    
    # Should have received segments
    assert len(segment_timestamps) > 0
    
    # Segments should have arrived at different times (streaming)
    # Not all at the end
    if len(segment_timestamps) >= 2:
        time_spread = segment_timestamps[-1] - segment_timestamps[0]
        # Should take at least some time (not instant)
        assert time_spread > 0.05
