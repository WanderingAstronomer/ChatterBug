from __future__ import annotations

from pathlib import Path
import wave

from vociferous.audio.decoder import FfmpegDecoder


class DecoderComponent:
    """Standardize audio to PCM mono 16kHz WAV."""

    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        self._decoder = FfmpegDecoder(ffmpeg_path=ffmpeg_path)

    def decode_to_wav(self, input_path: Path | str, output_path: Path | None = None) -> Path:
        """Decode arbitrary audio to PCM16 mono 16k WAV."""
        input_path = Path(input_path)
        if output_path is None:
            output_path = Path(f"{input_path.stem}_decoded.wav")

        decoded = self._decoder.decode(str(input_path))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(decoded.samples)

        return output_path
