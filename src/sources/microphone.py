"""MicrophoneSource - Streams audio chunks from microphone.

Provides real-time audio capture from a microphone device.
"""

from __future__ import annotations

from threading import Event
from typing import Iterator

from vociferous.audio.recorder import MicrophoneRecorder, SoundDeviceRecorder
from vociferous.audio.utilities import validate_pcm_chunk
from vociferous.domain.model import AudioChunk, AudioSource


class MicrophoneSource(AudioSource):
    """Streams live microphone audio via an injectable recorder.
    
    Example:
        >>> source = MicrophoneSource()
        >>> for chunk in source.stream():
        ...     process(chunk)
        ...     if should_stop:
        ...         source.stop()
    """

    def __init__(
        self,
        device_name: str | None = None,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_ms: int = 960,
        sample_width_bytes: int = 2,
        recorder: MicrophoneRecorder | None = None,
    ) -> None:
        """Initialize microphone source.
        
        Args:
            device_name: Name of audio device (default: system default)
            sample_rate: Sample rate in Hz (default: 16000)
            channels: Number of audio channels (default: 1 for mono)
            chunk_ms: Chunk size in milliseconds (default: 960)
            sample_width_bytes: Bytes per sample (default: 2 for PCM16)
            recorder: Custom recorder implementation (default: SoundDeviceRecorder)
        """
        self.device_name = device_name
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_ms = chunk_ms
        self.sample_width_bytes = sample_width_bytes
        self._recorder: MicrophoneRecorder = recorder or SoundDeviceRecorder(device_name)
        self._stop_event = Event()

    def stop(self) -> None:
        """Stop streaming audio from microphone."""
        self._stop_event.set()

    def stream(self) -> Iterator[AudioChunk]:
        """Yield live audio chunks from microphone.
        
        Yields:
            AudioChunk objects with PCM data and timing information
        """
        chunk_duration = self.chunk_ms / 1000
        start = 0.0
        
        for raw in self._recorder.stream_chunks(
            sample_rate=self.sample_rate,
            channels=self.channels,
            chunk_ms=self.chunk_ms,
            stop_event=self._stop_event,
            sample_width_bytes=self.sample_width_bytes,
        ):
            validate_pcm_chunk(
                raw,
                sample_rate=self.sample_rate,
                channels=self.channels,
                chunk_ms=self.chunk_ms,
                sample_width_bytes=self.sample_width_bytes,
            )
            end = start + chunk_duration
            yield AudioChunk(
                samples=raw,
                sample_rate=self.sample_rate,
                channels=self.channels,
                start_s=start,
                end_s=end,
            )
            start = end
            if self._stop_event.is_set():
                break
