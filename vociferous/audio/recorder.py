from __future__ import annotations

from collections.abc import Iterable
from threading import Event
from typing import Any, Protocol

from vociferous.domain.exceptions import ConfigurationError, DependencyError


class MicrophoneRecorder(Protocol):
    """Abstract microphone recorder that yields raw PCM chunks."""

    def stream_chunks(
        self,
        *,
        sample_rate: int,
        channels: int,
        chunk_ms: int,
        stop_event: Event | None = None,
        sample_width_bytes: int = 2,
    ) -> Iterable[bytes]:
        ...


class SoundDeviceRecorder:
    """sounddevice-backed recorder. Requires sounddevice/PortAudio at runtime."""

    def __init__(self, device_name: str | None = None, dtype: str = "int16") -> None:
        try:
            import sounddevice as sd  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise DependencyError("sounddevice is required for SoundDeviceRecorder") from exc
        self._sd = sd
        self.device_name = device_name
        self.dtype = dtype

    @property
    def sample_width_bytes(self) -> int:
        import numpy as np

        return int(np.dtype(self.dtype).itemsize)

    def stream_chunks(
        self,
        *,
        sample_rate: int,
        channels: int,
        chunk_ms: int,
        stop_event: Event | None = None,
        sample_width_bytes: int = 2,
    ) -> Iterable[bytes]:
        import logging
        import queue

        blocksize = max(1, int(sample_rate * (chunk_ms / 1000)))
        actual_sample_width = self.sample_width_bytes
        if sample_width_bytes != actual_sample_width:
            raise ConfigurationError(
                f"Requested {sample_width_bytes} bytes/sample but recorder "
                f"configured for {actual_sample_width}"
            )

        bytes_per_frame = actual_sample_width * channels
        q: queue.SimpleQueue[bytes] = queue.SimpleQueue()

        def callback(indata: Any, frames: Any, time_info: Any, status: Any) -> None:
            if status:  # underflow/overflow/etc.
                logging.warning("Microphone status: %s", status)
            q.put(bytes(indata))

        with self._sd.InputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype=self.dtype,
            blocksize=blocksize,
            device=self.device_name,
            callback=callback,
        ):
            while True:
                if stop_event is not None and stop_event.is_set():
                    while True:
                        try:
                            remaining = q.get_nowait()
                        except queue.Empty:
                            return
                        yield remaining
                try:
                    chunk = q.get(timeout=0.25)
                except queue.Empty:
                    continue
                if len(chunk) % bytes_per_frame != 0:
                    logging.warning(
                        "Unexpected recorder chunk size: %s bytes (frame size %s)",
                        len(chunk),
                        bytes_per_frame,
                    )
                yield chunk
