"""Tests for audio file validation.

These tests verify that the validation module correctly:
- Validates audio files exist and are readable
- Extracts metadata via ffprobe
- Returns helpful errors for invalid files
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vociferous.audio.validation import (
    SUPPORTED_EXTENSIONS,
    AudioFileInfo,
    is_supported_format,
    validate_audio_file,
)
from vociferous.domain.exceptions import AudioDecodeError


# Use shared sample audio - WAV file has duration metadata
SAMPLE_AUDIO = Path(__file__).parent / "sample_audio" / "ASR_Test_preprocessed.wav"


class TestValidateAudioFile:
    """Tests for validate_audio_file()."""

    def test_validate_valid_audio_file(self) -> None:
        """Test validation of a valid audio file."""
        if not SAMPLE_AUDIO.exists():
            pytest.skip("Sample audio file not found")
        
        info = validate_audio_file(SAMPLE_AUDIO)
        
        assert isinstance(info, AudioFileInfo)
        assert info.path.name == SAMPLE_AUDIO.name
        assert info.duration_s > 0
        assert info.sample_rate > 0
        assert info.channels > 0
        assert info.codec
        assert info.format_name
        assert info.file_size_mb > 0

    def test_validate_nonexistent_file(self) -> None:
        """Test validation of nonexistent file raises error."""
        fake_path = Path("/nonexistent/directory/fake_audio.mp3")
        
        with pytest.raises(AudioDecodeError, match="not found"):
            validate_audio_file(fake_path)

    def test_validate_directory_not_file(self, tmp_path: Path) -> None:
        """Test validation of directory raises error."""
        directory = tmp_path / "not_a_file"
        directory.mkdir()
        
        with pytest.raises(AudioDecodeError, match="not a file"):
            validate_audio_file(directory)

    def test_validate_empty_file(self, tmp_path: Path) -> None:
        """Test validation of empty file raises error."""
        empty_file = tmp_path / "empty.wav"
        empty_file.touch()
        
        with pytest.raises(AudioDecodeError, match="empty"):
            validate_audio_file(empty_file)

    def test_validate_corrupted_file(self, tmp_path: Path) -> None:
        """Test validation of corrupted file raises error."""
        corrupted = tmp_path / "corrupted.mp3"
        corrupted.write_bytes(b"This is not audio data at all")
        
        with pytest.raises(AudioDecodeError):
            validate_audio_file(corrupted)

    def test_validate_text_file_with_audio_extension(self, tmp_path: Path) -> None:
        """Test that text files with audio extensions are rejected."""
        fake_audio = tmp_path / "fake.wav"
        fake_audio.write_text("This is a text file pretending to be audio")
        
        with pytest.raises(AudioDecodeError):
            validate_audio_file(fake_audio)

    def test_validation_error_contains_suggestions(self) -> None:
        """Test validation errors have helpful suggestions."""
        fake_path = Path("/nonexistent/audio.mp3")
        
        with pytest.raises(AudioDecodeError) as exc_info:
            validate_audio_file(fake_path)
        
        error = exc_info.value
        assert len(error.suggestions) > 0
        # Should mention checking the path
        assert any("path" in s.lower() for s in error.suggestions)

    def test_validation_error_contains_context(self) -> None:
        """Test validation errors include file context."""
        fake_path = Path("/nonexistent/audio.mp3")
        
        with pytest.raises(AudioDecodeError) as exc_info:
            validate_audio_file(fake_path)
        
        error = exc_info.value
        assert "file" in error.context
        assert "audio.mp3" in error.context["file"]


class TestAudioFileInfo:
    """Tests for AudioFileInfo dataclass."""

    def test_audio_file_info_str(self) -> None:
        """Test AudioFileInfo string representation."""
        if not SAMPLE_AUDIO.exists():
            pytest.skip("Sample audio file not found")
        
        info = validate_audio_file(SAMPLE_AUDIO)
        info_str = str(info)
        
        assert SAMPLE_AUDIO.name in info_str
        assert "Duration:" in info_str
        assert "Format:" in info_str
        assert "Sample Rate:" in info_str
        assert "Channels:" in info_str
        assert "Size:" in info_str

    def test_audio_file_info_to_dict(self) -> None:
        """Test AudioFileInfo serialization."""
        if not SAMPLE_AUDIO.exists():
            pytest.skip("Sample audio file not found")
        
        info = validate_audio_file(SAMPLE_AUDIO)
        data = info.to_dict()
        
        assert "path" in data
        assert "filename" in data
        assert "duration_s" in data
        assert "duration_formatted" in data
        assert "sample_rate" in data
        assert "channels" in data
        assert "codec" in data
        assert "format_name" in data
        assert "file_size_mb" in data
        
        # Check types
        assert isinstance(data["duration_s"], float)
        assert isinstance(data["sample_rate"], int)
        assert isinstance(data["channels"], int)

    def test_duration_formatting_seconds(self) -> None:
        """Test duration formatting for short durations."""
        # Create a mock AudioFileInfo to test formatting
        formatted = AudioFileInfo._format_duration(45.5)
        assert formatted == "45.5s"

    def test_duration_formatting_minutes(self) -> None:
        """Test duration formatting for minute-length durations."""
        formatted = AudioFileInfo._format_duration(125.0)
        assert "2m" in formatted
        assert "5s" in formatted

    def test_duration_formatting_hours(self) -> None:
        """Test duration formatting for hour-length durations."""
        formatted = AudioFileInfo._format_duration(3725.0)  # 1h 2m 5s
        assert "1h" in formatted
        assert "2m" in formatted


class TestIsSupportedFormat:
    """Tests for is_supported_format()."""

    def test_common_audio_formats_supported(self) -> None:
        """Test that common audio formats are recognized."""
        supported_files = [
            Path("audio.mp3"),
            Path("audio.wav"),
            Path("audio.flac"),
            Path("audio.m4a"),
            Path("audio.ogg"),
            Path("audio.opus"),
        ]
        
        for audio_file in supported_files:
            assert is_supported_format(audio_file), f"{audio_file} should be supported"

    def test_case_insensitive(self) -> None:
        """Test that format detection is case-insensitive."""
        assert is_supported_format(Path("audio.MP3"))
        assert is_supported_format(Path("audio.Wav"))
        assert is_supported_format(Path("audio.FLAC"))

    def test_non_audio_formats_rejected(self) -> None:
        """Test that non-audio formats are rejected."""
        non_audio_files = [
            Path("document.pdf"),
            Path("video.mp4"),
            Path("image.png"),
            Path("text.txt"),
            Path("archive.zip"),
        ]
        
        for non_audio_file in non_audio_files:
            assert not is_supported_format(non_audio_file), f"{non_audio_file} should not be supported"

    def test_supported_extensions_constant(self) -> None:
        """Test that SUPPORTED_EXTENSIONS is properly defined."""
        assert ".mp3" in SUPPORTED_EXTENSIONS
        assert ".wav" in SUPPORTED_EXTENSIONS
        assert ".flac" in SUPPORTED_EXTENSIONS
        assert ".ogg" in SUPPORTED_EXTENSIONS
        
        # Should be lowercase
        for ext in SUPPORTED_EXTENSIONS:
            assert ext.startswith(".")
            assert ext == ext.lower()


class TestValidationWithRealFiles:
    """Integration tests with real audio files."""

    def test_wav_file_validation(self) -> None:
        """Test WAV file validation."""
        if not SAMPLE_AUDIO.exists():
            pytest.skip("Sample audio file not found")
        
        info = validate_audio_file(SAMPLE_AUDIO)
        
        assert "wav" in info.format_name.lower()
        assert "pcm" in info.codec.lower()

    def test_sample_rate_is_reasonable(self) -> None:
        """Test that detected sample rate is reasonable."""
        if not SAMPLE_AUDIO.exists():
            pytest.skip("Sample audio file not found")
        
        info = validate_audio_file(SAMPLE_AUDIO)
        
        # Common sample rates: 8000, 16000, 22050, 44100, 48000, 96000
        assert 8000 <= info.sample_rate <= 192000

    def test_channel_count_is_reasonable(self) -> None:
        """Test that detected channel count is reasonable."""
        if not SAMPLE_AUDIO.exists():
            pytest.skip("Sample audio file not found")
        
        info = validate_audio_file(SAMPLE_AUDIO)
        
        # Most audio is mono, stereo, or up to 8 channels
        assert 1 <= info.channels <= 8


class TestErrorSerialization:
    """Test that validation errors can be serialized."""

    def test_validation_error_can_be_serialized(self) -> None:
        """Test that validation errors work with to_dict()."""
        fake_path = Path("/nonexistent/audio.mp3")
        
        try:
            validate_audio_file(fake_path)
            pytest.fail("Expected AudioDecodeError")
        except AudioDecodeError as e:
            data = e.to_dict()
            
            assert data["error_type"] == "AudioDecodeError"
            assert "not found" in data["message"]
            assert len(data["suggestions"]) > 0
