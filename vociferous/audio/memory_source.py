"""In-memory audio source for streaming preprocessed audio segments.

Provides a drop-in replacement for FileSource that streams from RAM
instead of reading from disk.
"""

from __future__ import annotations

from typing import Iterable

from vociferous.domain.model import AudioChunk, AudioSource


class InMemoryAudioSource(AudioSource):
    """Streams preprocessed audio segments from RAM.
    
    Drop-in replacement for FileSource that operates on in-memory
    PCM segments produced by the preprocessing pipeline.
    """
    
    def __init__(
        self,
        pcm_segments: list[bytes],
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_ms: int = 30000,
    ) -> None:
        """Initialize in-memory audio source.
        
        Args:
            pcm_segments: List of PCM16 audio segments
            sample_rate: Sample rate of audio (default: 16000)
            channels: Number of channels (default: 1 for mono)
            chunk_ms: Chunk size in milliseconds (default: 30000ms = 30s)
        """
        self.pcm_segments = pcm_segments
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_ms = chunk_ms
    
    def stream(self) -> Iterable[AudioChunk]:
        """Yield AudioChunks from preprocessed in-memory segments.
        
        Each segment is already speech-bounded and cleaned by preprocessing.
        Segments are further chunked to chunk_ms size for streaming.
        
        Yields:
            AudioChunk objects with PCM data and timing information
        """
        global_start_s = 0.0
        
        for segment_pcm in self.pcm_segments:
            if not segment_pcm:
                continue
            
            # Calculate segment parameters
            sample_width_bytes = 2  # PCM16 = 2 bytes per sample
            bytes_per_second = self.sample_rate * self.channels * sample_width_bytes
            segment_duration_s = len(segment_pcm) / bytes_per_second
            
            # Chunk the segment if it's larger than chunk_ms
            chunk_bytes = int((self.chunk_ms / 1000.0) * bytes_per_second)
            
            segment_start_s = global_start_s
            
            for i in range(0, len(segment_pcm), chunk_bytes):
                chunk_pcm = segment_pcm[i:i + chunk_bytes]
                chunk_duration_s = len(chunk_pcm) / bytes_per_second
                chunk_end_s = segment_start_s + chunk_duration_s
                
                yield AudioChunk(
                    samples=chunk_pcm,
                    sample_rate=self.sample_rate,
                    channels=self.channels,
                    start_s=segment_start_s,
                    end_s=chunk_end_s,
                )
                
                segment_start_s = chunk_end_s
            
            # Update global timestamp for next segment
            global_start_s += segment_duration_s
