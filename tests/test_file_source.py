from __future__ import annotations

from pathlib import Path

import pytest

from vociferous.audio.decoder import AudioDecoder, DecodedAudio
from vociferous.sources import FileSource
from vociferous.domain.model import AudioChunk


class FakeDecoder(AudioDecoder):
    def __init__(self, audio: DecodedAudio) -> None:
        self.audio = audio

    def decode(self, source: str | bytes) -> DecodedAudio:  # noqa: D401
        return self.audio

    def supports_format(self, extension_or_mime: str) -> bool:
        return True

    def to_chunks(self, audio: DecodedAudio, chunk_ms: int):
        yield AudioChunk(
            samples=audio.samples,
            sample_rate=audio.sample_rate,
            channels=audio.channels,
            start_s=0.0,
            end_s=audio.duration_s,
        )


def test_file_source_rejects_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.wav"
    source = FileSource(missing, decoder=FakeDecoder(DecodedAudio(b"", 16000, 1, 0.0)))
    with pytest.raises(FileNotFoundError):
        list(source.stream())


def test_file_source_streams_chunks(tmp_path: Path) -> None:
    wav_path = tmp_path / "dummy.wav"
    wav_path.write_bytes(b"RIFFxxxx")  # file exists, content irrelevant for fake decoder
    decoded = DecodedAudio(samples=b"\x00\x00" * 10, sample_rate=16000, channels=1, duration_s=0.00125)
    source = FileSource(wav_path, decoder=FakeDecoder(decoded))
    chunks = list(source.stream())
    assert len(chunks) == 1
    assert chunks[0].samples == decoded.samples


def test_file_source_fallback_to_wav_decoder(tmp_path: Path) -> None:
    wav_path = tmp_path / "dummy.wav"
    wav_path.write_bytes(b"RIFFxxxx")

    class FailingDecoder(FakeDecoder):
        def decode(self, source: str | bytes) -> DecodedAudio:
            raise RuntimeError("ffmpeg fail")

    source = FileSource(wav_path, decoder=FailingDecoder(DecodedAudio(b"", 16000, 1, 0.0)))
    # Should fallback to WavDecoder and raise because content is invalid WAV
    with pytest.raises(Exception):
        list(source.stream())
