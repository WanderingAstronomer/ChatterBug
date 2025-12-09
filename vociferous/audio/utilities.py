"""Consolidated helper functions for audio processing.

This module provides utility functions used across audio components for
validation, chunking, and audio manipulation.
"""

from __future__ import annotations

import array
from typing import Iterator

from vociferous.domain.exceptions import ConfigurationError
from vociferous.domain.model import AudioChunk


def validate_pcm_chunk(
    chunk: bytes,
    *,
    sample_rate: int,
    channels: int,
    chunk_ms: int,
    sample_width_bytes: int = 2,
) -> None:
    """Ensure captured audio chunk is non-empty and matches expected size.
    
    Args:
        chunk: PCM audio data
        sample_rate: Sample rate in Hz
        channels: Number of audio channels
        chunk_ms: Expected chunk duration in milliseconds
        sample_width_bytes: Bytes per sample (default: 2 for PCM16)
        
    Raises:
        ConfigurationError: If chunk is empty or has unexpected size
    """
    if not chunk:
        raise ConfigurationError("Empty audio chunk captured")

    expected_bytes = int(sample_rate * (chunk_ms / 1000) * channels * sample_width_bytes)
    if expected_bytes <= 0:
        raise ConfigurationError("Invalid expected size computed for audio chunk")

    if len(chunk) != expected_bytes:
        raise ConfigurationError(
            f"Unexpected chunk size {len(chunk)} bytes; expected {expected_bytes} "
            f"for {chunk_ms}ms at {sample_rate}Hz, {channels}ch"
        )


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


def ms_to_seconds(ms: int | float) -> float:
    """Convert milliseconds to seconds.
    
    Args:
        ms: Time in milliseconds
        
    Returns:
        Time in seconds
    """
    return ms / 1000.0


def seconds_to_ms(seconds: float) -> int:
    """Convert seconds to milliseconds.
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Time in milliseconds (rounded to integer)
    """
    return int(seconds * 1000)


def bytes_to_samples(num_bytes: int, sample_width_bytes: int = 2) -> int:
    """Convert byte count to sample count.
    
    Args:
        num_bytes: Number of bytes
        sample_width_bytes: Bytes per sample (default: 2 for PCM16)
        
    Returns:
        Number of samples
    """
    return num_bytes // sample_width_bytes


def samples_to_bytes(num_samples: int, sample_width_bytes: int = 2) -> int:
    """Convert sample count to byte count.
    
    Args:
        num_samples: Number of samples
        sample_width_bytes: Bytes per sample (default: 2 for PCM16)
        
    Returns:
        Number of bytes
    """
    return num_samples * sample_width_bytes


def duration_to_samples(duration_s: float, sample_rate: int = 16000) -> int:
    """Convert duration in seconds to sample count.
    
    Args:
        duration_s: Duration in seconds
        sample_rate: Sample rate in Hz (default: 16000)
        
    Returns:
        Number of samples
    """
    return int(duration_s * sample_rate)


def samples_to_duration(num_samples: int, sample_rate: int = 16000) -> float:
    """Convert sample count to duration in seconds.
    
    Args:
        num_samples: Number of samples
        sample_rate: Sample rate in Hz (default: 16000)
        
    Returns:
        Duration in seconds
    """
    return num_samples / sample_rate
