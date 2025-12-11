"""MicSource - microphone capture source that yields a recorded WAV file."""

from __future__ import annotations

from pathlib import Path
from threading import Event
import tempfile
import wave

from vociferous.audio.recorder import MicrophoneRecorder, SoundDeviceRecorder
from vociferous.domain.exceptions import DependencyError
from vociferous.sources.base import Source


class MicSource(Source):
    """Capture audio from a microphone into a temporary WAV file.

    MicSource records a short clip using the provided recorder (defaults to
    `SoundDeviceRecorder`) and returns the path to the captured WAV file.
    Recording is duration-bound to avoid interactive prompts in automated
    workflows.
    """

    def __init__(
        self,
        *,
        duration_seconds: float = 5.0,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_ms: int = 100,
        sample_width_bytes: int = 2,
        recorder: MicrophoneRecorder | None = None,
        output_path: Path | None = None,
    ) -> None:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if channels <= 0:
            raise ValueError("channels must be positive")

        self.duration_seconds = duration_seconds
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_ms = chunk_ms
        self.sample_width_bytes = sample_width_bytes
        self.recorder = recorder
        self.output_path = output_path

    def _resolve_recorder(self) -> MicrophoneRecorder:
        if self.recorder is not None:
            return self.recorder
        # Default to sounddevice-backed recorder (may raise DependencyError)
        return SoundDeviceRecorder()

    def resolve_to_path(self, work_dir: Path | None = None) -> Path:
        target_dir = work_dir or Path(tempfile.mkdtemp(prefix="vociferous_mic_"))
        target_dir.mkdir(parents=True, exist_ok=True)
        target = self.output_path or target_dir / "mic_capture.wav"

        recorder = self._resolve_recorder()
        # Prefer recorder-provided sample width if available
        sample_width_bytes = getattr(recorder, "sample_width_bytes", self.sample_width_bytes)

        bytes_per_second = self.sample_rate * self.channels * sample_width_bytes
        max_bytes = int(self.duration_seconds * bytes_per_second)
        bytes_written = 0

        stop_event = Event()
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            with wave.open(str(target), "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(sample_width_bytes)
                wf.setframerate(self.sample_rate)

                for chunk in recorder.stream_chunks(
                    sample_rate=self.sample_rate,
                    channels=self.channels,
                    chunk_ms=self.chunk_ms,
                    sample_width_bytes=sample_width_bytes,
                    stop_event=stop_event,
                ):
                    wf.writeframes(chunk)
                    bytes_written += len(chunk)
                    if bytes_written >= max_bytes:
                        stop_event.set()
                        break
        except DependencyError:
            # Bubble up to caller; callers can surface friendly messaging
            raise
        except Exception:
            if target.exists():
                target.unlink(missing_ok=True)
            raise

        if bytes_written == 0:
            # No audio captured; remove empty file
            target.unlink(missing_ok=True)
            raise RuntimeError("No audio captured from microphone")

        return target
