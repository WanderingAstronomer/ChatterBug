"""Consolidated helper functions for audio processing.

This module provides utility functions used across audio components for
validation, chunking, and audio manipulation.
"""

from __future__ import annotations

import array
import subprocess
from pathlib import Path
from typing import Iterator

from vociferous.domain.exceptions import AudioDecodeError, ConfigurationError
from vociferous.domain.model import AudioChunk


def chunk_pcm_bytes(
    pcm: bytes,
    sample_rate: int,
    channels: int,
    chunk_ms: int,
    sample_width_bytes: int = 2,
) -> Iterator[AudioChunk]:
    """Split PCM bytes into time-based AudioChunks.
    
    Args:
        pcm: Raw PCM audio bytes
        sample_rate: Sample rate in Hz
        channels: Number of audio channels
        chunk_ms: Duration of each chunk in milliseconds
        sample_width_bytes: Bytes per sample (default: 2 for PCM16)
        
    Yields:
        AudioChunk objects with timing information
    """
    bytes_per_second = sample_rate * channels * sample_width_bytes
    bytes_per_chunk = int(bytes_per_second * (chunk_ms / 1000))
    
    if bytes_per_chunk <= 0:
        raise ConfigurationError("Invalid chunk size computed for audio")

    total = len(pcm)
    offset = 0
    start = 0.0
    
    while offset < total:
        end = min(offset + bytes_per_chunk, total)
        chunk_bytes = pcm[offset:end]
        if not chunk_bytes:
            break
        end_s = start + (len(chunk_bytes) / bytes_per_second)
        yield AudioChunk(
            samples=chunk_bytes,
            sample_rate=sample_rate,
            channels=channels,
            start_s=start,
            end_s=end_s,
        )
        offset += bytes_per_chunk
        start = end_s


def apply_noise_gate(
    pcm: bytes,
    threshold: int,
    sample_width_bytes: int = 2,
) -> bytes:
    """Zero samples whose absolute value is below threshold.
    
    Only supports int16 (2-byte) audio format.
    
    Args:
        pcm: Raw PCM audio bytes
        threshold: Amplitude threshold (samples below this are zeroed)
        sample_width_bytes: Bytes per sample (must be 2 for this function)
        
    Returns:
        PCM bytes with low-amplitude samples zeroed
    """
    if sample_width_bytes != 2:
        return pcm
    
    arr = array.array("h")
    arr.frombytes(pcm)
    for i, v in enumerate(arr):
        if -threshold < v < threshold:
            arr[i] = 0
    return arr.tobytes()


def trim_trailing_silence(
    pcm: bytes,
    threshold: int = 64,
    sample_width_bytes: int = 2,
) -> bytes:
    """Remove trailing samples below threshold.
    
    Only supports int16 (2-byte) audio format.
    
    Args:
        pcm: Raw PCM audio bytes
        threshold: Amplitude threshold for silence detection
        sample_width_bytes: Bytes per sample (must be 2 for this function)
        
    Returns:
        PCM bytes with trailing silence removed
    """
    if sample_width_bytes != 2:
        return pcm
    
    arr = array.array("h")
    arr.frombytes(pcm)
    last_idx = len(arr) - 1
    while last_idx >= 0 and -threshold < arr[last_idx] < threshold:
        last_idx -= 1
    if last_idx < len(arr) - 1:
        arr = arr[: last_idx + 1]
    return arr.tobytes()


def get_audio_duration(audio_path: Path) -> float:
    """Get audio file duration in seconds using ffprobe.
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Duration in seconds
        
    Raises:
        AudioDecodeError: If ffprobe fails or file is invalid
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        duration_str = result.stdout.strip()
        return float(duration_str)
    except subprocess.CalledProcessError as exc:
        raise AudioDecodeError(f"Failed to get duration for {audio_path}: {exc.stderr}") from exc
    except ValueError as exc:
        raise AudioDecodeError(f"Invalid duration output from ffprobe: {duration_str}") from exc
