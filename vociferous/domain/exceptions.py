"""Domain-specific exceptions for Vociferous.

This module defines custom exception types with rich error context,
providing better error categorization, helpful suggestions, and
formatted output for CLI display.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class VociferousError(Exception):
    """Base exception for all Vociferous errors with rich error context.

    Provides structured error information including:
    - Descriptive message
    - Contextual details (file paths, parameters, etc.)
    - Actionable suggestions for resolution
    - Optional root cause exception

    Usage:
        raise VociferousError(
            "Failed to decode audio file",
            cause=original_exception,
            context={"file": str(audio_path), "format": "mp3"},
            suggestions=["Check file format", "Verify file exists"],
        )
    """

    def __init__(
        self,
        message: str,
        *,
        cause: Exception | None = None,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause
        self.context = context or {}
        self.suggestions = suggestions or []

    def format_error(self) -> str:
        """Format error with full context for display.

        Returns a formatted string suitable for CLI or logging output.
        For Rich panel display, use format_rich() instead.
        """
        lines = [f"✗ Error: {self.message}"]

        if self.context:
            lines.append("\nDetails:")
            for key, value in self.context.items():
                lines.append(f"  • {key}: {value}")

        if self.suggestions:
            lines.append("\nPossible solutions:")
            for i, suggestion in enumerate(self.suggestions, 1):
                lines.append(f"  {i}. {suggestion}")

        if self.cause:
            lines.append(f"\nCaused by: {type(self.cause).__name__}: {self.cause}")

        return "\n".join(lines)

    def format_rich(self) -> Any:
        """Format error as a Rich Panel for CLI display.

        Returns a Rich Panel object. Requires the `rich` library.
        """
        try:
            from rich.panel import Panel
            from rich.text import Text

            output = Text()
            output.append("✗ Error: ", style="bold red")
            output.append(self.message)

            if self.context:
                output.append("\n\nDetails:\n", style="bold")
                for key, value in self.context.items():
                    output.append(f"  • {key}: {value}\n")

            if self.suggestions:
                output.append("\nPossible solutions:\n", style="bold yellow")
                for i, suggestion in enumerate(self.suggestions, 1):
                    output.append(f"  {i}. {suggestion}\n", style="yellow")

            if self.cause:
                output.append(
                    f"\nCaused by: {type(self.cause).__name__}: {self.cause}\n",
                    style="dim",
                )

            return Panel(output, border_style="red", title="[bold]Error[/bold]")

        except ImportError:
            # Fall back to plain text if Rich not available
            return self.format_error()


class EngineError(VociferousError):
    """Raised when an ASR engine encounters an error during initialization or inference."""

    pass


class AudioDecodeError(VociferousError):
    """Raised when audio decoding fails.

    Provides helpful context about the audio file and FFmpeg error,
    with actionable suggestions for resolution.
    """

    @classmethod
    def from_ffmpeg_error(
        cls,
        audio_path: Path,
        returncode: int,
        stderr: str,
    ) -> AudioDecodeError:
        """Create error from FFmpeg failure with helpful context.

        Args:
            audio_path: Path to the audio file that failed
            returncode: FFmpeg exit code
            stderr: FFmpeg stderr output

        Returns:
            AudioDecodeError with context and suggestions
        """
        suggestions: list[str] = []

        # Analyze FFmpeg error for specific guidance
        stderr_lower = stderr.lower() if stderr else ""

        if "invalid data found" in stderr_lower or "could not find codec" in stderr_lower:
            suggestions.extend([
                "File may be corrupted. Try playing it with VLC or another player.",
                f"Convert to a standard format: ffmpeg -i {audio_path} output.wav",
                "Supported formats: MP3, WAV, FLAC, M4A, OGG, OPUS",
            ])

        elif "permission denied" in stderr_lower:
            suggestions.extend([
                f"Check file permissions: ls -l {audio_path}",
                f"Try: chmod 644 {audio_path}",
            ])

        elif "no such file" in stderr_lower:
            suggestions.extend([
                f"File does not exist: {audio_path}",
                "Check the path and try again.",
            ])

        else:
            suggestions.append("Run with --verbose to see full FFmpeg output")

        return cls(
            f"Failed to decode audio file: {audio_path.name}",
            context={
                "file": str(audio_path),
                "ffmpeg_exit_code": returncode,
            },
            suggestions=suggestions,
        )


class ConfigurationError(VociferousError):
    """Raised when configuration validation fails."""

    @classmethod
    def invalid_profile(cls, profile_name: str, valid_profiles: list[str]) -> ConfigurationError:
        """Create error for invalid profile name."""
        return cls(
            f"Invalid profile: '{profile_name}'",
            context={"requested_profile": profile_name},
            suggestions=[
                f"Available profiles: {', '.join(valid_profiles)}",
                "Create a new profile with: vociferous config set-profile <name>",
            ],
        )


class DependencyError(VociferousError):
    """Raised when a required dependency is missing."""

    @classmethod
    def missing_ffmpeg(cls) -> DependencyError:
        """Create error for missing FFmpeg."""
        return cls(
            "FFmpeg is not installed or not in PATH",
            suggestions=[
                "Install FFmpeg: sudo apt install ffmpeg (Debian/Ubuntu)",
                "Or: brew install ffmpeg (macOS)",
                "Verify installation: ffmpeg -version",
            ],
        )

    @classmethod
    def missing_cuda(cls, required_for: str = "GPU inference") -> DependencyError:
        """Create error for missing CUDA."""
        return cls(
            f"CUDA is not available ({required_for} requires GPU)",
            suggestions=[
                "Install NVIDIA drivers: sudo apt install nvidia-driver-XXX",
                "Install CUDA toolkit: sudo apt install nvidia-cuda-toolkit",
                "Use --device cpu to run on CPU (slower)",
            ],
        )


class AudioProcessingError(VociferousError):
    """Raised when audio processing (decode, condense, VAD) fails."""

    pass


class VADError(AudioProcessingError):
    """Raised when VAD fails or detects no speech.

    Provides helpful suggestions for adjusting VAD parameters
    or checking audio quality.
    """

    @classmethod
    def no_speech_detected(
        cls,
        audio_path: Path,
        audio_duration_s: float,
        threshold: float,
    ) -> VADError:
        """Create error when VAD finds no speech.

        Args:
            audio_path: Path to the audio file
            audio_duration_s: Duration of the audio in seconds
            threshold: VAD threshold that was used

        Returns:
            VADError with context and suggestions
        """
        return cls(
            "No speech detected in audio file",
            context={
                "file": str(audio_path),
                "duration": f"{audio_duration_s:.1f}s",
                "vad_threshold": threshold,
            },
            suggestions=[
                "Audio may be silent or very quiet. Check recording levels.",
                "Background noise may be drowning out speech. Try noise reduction.",
                f"Lower VAD sensitivity: --vad-threshold {threshold * 0.7:.2f}",
                "Use --preprocess clean to apply noise reduction before VAD",
            ],
        )


class UnsplittableSegmentError(AudioProcessingError):
    """Raised when a single speech segment exceeds max chunk duration.

    This occurs when VAD produces a continuous speech segment longer than the
    engine's maximum input duration (e.g., >40s for Canary). The audio may need
    manual splitting or different VAD parameters.
    """

    def __init__(
        self,
        segment_start: float,
        segment_end: float,
        max_chunk_s: float,
    ) -> None:
        duration = segment_end - segment_start

        super().__init__(
            f"Single speech segment is too long ({duration:.1f}s exceeds {max_chunk_s:.1f}s limit)",
            context={
                "segment_duration": f"{duration:.1f}s",
                "max_allowed": f"{max_chunk_s:.1f}s",
                "segment_range": f"{segment_start:.1f}s - {segment_end:.1f}s",
            },
            suggestions=[
                "VAD failed to detect pauses. Try adjusting VAD parameters:",
                "  --min-silence-ms 300  (detect shorter pauses)",
                "  --vad-threshold 0.3   (lower sensitivity)",
                "Pre-split audio manually at known boundaries",
                "Use a different engine with longer context support",
            ],
        )


class TranscriptionError(VociferousError):
    """Raised when transcription fails."""

    @classmethod
    def engine_inference_failed(
        cls,
        engine_name: str,
        audio_path: Path,
        cause: Exception,
    ) -> TranscriptionError:
        """Create error for engine inference failure."""
        return cls(
            f"Engine '{engine_name}' failed to transcribe audio",
            cause=cause,
            context={
                "engine": engine_name,
                "file": str(audio_path),
            },
            suggestions=[
                "Check GPU memory: nvidia-smi",
                "Try a smaller model or lower batch size",
                "Restart the daemon: vociferous daemon restart",
            ],
        )


class RefinementError(VociferousError):
    """Raised when text refinement fails."""

    @classmethod
    def output_invalid(
        cls,
        original_length: int,
        refined_length: int,
        reason: str,
    ) -> RefinementError:
        """Create error for invalid refinement output."""
        return cls(
            f"Refinement produced invalid output: {reason}",
            context={
                "original_length": original_length,
                "refined_length": refined_length,
            },
            suggestions=[
                "Try with default refinement instructions",
                "Skip refinement: --no-refine",
            ],
        )

