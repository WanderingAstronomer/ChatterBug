from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Event
import wave

from vociferous.audio.recorder import SoundDeviceRecorder
from vociferous.domain.exceptions import DependencyError


class RecorderComponent:
    """Interactive microphone recorder."""

    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_ms: int = 100,
        device_name: str | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_ms = chunk_ms
        self.device_name = device_name

    def default_output_path(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        recordings_dir = Path(__file__).resolve().parent.parent / "recordings"
        return recordings_dir / f"recording_{timestamp}.wav"

    def record_to_file(self, output_path: Path, stop_event: Event) -> Path:
        """Record microphone audio until stop_event is set."""
        try:
            recorder = SoundDeviceRecorder(device_name=self.device_name)
        except DependencyError:
            raise

        sample_width = recorder.sample_width_bytes

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(self.sample_rate)

            for chunk in recorder.stream_chunks(
                sample_rate=self.sample_rate,
                channels=self.channels,
                chunk_ms=self.chunk_ms,
                sample_width_bytes=sample_width,
                stop_event=stop_event,
            ):
                wf.writeframes(chunk)

        return output_path