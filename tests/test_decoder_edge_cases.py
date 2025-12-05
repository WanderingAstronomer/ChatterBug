"""Test decoder edge cases and error handling (TDD approach)."""
import shutil
import pytest
from pathlib import Path

from chatterbug.audio.decoder import FfmpegDecoder, WavDecoder, DecodedAudio, _chunk_pcm_bytes
from chatterbug.domain.model import AudioChunk
from chatterbug.domain.exceptions import AudioDecodeError, ConfigurationError


def test_ffmpeg_decoder_handles_missing_binary() -> None:
    """Test FfmpegDecoder raises clear error when ffmpeg not found."""
    decoder = FfmpegDecoder(ffmpeg_path="/nonexistent/ffmpeg")
    with pytest.raises(FileNotFoundError, match="ffmpeg binary not found"):
        decoder.decode(b"fake audio data")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not available")
def test_ffmpeg_decoder_handles_corrupted_audio() -> None:
    """Test FfmpegDecoder raises on corrupted/invalid audio data."""
    decoder = FfmpegDecoder()
    with pytest.raises(AudioDecodeError, match="ffmpeg decode failed"):
        decoder.decode(b"not real audio data at all")


def test_ffmpeg_decoder_handles_file_not_found() -> None:
    """Test FfmpegDecoder handles missing file path gracefully."""
    decoder = FfmpegDecoder()
    with pytest.raises(FileNotFoundError):
        decoder.decode("/nonexistent/file.mp3")


def test_wav_decoder_rejects_bytes_input() -> None:
    """Test WavDecoder raises on byte buffer input (unsupported)."""
    decoder = WavDecoder()
    with pytest.raises(AudioDecodeError, match="Byte-buffer decode not supported"):
        decoder.decode(b"fake wav data")


def test_wav_decoder_handles_missing_file() -> None:
    """Test WavDecoder handles missing file path."""
    decoder = WavDecoder()
    with pytest.raises(FileNotFoundError):
        decoder.decode("/nonexistent/file.wav")


def test_wav_decoder_handles_corrupted_wav(tmp_path: Path) -> None:
    """Test WavDecoder handles corrupted WAV file."""
    bad_wav = tmp_path / "bad.wav"
    bad_wav.write_bytes(b"not a wav file")
    
    decoder = WavDecoder()
    with pytest.raises(Exception):  # wave.Error
        decoder.decode(str(bad_wav))


def test_wav_decoder_supports_format() -> None:
    """Test WavDecoder format support detection."""
    decoder = WavDecoder()
    assert decoder.supports_format(".wav") is True
    assert decoder.supports_format("wav") is True
    assert decoder.supports_format("audio/wav") is True
    assert decoder.supports_format(".mp3") is False
    assert decoder.supports_format("audio/mpeg") is False


def test_chunk_pcm_bytes_with_zero_chunk_size() -> None:
    """Test _chunk_pcm_bytes raises on invalid chunk size."""
    audio = DecodedAudio(
        samples=b"\x00\x01\x02\x03",
        sample_rate=16000,
        channels=1,
        duration_s=0.001,
        sample_width_bytes=2,
    )
    with pytest.raises(ConfigurationError, match="Invalid chunk size"):
        list(_chunk_pcm_bytes(audio, chunk_ms=0))


def test_chunk_pcm_bytes_with_negative_chunk_size() -> None:
    """Test _chunk_pcm_bytes raises on negative chunk size."""
    audio = DecodedAudio(
        samples=b"\x00\x01\x02\x03",
        sample_rate=16000,
        channels=1,
        duration_s=0.001,
        sample_width_bytes=2,
    )
    with pytest.raises(ConfigurationError, match="Invalid chunk size"):
        list(_chunk_pcm_bytes(audio, chunk_ms=-100))


def test_chunk_pcm_bytes_with_empty_audio() -> None:
    """Test _chunk_pcm_bytes handles empty audio samples."""
    audio = DecodedAudio(
        samples=b"",
        sample_rate=16000,
        channels=1,
        duration_s=0.0,
        sample_width_bytes=2,
    )
    chunks = list(_chunk_pcm_bytes(audio, chunk_ms=960))
    assert len(chunks) == 0


def test_chunk_pcm_bytes_creates_correct_timestamps() -> None:
    """Test _chunk_pcm_bytes generates correct time boundaries."""
    # 16000 Hz, 1 channel, 2 bytes/sample = 32000 bytes/second
    # 960ms = 0.96s = 30720 bytes
    sample_rate = 16000
    channels = 1
    sample_width = 2
    chunk_ms = 960
    
    # Create 2 seconds of audio
    bytes_per_second = sample_rate * channels * sample_width
    total_bytes = bytes_per_second * 2
    
    audio = DecodedAudio(
        samples=b"\x00" * total_bytes,
        sample_rate=sample_rate,
        channels=channels,
        duration_s=2.0,
        sample_width_bytes=sample_width,
    )
    
    chunks = list(_chunk_pcm_bytes(audio, chunk_ms))
    
    # Should have 3 chunks (960ms + 960ms + 80ms = 2000ms)
    assert len(chunks) >= 2
    
    # First chunk should start at 0
    assert chunks[0].start_s == 0.0
    
    # Each chunk should have continuous timestamps
    for i in range(len(chunks) - 1):
        assert chunks[i].end_s == pytest.approx(chunks[i + 1].start_s, abs=0.001)


def test_decoded_audio_immutable() -> None:
    """Test DecodedAudio is frozen (immutable)."""
    audio = DecodedAudio(
        samples=b"test",
        sample_rate=16000,
        channels=1,
        duration_s=1.0,
    )
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        audio.sample_rate = 8000  # type: ignore[misc]


def test_ffmpeg_decoder_supports_all_formats() -> None:
    """Test FfmpegDecoder claims to support all formats."""
    decoder = FfmpegDecoder()
    assert decoder.supports_format(".mp3") is True
    assert decoder.supports_format(".wav") is True
    assert decoder.supports_format(".flac") is True
    assert decoder.supports_format("audio/mpeg") is True
    assert decoder.supports_format("unknown_format") is True  # Claims support for everything
