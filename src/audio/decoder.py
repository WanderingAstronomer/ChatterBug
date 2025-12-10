from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from vociferous.domain.model import AudioChunk
from vociferous.domain.exceptions import AudioDecodeError, ConfigurationError


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
        if isinstance(source, bytes):
            input_bytes = source
        else:
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
                raise FileNotFoundError("ffmpeg binary not found; install ffmpeg or adjust PATH") from exc
            if proc.returncode != 0:
                stderr.seek(0)
                err_text = stderr.read().decode(errors="ignore")
                raise AudioDecodeError(f"ffmpeg decode failed (code {proc.returncode}): {err_text}")
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
        return True

    def to_chunks(self, audio: DecodedAudio, chunk_ms: int) -> Iterable[AudioChunk]:
        yield from _chunk_pcm_bytes(audio, chunk_ms)


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
        return extension_or_mime.lower() in (".wav", "audio/wav", "wav")

    def to_chunks(self, audio: DecodedAudio, chunk_ms: int) -> Iterable[AudioChunk]:
        yield from _chunk_pcm_bytes(audio, chunk_ms)


def _chunk_pcm_bytes(audio: DecodedAudio, chunk_ms: int) -> Iterable[AudioChunk]:
    bytes_per_second = audio.sample_rate * audio.channels * audio.sample_width_bytes
    bytes_per_chunk = int(bytes_per_second * (chunk_ms / 1000))
    if bytes_per_chunk <= 0:
        raise ConfigurationError("Invalid chunk size computed for audio")

    total = len(audio.samples)
    offset = 0
    start = 0.0
    while offset < total:
        end = min(offset + bytes_per_chunk, total)
        chunk_bytes = audio.samples[offset:end]
        if not chunk_bytes:
            break
        end_s = start + (len(chunk_bytes) / bytes_per_second)
        yield AudioChunk(
            samples=chunk_bytes,
            sample_rate=audio.sample_rate,
            channels=audio.channels,
            start_s=start,
            end_s=end_s,
        )
        offset += bytes_per_chunk
        start = end_s


def _apply_noise_gate(pcm: bytes, sample_width_bytes: int, threshold: int) -> bytes:
    """Zero samples whose absolute value is below threshold (int16 only)."""
    if sample_width_bytes != 2:
        return pcm
    import array

    arr = array.array("h")
    arr.frombytes(pcm)
    for i, v in enumerate(arr):
        if -threshold < v < threshold:
            arr[i] = 0
    return arr.tobytes()


def _trim_trailing_silence(pcm: bytes, sample_width_bytes: int, threshold: int) -> bytes:
    """Remove trailing samples below threshold (int16 only)."""
    if sample_width_bytes != 2:
        return pcm
    import array

    arr = array.array("h")
    arr.frombytes(pcm)
    last_idx = len(arr) - 1
    while last_idx >= 0 and -threshold < arr[last_idx] < threshold:
        last_idx -= 1
    if last_idx < len(arr) - 1:
        arr = arr[: last_idx + 1]
    return arr.tobytes()
