from __future__ import annotations

from typing import Iterable

from vociferous.sources import MicrophoneSource
from vociferous.audio.recorder import MicrophoneRecorder


class FakeRecorder(MicrophoneRecorder):
    def __init__(self, chunks: Iterable[bytes]) -> None:
        self._chunks = list(chunks)

    def stream_chunks(
        self,
        *,
        sample_rate: int,
        channels: int,
        chunk_ms: int,
        stop_event=None,
        sample_width_bytes: int = 2,
    ):
        for chunk in self._chunks:
            if stop_event is not None and stop_event.is_set():
                break
            yield chunk


def _chunk_bytes(sample_rate: int, chunk_ms: int, channels: int = 1, sample_width_bytes: int = 2) -> bytes:
    samples = int(sample_rate * (chunk_ms / 1000))
    return b"\x00" * samples * channels * sample_width_bytes


def test_microphone_source_streams_chunks_with_timestamps() -> None:
    chunk = _chunk_bytes(sample_rate=16000, chunk_ms=100)
    source = MicrophoneSource(
        recorder=FakeRecorder([chunk, chunk]),
        sample_rate=16000,
        channels=1,
        chunk_ms=100,
        sample_width_bytes=2,
    )

    chunks = list(source.stream())
    assert len(chunks) == 2
    assert chunks[0].start_s == 0.0
    assert chunks[0].end_s == 0.1
    assert chunks[1].start_s == 0.1
    assert chunks[1].end_s == 0.2
    assert chunks[0].samples == chunk


def test_microphone_source_stop_interrupts_stream() -> None:
    chunk = _chunk_bytes(sample_rate=16000, chunk_ms=100)
    source = MicrophoneSource(
        recorder=FakeRecorder([chunk, chunk, chunk]),
        sample_rate=16000,
        channels=1,
        chunk_ms=100,
        sample_width_bytes=2,
    )

    stream = source.stream()
    first = next(stream)
    assert first.start_s == 0.0
    source.stop()
    remaining = list(stream)
    assert remaining == []
