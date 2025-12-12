"""Audio file validation and metadata extraction.

This module provides upfront validation of audio files before transcription,
enabling GUI users to see file information and errors immediately instead
of waiting until the transcription process fails.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from vociferous.domain.exceptions import AudioDecodeError

__all__ = [
    "AudioFileInfo",
    "validate_audio_file",
    "is_supported_format",
    "SUPPORTED_EXTENSIONS",
]


# Supported audio file extensions (case-insensitive)
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    ".mp3",
    ".wav",
    ".flac",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wma",
    ".aiff",
    ".ape",
    ".wv",
    ".webm",
})


@dataclass
class AudioFileInfo:
    """Metadata about an audio file.
    
    Contains all relevant metadata extracted via ffprobe, providing
    information for display in GUI and validation before transcription.
    
    Attributes:
        path: Absolute path to the audio file
        duration_s: Duration in seconds
        sample_rate: Sample rate in Hz (e.g., 16000, 44100)
        channels: Number of audio channels (1=mono, 2=stereo)
        codec: Audio codec name (e.g., 'mp3', 'pcm_s16le', 'flac')
        bitrate_kbps: Bitrate in kbps, if available
        format_name: Container format (e.g., 'mp3', 'wav', 'flac')
        file_size_mb: File size in megabytes
    
    Example:
        >>> info = validate_audio_file(Path("audio.mp3"))
        >>> print(f"Duration: {info.duration_s:.1f}s")
        Duration: 180.5s
    """
    
    path: Path
    duration_s: float
    sample_rate: int
    channels: int
    codec: str
    bitrate_kbps: int | None
    format_name: str
    file_size_mb: float
    
    def __str__(self) -> str:
        """Human-readable file info for display."""
        bitrate_str = f"{self.bitrate_kbps} kbps" if self.bitrate_kbps else "N/A"
        channel_str = "Mono" if self.channels == 1 else f"{self.channels} channels"
        
        return (
            f"{self.path.name}\n"
            f"  Duration: {self._format_duration(self.duration_s)}\n"
            f"  Format: {self.format_name.upper()}\n"
            f"  Codec: {self.codec}\n"
            f"  Sample Rate: {self.sample_rate:,} Hz\n"
            f"  Channels: {channel_str}\n"
            f"  Bitrate: {bitrate_str}\n"
            f"  Size: {self.file_size_mb:.2f} MB"
        )
    
    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format duration as human-readable string."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        if minutes < 60:
            return f"{minutes}m {remaining_seconds:.0f}s"
        hours = minutes // 60
        remaining_minutes = minutes % 60
        return f"{hours}h {remaining_minutes}m {remaining_seconds:.0f}s"
    
    def to_dict(self) -> dict[str, str | int | float | None]:
        """Serialize to dictionary for GUI consumption.
        
        Returns:
            Dictionary with all file info fields
        """
        return {
            "path": str(self.path),
            "filename": self.path.name,
            "duration_s": self.duration_s,
            "duration_formatted": self._format_duration(self.duration_s),
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "codec": self.codec,
            "bitrate_kbps": self.bitrate_kbps,
            "format_name": self.format_name,
            "file_size_mb": self.file_size_mb,
        }


def validate_audio_file(path: Path) -> AudioFileInfo:
    """Validate audio file and extract metadata.
    
    Performs comprehensive validation including:
    - File existence and readability
    - Valid audio format detection via ffprobe
    - Metadata extraction (duration, sample rate, codec, etc.)
    
    This should be called before starting transcription to provide
    immediate feedback to users about invalid files.
    
    Args:
        path: Path to audio file
    
    Returns:
        AudioFileInfo with complete metadata
    
    Raises:
        AudioDecodeError: If file doesn't exist, isn't audio, or is invalid
    
    Example:
        >>> info = validate_audio_file(Path("audio.mp3"))
        >>> print(f"Duration: {info.duration_s:.1f}s")
        Duration: 180.5s
    """
    # Resolve to absolute path
    path = path.resolve()
    
    # Check file exists
    if not path.exists():
        raise AudioDecodeError(
            f"Audio file not found: {path.name}",
            context={"file": str(path)},
            suggestions=[
                "Check the file path is correct",
                "Ensure the file hasn't been moved or deleted",
            ],
        )
    
    # Check path is a file, not a directory
    if not path.is_file():
        raise AudioDecodeError(
            f"Path is not a file: {path.name}",
            context={"file": str(path)},
            suggestions=["Ensure the path points to a file, not a directory"],
        )
    
    # Check file is not empty
    file_size = path.stat().st_size
    if file_size == 0:
        raise AudioDecodeError(
            f"Audio file is empty: {path.name}",
            context={"file": str(path), "size_bytes": 0},
            suggestions=["File may be corrupted or incomplete"],
        )
    
    # Use ffprobe to get metadata
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,  # Timeout for very large/slow files
            check=False,  # Don't raise on non-zero exit
        )
    except FileNotFoundError:
        raise AudioDecodeError(
            "ffprobe not found (ffmpeg not installed)",
            suggestions=[
                "Install ffmpeg: sudo apt install ffmpeg (Linux)",
                "Install ffmpeg: brew install ffmpeg (macOS)",
                "Download from https://ffmpeg.org/download.html (Windows)",
            ],
        )
    except subprocess.TimeoutExpired:
        raise AudioDecodeError(
            f"Timeout reading audio file: {path.name}",
            context={"file": str(path), "timeout_seconds": 30},
            suggestions=[
                "File may be very large or on a slow drive",
                "Try with a smaller file to test",
            ],
        )
    
    if result.returncode != 0:
        stderr = result.stderr or "Unknown error"
        raise AudioDecodeError(
            f"Failed to read audio file: {path.name}",
            context={"file": str(path), "ffprobe_exit_code": result.returncode},
            suggestions=[
                "File may be corrupted - try playing it with VLC",
                "File may not be a valid audio format",
                "Run: ffprobe -v error <file> to see detailed error",
            ],
        )
    
    # Parse JSON output
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AudioDecodeError(
            f"Failed to parse audio metadata: {path.name}",
            context={"file": str(path), "parse_error": str(e)},
            suggestions=["File may be corrupted or in an unusual format"],
        ) from e
    
    # Find audio stream
    audio_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "audio":
            audio_stream = stream
            break
    
    if not audio_stream:
        raise AudioDecodeError(
            f"No audio stream found in file: {path.name}",
            context={"file": str(path)},
            suggestions=[
                "File may be video-only",
                "File may be corrupted",
                "Try a different file",
            ],
        )
    
    # Extract metadata
    format_info = data.get("format", {})
    
    try:
        # Duration can be in format or stream
        duration_str = format_info.get("duration") or audio_stream.get("duration")
        duration = float(duration_str) if duration_str else 0.0
        
        sample_rate_str = audio_stream.get("sample_rate", "0")
        sample_rate = int(sample_rate_str)
        
        channels = int(audio_stream.get("channels", 0))
        
        codec = audio_stream.get("codec_name", "unknown")
        
        bitrate_str = format_info.get("bit_rate") or audio_stream.get("bit_rate")
        bitrate_kbps = int(int(bitrate_str) / 1000) if bitrate_str else None
        
        # Get format name (first one if multiple)
        format_name = format_info.get("format_name", "unknown")
        if "," in format_name:
            format_name = format_name.split(",")[0]
        
        file_size_mb = file_size / (1024 * 1024)
        
    except (ValueError, KeyError, TypeError) as e:
        raise AudioDecodeError(
            f"Invalid audio metadata: {path.name}",
            context={"file": str(path), "error": str(e)},
            suggestions=["File may be corrupted or in an unusual format"],
        ) from e
    
    # Validate basic requirements
    if duration <= 0:
        raise AudioDecodeError(
            f"Audio file has zero or negative duration: {path.name}",
            context={"file": str(path), "duration": duration},
            suggestions=["File may be empty or corrupted"],
        )
    
    if sample_rate == 0:
        raise AudioDecodeError(
            f"Invalid sample rate: {path.name}",
            context={"file": str(path), "sample_rate": sample_rate},
            suggestions=["File may be corrupted"],
        )
    
    if channels == 0:
        raise AudioDecodeError(
            f"Invalid channel count: {path.name}",
            context={"file": str(path), "channels": channels},
            suggestions=["File may be corrupted"],
        )
    
    return AudioFileInfo(
        path=path,
        duration_s=duration,
        sample_rate=sample_rate,
        channels=channels,
        codec=codec,
        bitrate_kbps=bitrate_kbps,
        format_name=format_name,
        file_size_mb=file_size_mb,
    )


def is_supported_format(path: Path) -> bool:
    """Check if file extension is a supported audio format.
    
    This is a quick check before attempting full validation with ffprobe.
    Useful for filtering files in a GUI file picker or batch operations.
    
    Args:
        path: Path to audio file
    
    Returns:
        True if extension is a known audio format
    
    Note:
        This is not definitive - files can have wrong extensions.
        Use validate_audio_file() for thorough validation.
    
    Example:
        >>> is_supported_format(Path("audio.mp3"))
        True
        >>> is_supported_format(Path("document.pdf"))
        False
    """
    return path.suffix.lower() in SUPPORTED_EXTENSIONS
