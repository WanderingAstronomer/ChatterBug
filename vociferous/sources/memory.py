"""MemorySource - wrap in-memory PCM data as a temporary WAV file."""

from __future__ import annotations

import tempfile
import wave
from pathlib import Path

from vociferous.sources.base import Source


class MemorySource(Source):
    """Wrap raw PCM bytes (mono) into a temporary WAV file for pipeline use.

    Intended for programmatic inputs where audio is already in memory.
    Writes a short-lived WAV file and returns its path.
    """

    def __init__(
        self,
        pcm: bytes,
        *,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width_bytes: int = 2,
        output_path: Path | None = None,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if channels <= 0:
            raise ValueError("channels must be positive")
        if sample_width_bytes not in (1, 2, 3, 4):
            raise ValueError("sample_width_bytes must be 1, 2, 3, or 4")
        self.pcm = pcm
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width_bytes = sample_width_bytes
        self.output_path = output_path

    def resolve_to_path(self, work_dir: Path | None = None) -> Path:
        target_dir = work_dir or Path(tempfile.mkdtemp(prefix="vociferous_mem_"))
        target_dir.mkdir(parents=True, exist_ok=True)
        target = self.output_path or target_dir / "memory_audio.wav"

        bytes_per_frame = self.sample_width_bytes * self.channels
        if len(self.pcm) == 0 or len(self.pcm) % bytes_per_frame != 0:
            raise ValueError("PCM buffer is empty or not aligned to frame size")

        target.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(target), "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.sample_width_bytes)
            wf.setframerate(self.sample_rate)
            wf.writeframes(self.pcm)

        return target
