from __future__ import annotations

from threading import Event
from typing import Iterable, Protocol

from chatterbug.domain.exceptions import DependencyError


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

        blocksize = int(sample_rate * (chunk_ms / 1000))
        q: "queue.SimpleQueue[bytes]" = queue.SimpleQueue()

        def callback(indata, frames, time_info, status) -> None:  # type: ignore[no-untyped-def]
            if status:  # underflow/overflow/etc.
                logging.warning("Microphone status: %s", status)
            q.put(bytes(indata))

        with self._sd.InputStream(  # type: ignore[attr-defined]
            samplerate=sample_rate,
            channels=channels,
            dtype=self.dtype,
            blocksize=blocksize,
            device=self.device_name,
            callback=callback,
        ):
            while True:
                if stop_event is not None and stop_event.is_set():
                    break
                try:
                    chunk = q.get(timeout=0.25)
                except queue.Empty:
                    continue
                yield chunk
