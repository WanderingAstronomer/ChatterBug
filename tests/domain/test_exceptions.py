"""Tests for rich error system with context and suggestions."""

from __future__ import annotations

from pathlib import Path

from vociferous.domain.exceptions import (
    AudioDecodeError,
    ConfigurationError,
    DependencyError,
    RefinementError,
    TranscriptionError,
    UnsplittableSegmentError,
    VADError,
    VociferousError,
)


class TestVociferousError:
    """Tests for base VociferousError class."""

    def test_basic_initialization(self):
        """Error can be created with just a message."""
        error = VociferousError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.cause is None
        assert error.context == {}
        assert error.suggestions == []

    def test_full_initialization(self):
        """Error can be created with all optional fields."""
        cause = ValueError("original error")
        error = VociferousError(
            "Something went wrong",
            cause=cause,
            context={"file": "/path/to/file", "code": 42},
            suggestions=["Try this", "Or that"],
        )
        assert error.cause is cause
        assert error.context == {"file": "/path/to/file", "code": 42}
        assert error.suggestions == ["Try this", "Or that"]

    def test_format_error_basic(self):
        """format_error produces readable output for basic error."""
        error = VociferousError("File not found")
        formatted = error.format_error()
        assert "✗ Error: File not found" in formatted

    def test_format_error_with_context(self):
        """format_error includes context details."""
        error = VociferousError(
            "Decode failed",
            context={"file": "audio.mp3", "code": 1},
        )
        formatted = error.format_error()
        assert "audio.mp3" in formatted
        assert "Details:" in formatted

    def test_format_error_with_suggestions(self):
        """format_error includes suggestions."""
        error = VociferousError(
            "Decode failed",
            suggestions=["Install ffmpeg", "Check file format"],
        )
        formatted = error.format_error()
        assert "Possible solutions:" in formatted
        assert "Install ffmpeg" in formatted

    def test_format_error_with_cause(self):
        """format_error includes root cause."""
        cause = ValueError("bad value")
        error = VociferousError("Failed", cause=cause)
        formatted = error.format_error()
        assert "Caused by: ValueError: bad value" in formatted

    def test_format_rich_returns_panel(self):
        """format_rich returns a Rich Panel object."""
        error = VociferousError(
            "Test error",
            context={"key": "value"},
            suggestions=["Do something"],
        )
        panel = error.format_rich()
        # Should be a Panel object
        from rich.panel import Panel
        assert isinstance(panel, Panel)


class TestAudioDecodeError:
    """Tests for AudioDecodeError factory methods."""

    def test_from_ffmpeg_error_corrupt_file(self):
        """Creates helpful error for corrupt file."""
        error = AudioDecodeError.from_ffmpeg_error(
            Path("/path/to/audio.mp3"),
            returncode=1,
            stderr="Invalid data found when processing input",
        )
        assert "audio.mp3" in error.message
        assert error.context["ffmpeg_exit_code"] == 1
        assert any("corrupted" in s.lower() for s in error.suggestions)

    def test_from_ffmpeg_error_permission_denied(self):
        """Creates helpful error for permission issues."""
        error = AudioDecodeError.from_ffmpeg_error(
            Path("/path/to/audio.mp3"),
            returncode=1,
            stderr="Permission denied",
        )
        assert any("permission" in s.lower() for s in error.suggestions)

    def test_from_ffmpeg_error_file_not_found(self):
        """Creates helpful error for missing file."""
        error = AudioDecodeError.from_ffmpeg_error(
            Path("/path/to/missing.mp3"),
            returncode=1,
            stderr="No such file or directory",
        )
        assert any("does not exist" in s.lower() for s in error.suggestions)

    def test_from_ffmpeg_error_generic(self):
        """Creates generic suggestion for unknown errors."""
        error = AudioDecodeError.from_ffmpeg_error(
            Path("/path/to/audio.mp3"),
            returncode=1,
            stderr="Some unknown error",
        )
        assert any("verbose" in s.lower() for s in error.suggestions)


class TestVADError:
    """Tests for VADError factory methods."""

    def test_no_speech_detected(self):
        """Creates helpful error when no speech detected."""
        error = VADError.no_speech_detected(
            audio_path=Path("/path/to/silent.wav"),
            audio_duration_s=30.5,
            threshold=0.5,
        )
        assert "No speech detected" in error.message
        assert error.context["duration"] == "30.5s"
        assert error.context["vad_threshold"] == 0.5
        assert len(error.suggestions) > 0
        assert any("vad-threshold" in s.lower() for s in error.suggestions)


class TestUnsplittableSegmentError:
    """Tests for UnsplittableSegmentError."""

    def test_creates_with_context(self):
        """Creates error with segment details."""
        error = UnsplittableSegmentError(
            segment_start=10.0,
            segment_end=60.0,
            max_chunk_s=40.0,
        )
        assert "50.0s exceeds 40.0s" in error.message
        assert error.context["segment_duration"] == "50.0s"
        assert error.context["max_allowed"] == "40.0s"
        assert len(error.suggestions) > 0


class TestConfigurationError:
    """Tests for ConfigurationError factory methods."""

    def test_invalid_profile(self):
        """Creates helpful error for invalid profile."""
        error = ConfigurationError.invalid_profile(
            "nonexistent",
            ["default", "fast", "accurate"],
        )
        assert "nonexistent" in error.message
        assert any("default" in s for s in error.suggestions)


class TestDependencyError:
    """Tests for DependencyError factory methods."""

    def test_missing_ffmpeg(self):
        """Creates helpful error for missing ffmpeg."""
        error = DependencyError.missing_ffmpeg()
        assert "FFmpeg" in error.message
        assert any("install" in s.lower() for s in error.suggestions)

    def test_missing_cuda(self):
        """Creates helpful error for missing CUDA."""
        error = DependencyError.missing_cuda("GPU transcription")
        assert "CUDA" in error.message
        assert any("nvidia" in s.lower() for s in error.suggestions)


class TestTranscriptionError:
    """Tests for TranscriptionError factory methods."""

    def test_engine_inference_failed(self):
        """Creates helpful error for engine failure."""
        cause = RuntimeError("Out of memory")
        error = TranscriptionError.engine_inference_failed(
            engine_name="canary_qwen",
            audio_path=Path("/path/to/audio.wav"),
            cause=cause,
        )
        assert "canary_qwen" in error.message
        assert error.cause is cause
        assert any("gpu memory" in s.lower() for s in error.suggestions)


class TestRefinementError:
    """Tests for RefinementError factory methods."""

    def test_output_invalid(self):
        """Creates helpful error for invalid refinement output."""
        error = RefinementError.output_invalid(
            original_length=100,
            refined_length=500,
            reason="output too long",
        )
        assert "invalid output" in error.message.lower()
        assert error.context["original_length"] == 100
        assert any("--no-refine" in s for s in error.suggestions)
