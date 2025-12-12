from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from vociferous.audio.utilities import chunk_pcm_bytes
from vociferous.domain.exceptions import AudioDecodeError, DependencyError
from vociferous.domain.model import AudioChunk


@dataclass(frozen=True)
class DecodedAudio:
    samples: bytes
    sample_rate: int
    channels: int
    duration_s: float
    sample_width_bytes: int = 2


class AudioDecoder(Protocol):
    def decode(self, source: str | bytes) -> DecodedAudio:
        ...

    def supports_format(self, extension_or_mime: str) -> bool:
        ...

    def to_chunks(self, audio: DecodedAudio, chunk_ms: int) -> Iterable[AudioChunk]:
        ...


class FfmpegDecoder:
    """ffmpeg-backed decoder that normalizes to 16kHz mono int16 PCM."""

    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        self.ffmpeg_path = ffmpeg_path
        self._ffmpeg_available: bool | None = None

    def decode(self, source: str | bytes) -> DecodedAudio:
        import subprocess
        import tempfile

        cmd = [
            self.ffmpeg_path,
            "-nostdin",
            "-y",
            "-i",
            "pipe:0",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-f",
            "s16le",
            "pipe:1",
        ]
        input_bytes: bytes
        source_path: Path | None = None
        if isinstance(source, bytes):
            input_bytes = source
        else:
            source_path = Path(source)
            with open(source, "rb") as f:
                input_bytes = f.read()

        with tempfile.TemporaryFile() as stderr:
            try:
                proc = subprocess.run(
                    cmd,
                    input=input_bytes,
                    stdout=subprocess.PIPE,
                    stderr=stderr,
                    check=False,
                )
            except FileNotFoundError as exc:
                raise DependencyError.missing_ffmpeg() from exc
            if proc.returncode != 0:
                stderr.seek(0)
                err_text = stderr.read().decode(errors="ignore")
                if source_path:
                    raise AudioDecodeError.from_ffmpeg_error(
                        source_path, proc.returncode, err_text
                    )
                else:
                    raise AudioDecodeError(
                        "Failed to decode audio from bytes",
                        context={"ffmpeg_exit_code": proc.returncode},
                        suggestions=["Ensure audio data is in a valid format"],
                    )
            pcm = proc.stdout

        sample_rate = 16000
        channels = 1
        sample_width_bytes = 2
        duration = len(pcm) / (sample_rate * channels * sample_width_bytes)
        return DecodedAudio(
            samples=pcm,
            sample_rate=sample_rate,
            channels=channels,
            duration_s=duration,
            sample_width_bytes=sample_width_bytes,
        )

    def supports_format(self, extension_or_mime: str) -> bool:
        if self._ffmpeg_available is None:
            self._ffmpeg_available = self._check_ffmpeg()
        return self._ffmpeg_available

    def to_chunks(self, audio: DecodedAudio, chunk_ms: int) -> Iterable[AudioChunk]:
        yield from chunk_pcm_bytes(
            audio.samples,
            audio.sample_rate,
            audio.channels,
            chunk_ms,
            audio.sample_width_bytes,
        )

    def _check_ffmpeg(self) -> bool:
        import os
        import shutil
        import subprocess

        # Check if it's already a full path
        if os.path.isfile(self.ffmpeg_path) and os.access(self.ffmpeg_path, os.X_OK):
            path = self.ffmpeg_path
        else:
            path = shutil.which(self.ffmpeg_path)
        
        if path is None:
            return False

        try:
            proc = subprocess.run(
                [path, "-version"],
                capture_output=True,
                check=False,
            )
        except OSError:
            return False

        return proc.returncode == 0


class WavDecoder:
    """Basic WAV decoder to ensure we can validate local captures without external deps."""

    def __init__(self, sample_width_bytes: int = 2) -> None:
        self.sample_width_bytes = sample_width_bytes

    def decode(self, source: str | bytes) -> DecodedAudio:
        import wave

        if isinstance(source, bytes):
            raise AudioDecodeError("Byte-buffer decode not supported for WAV decoder")

        with wave.open(source, "rb") as wf:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            width = wf.getsampwidth()
            frames = wf.readframes(wf.getnframes())
            duration = wf.getnframes() / float(sample_rate)

        return DecodedAudio(
            samples=frames,
            sample_rate=sample_rate,
            channels=channels,
            duration_s=duration,
            sample_width_bytes=width,
        )

    def supports_format(self, extension_or_mime: str) -> bool:
        normalized = extension_or_mime.strip().lower().lstrip(".")
        return normalized in ("wav", "audio/wav")

    def to_chunks(self, audio: DecodedAudio, chunk_ms: int) -> Iterable[AudioChunk]:
        yield from chunk_pcm_bytes(
            audio.samples,
            audio.sample_rate,
            audio.channels,
            chunk_ms,
            audio.sample_width_bytes,
        )
