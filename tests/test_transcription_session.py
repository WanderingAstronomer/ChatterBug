from __future__ import annotations

from typing import Iterable

from chatterbug.app import TranscriptionSession
from chatterbug.app.sinks import PolishingSink
from chatterbug.domain.model import (
    AudioChunk,
    EngineMetadata,
    TranscriptSegment,
    TranscriptionEngine,
    TranscriptionOptions,
)


class FakeSource:
    def stream(self) -> Iterable[AudioChunk]:
        yield AudioChunk(samples=b"", sample_rate=16000, channels=1, start_s=0.0, end_s=0.1)


class FakeEngine(TranscriptionEngine):
    def __init__(self):
        self._segments: list[TranscriptSegment] = []

    def start(self, options: TranscriptionOptions) -> None:
        self._segments.clear()

    def push_audio(self, pcm16: bytes, timestamp_ms: int) -> None:
        start_s = timestamp_ms / 1000.0
        self._segments.append(
            TranscriptSegment(text="ok", start_s=start_s, end_s=start_s + 0.1, language="en", confidence=1.0)
        )

    def flush(self) -> None:
        pass

    def poll_segments(self) -> list[TranscriptSegment]:
        segs = list(self._segments)
        self._segments.clear()
        return segs

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(model_name="test-model", device="cpu", precision="int8")


class CollectSink:
    def __init__(self) -> None:
        self.segments: list[TranscriptSegment] = []
        self.completed = False
        self.result_text: str | None = None

    def handle_segment(self, segment: TranscriptSegment) -> None:
        self.segments.append(segment)

    def complete(self, result) -> None:
        self.completed = True
        self.result_text = result.text


def test_transcription_session_join_waits_and_collects() -> None:
    source = FakeSource()
    engine = FakeEngine()
    sink = CollectSink()
    session = TranscriptionSession()
    session.start(source, engine, sink, TranscriptionOptions(), engine_kind="whisper_turbo")
    session.join()
    assert sink.completed is True
    assert len(sink.segments) == 1


class FakePolisher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def polish(self, text: str) -> str:
        self.calls.append(text)
        return f"polished: {text}"


def test_transcription_session_applies_polisher() -> None:
    """Test that polishing works via PolishingSink decorator."""
    source = FakeSource()
    engine = FakeEngine()
    base_sink = CollectSink()
    polisher = FakePolisher()
    # Wrap the sink with polishing decorator
    sink = PolishingSink(base_sink, polisher)
    session = TranscriptionSession()
    session.start(
        source,
        engine,
        sink,
        TranscriptionOptions(),
        engine_kind="whisper_turbo",
    )
    session.join()
    assert polisher.calls == ["ok"]
    assert base_sink.result_text == "polished: ok"
