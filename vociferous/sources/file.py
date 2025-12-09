"""FileSource - Streams audio chunks from a file.

Provides a simplified file-based audio source that decodes and streams
audio chunks for transcription.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from vociferous.audio.decoder import AudioDecoder, FfmpegDecoder, WavDecoder
from vociferous.audio.utilities import apply_noise_gate, trim_trailing_silence
from vociferous.domain.exceptions import ConfigurationError
from vociferous.domain.model import AudioChunk, AudioSource


class FileSource(AudioSource):
    """Streams normalized chunks from a decoded file.
    
    Example:
        >>> source = FileSource("audio.mp3")
        >>> for chunk in source.stream():
        ...     process(chunk)
    """

    def __init__(
        self,
        path: str | Path,
        *,
        decoder: AudioDecoder | None = None,
        chunk_ms: int = 30000,
        trim_tail_ms: int = 800,
        noise_gate_db: float | None = None,
    ) -> None:
        """Initialize file source.
        
        Args:
            path: Path to audio file
            decoder: Audio decoder to use (default: FfmpegDecoder)
            chunk_ms: Chunk size in milliseconds (default: 30000 = 30s)
            trim_tail_ms: Trailing silence to trim in ms (default: 800)
            noise_gate_db: Noise gate threshold in dB (default: None = disabled)
        """
        self.path = Path(path)
        self.decoder = decoder or FfmpegDecoder()
        self.chunk_ms = chunk_ms
        self.trim_tail_ms = trim_tail_ms
        self.noise_gate_db = noise_gate_db

    def stream(self) -> Iterator[AudioChunk]:
        """Decode and yield audio chunks.
        
        Yields:
            AudioChunk objects from the decoded file
            
        Raises:
            FileNotFoundError: If audio file doesn't exist
            ConfigurationError: If path is not a file
        """
        if not self.path.exists():
            raise FileNotFoundError(f"Audio file not found: {self.path}")
        if not self.path.is_file():
            raise ConfigurationError(f"Path is not a file: {self.path}")

        try:
            audio = self.decoder.decode(str(self.path))
        except (RuntimeError, FileNotFoundError) as exc:
            # Attempt WAV fallback if ffmpeg missing or decode failed
            if isinstance(self.decoder, FfmpegDecoder) and self.path.suffix.lower() == ".wav":
                wav_decoder = WavDecoder()
                audio = wav_decoder.decode(str(self.path))
            else:
                raise exc
                
        pcm = audio.samples
        
        # Optional noise gate
        if self.noise_gate_db is not None:
            import math
            gate_linear = 10 ** (self.noise_gate_db / 20.0)
            threshold = max(1, int(32768 * gate_linear))
            pcm = apply_noise_gate(pcm, threshold, audio.sample_width_bytes)
            
        # Optional trailing trim
        if self.trim_tail_ms > 0:
            bytes_per_second = (
                audio.sample_rate * audio.channels * audio.sample_width_bytes
            )
            tail_bytes = int(bytes_per_second * (self.trim_tail_ms / 1000))
            if tail_bytes > 0 and tail_bytes < len(pcm):
                pcm = trim_trailing_silence(pcm, threshold=64, sample_width_bytes=audio.sample_width_bytes)
                
        # Update audio with processed PCM
        audio = audio.__class__(
            samples=pcm,
            sample_rate=audio.sample_rate,
            channels=audio.channels,
            duration_s=len(pcm)
            / (audio.sample_rate * audio.channels * audio.sample_width_bytes),
            sample_width_bytes=audio.sample_width_bytes,
        )

        yield from self.decoder.to_chunks(audio, self.chunk_ms)
