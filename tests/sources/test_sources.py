"""Source abstractions contract tests."""

from __future__ import annotations

import wave
from pathlib import Path

import pytest

from vociferous.sources import FileSource, MemorySource, MicSource

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "audio" / "sample_audio"
SAMPLE_FILE = SAMPLES_DIR / "ASR_Test.flac"


class DummyRecorder:
    """Fake recorder that yields a fixed number of PCM chunks."""

    def __init__(self, chunk: bytes, count: int = 2) -> None:
        self.chunk = chunk
        self.count = count
        self.sample_width_bytes = 2

    def stream_chunks(self, *, sample_rate: int, channels: int, chunk_ms: int, stop_event, sample_width_bytes: int = 2):
        # Emit a small number of chunks; MicSource will stop based on duration
        for _ in range(self.count):
            yield self.chunk


@pytest.mark.skipif(not SAMPLE_FILE.exists(), reason="Sample audio missing")
def test_file_source_resolves_path(tmp_path: Path) -> None:
    source = FileSource(SAMPLE_FILE)
    resolved = source.resolve_to_path(tmp_path)
    assert resolved.exists()
    assert resolved == SAMPLE_FILE


def test_memory_source_writes_wav(tmp_path: Path) -> None:
    # 0.1s of silence at 16kHz mono, 16-bit
    pcm = b"\x00" * (16000 // 10 * 2)
    source = MemorySource(pcm, output_path=tmp_path / "mem.wav")
    path = source.resolve_to_path(tmp_path)
    assert path.exists()

    with wave.open(str(path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 16000
        assert wf.getsampwidth() == 2
        duration = wf.getnframes() / float(wf.getframerate())
        assert duration > 0.05


def test_mic_source_uses_recorder(tmp_path: Path) -> None:
    # Provide two 0.05s chunks -> total 0.1s of audio
    chunk = b"\x01\x00" * int(16000 * 0.05)
    recorder = DummyRecorder(chunk, count=2)
    source = MicSource(
        duration_seconds=0.1,
        sample_rate=16000,
        channels=1,
        sample_width_bytes=2,
        recorder=recorder,
        output_path=tmp_path / "mic.wav",
    )
    path = source.resolve_to_path(tmp_path)
    assert path.exists()

    with wave.open(str(path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 16000
        assert wf.getsampwidth() == 2
        duration = wf.getnframes() / float(wf.getframerate())
        # Should capture at least 0.09s given duration cap
        assert duration >= 0.09
