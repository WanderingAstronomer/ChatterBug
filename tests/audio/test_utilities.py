"""Tests for audio utilities module."""

import pytest

from vociferous.audio.utilities import (
    validate_pcm_chunk,
    chunk_pcm_bytes,
    apply_noise_gate,
    trim_trailing_silence,
    ms_to_seconds,
    seconds_to_ms,
    bytes_to_samples,
    samples_to_bytes,
    duration_to_samples,
    samples_to_duration,
)
from vociferous.domain.exceptions import ConfigurationError


class TestValidatePcmChunk:
    """Tests for validate_pcm_chunk function."""
    
    def test_accepts_expected_size(self) -> None:
        """Valid chunk passes validation."""
        # 100ms at 16kHz mono int16 => 1600 samples => 3200 bytes
        data = b"\x00\x00" * 1600
        validate_pcm_chunk(data, sample_rate=16000, channels=1, chunk_ms=100)
    
    def test_rejects_empty_chunk(self) -> None:
        """Empty chunk raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Empty audio chunk"):
            validate_pcm_chunk(b"", sample_rate=16000, channels=1, chunk_ms=100)
    
    def test_rejects_wrong_size(self) -> None:
        """Wrong size chunk raises ConfigurationError."""
        data = b"\x00\x00" * 10  # Too small
        with pytest.raises(ConfigurationError, match="Unexpected chunk size"):
            validate_pcm_chunk(data, sample_rate=16000, channels=1, chunk_ms=100)
    
    def test_handles_stereo(self) -> None:
        """Stereo audio is handled correctly."""
        # 100ms at 16kHz stereo int16 => 1600 samples * 2 channels => 6400 bytes
        data = b"\x00\x00" * 3200
        validate_pcm_chunk(data, sample_rate=16000, channels=2, chunk_ms=100)


class TestChunkPcmBytes:
    """Tests for chunk_pcm_bytes function."""
    
    def test_chunks_audio_correctly(self) -> None:
        """Audio is chunked into correct sizes."""
        # 1 second of audio at 16kHz mono
        pcm = b"\x00\x00" * 16000  # 32000 bytes
        
        chunks = list(chunk_pcm_bytes(pcm, sample_rate=16000, channels=1, chunk_ms=500))
        
        assert len(chunks) == 2
        assert chunks[0].start_s == 0.0
        assert chunks[0].end_s == 0.5
        assert chunks[1].start_s == 0.5
        assert chunks[1].end_s == 1.0
    
    def test_handles_partial_last_chunk(self) -> None:
        """Partial last chunk is included."""
        # 750ms of audio
        pcm = b"\x00\x00" * 12000  # 24000 bytes
        
        chunks = list(chunk_pcm_bytes(pcm, sample_rate=16000, channels=1, chunk_ms=500))
        
        assert len(chunks) == 2
        assert len(chunks[1].samples) < 16000  # Partial chunk
    
    def test_raises_on_invalid_chunk_size(self) -> None:
        """Invalid chunk size raises error."""
        pcm = b"\x00\x00" * 100
        
        with pytest.raises(ConfigurationError):
            list(chunk_pcm_bytes(pcm, sample_rate=16000, channels=1, chunk_ms=0))


class TestApplyNoiseGate:
    """Tests for apply_noise_gate function."""
    
    def test_zeros_low_amplitude_samples(self) -> None:
        """Samples below threshold are zeroed."""
        # Create samples with known values
        import array
        arr = array.array('h', [10, 50, 100, 5, 200])
        pcm = arr.tobytes()
        
        result = apply_noise_gate(pcm, threshold=60)
        
        result_arr = array.array('h')
        result_arr.frombytes(result)
        
        assert result_arr[0] == 0  # 10 < 60, zeroed
        assert result_arr[1] == 0  # 50 < 60, zeroed
        assert result_arr[2] == 100  # 100 >= 60, kept
        assert result_arr[3] == 0  # 5 < 60, zeroed
        assert result_arr[4] == 200  # 200 >= 60, kept
    
    def test_ignores_non_int16(self) -> None:
        """Non-int16 audio is returned unchanged."""
        pcm = b"\x01\x02\x03\x04"
        
        result = apply_noise_gate(pcm, threshold=100, sample_width_bytes=4)
        
        assert result == pcm


class TestTrimTrailingSilence:
    """Tests for trim_trailing_silence function."""
    
    def test_removes_trailing_silence(self) -> None:
        """Trailing silence is removed."""
        import array
        arr = array.array('h', [100, 200, 300, 5, 5, 5])
        pcm = arr.tobytes()
        
        result = trim_trailing_silence(pcm, threshold=64)
        
        result_arr = array.array('h')
        result_arr.frombytes(result)
        
        assert len(result_arr) == 3  # Only the first 3 samples kept
        assert list(result_arr) == [100, 200, 300]
    
    def test_keeps_audio_with_no_trailing_silence(self) -> None:
        """Audio without trailing silence is unchanged."""
        import array
        arr = array.array('h', [100, 200, 300])
        pcm = arr.tobytes()
        
        result = trim_trailing_silence(pcm, threshold=64)
        
        assert result == pcm


class TestConversionFunctions:
    """Tests for time/sample conversion utilities."""
    
    def test_ms_to_seconds(self) -> None:
        """Milliseconds to seconds conversion."""
        assert ms_to_seconds(1000) == 1.0
        assert ms_to_seconds(500) == 0.5
        assert ms_to_seconds(0) == 0.0
    
    def test_seconds_to_ms(self) -> None:
        """Seconds to milliseconds conversion."""
        assert seconds_to_ms(1.0) == 1000
        assert seconds_to_ms(0.5) == 500
        assert seconds_to_ms(1.5) == 1500
    
    def test_bytes_to_samples(self) -> None:
        """Bytes to samples conversion."""
        assert bytes_to_samples(100) == 50  # 2 bytes per sample
        assert bytes_to_samples(100, sample_width_bytes=4) == 25
    
    def test_samples_to_bytes(self) -> None:
        """Samples to bytes conversion."""
        assert samples_to_bytes(50) == 100  # 2 bytes per sample
        assert samples_to_bytes(50, sample_width_bytes=4) == 200
    
    def test_duration_to_samples(self) -> None:
        """Duration to samples conversion."""
        assert duration_to_samples(1.0) == 16000  # 16kHz default
        assert duration_to_samples(1.0, sample_rate=8000) == 8000
    
    def test_samples_to_duration(self) -> None:
        """Samples to duration conversion."""
        assert samples_to_duration(16000) == 1.0  # 16kHz default
        assert samples_to_duration(8000, sample_rate=8000) == 1.0
