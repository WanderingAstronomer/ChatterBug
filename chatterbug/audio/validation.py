from __future__ import annotations

from chatterbug.domain.exceptions import ConfigurationError


def validate_pcm_chunk(
    chunk: bytes,
    *,
    sample_rate: int,
    channels: int,
    chunk_ms: int,
    sample_width_bytes: int = 2,
) -> None:
    """Ensure captured audio chunk is non-empty and matches expected size."""
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
