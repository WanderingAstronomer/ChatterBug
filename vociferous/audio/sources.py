from __future__ import annotations

from pathlib import Path
from typing import Iterable
from threading import Event

from vociferous.domain.model import AudioChunk, AudioSource, PreprocessingConfig
from vociferous.domain.exceptions import ConfigurationError
from .decoder import AudioDecoder, FfmpegDecoder, WavDecoder
from .recorder import MicrophoneRecorder, SoundDeviceRecorder
from .validation import validate_pcm_chunk


class FileSource(AudioSource):
    """Streams normalized chunks from a decoded file."""

    def __init__(
        self,
        path: str | Path,
        *,
        decoder: AudioDecoder | None = None,
        chunk_ms: int = 30000,
        trim_tail_ms: int = 800,
        noise_gate_db: float | None = None,
    ) -> None:
        self.path = Path(path)
        self.decoder = decoder or FfmpegDecoder()
        self.chunk_ms = chunk_ms
        self.trim_tail_ms = trim_tail_ms
        self.noise_gate_db = noise_gate_db

    def stream(self) -> Iterable[AudioChunk]:
        if not self.path.exists():
            raise FileNotFoundError(f"Audio file not found: {self.path}")
        if not self.path.is_file():
            raise ConfigurationError(f"Path is not a file: {self.path}")

        try:
            audio = self.decoder.decode(str(self.path))
        except (RuntimeError, FileNotFoundError) as exc:
            # Attempt WAV fallback if ffmpeg missing or decode failed.
            if isinstance(self.decoder, FfmpegDecoder) and self.path.suffix.lower() == ".wav":
                wav_decoder = WavDecoder()
                audio = wav_decoder.decode(str(self.path))
            else:
                raise exc
        pcm = audio.samples
        # Optional noise gate
        if self.noise_gate_db is not None:
            # Convert dBFS to int16 threshold (max 32768)
            import math

            gate_linear = 10 ** (self.noise_gate_db / 20.0)
            threshold = max(1, int(32768 * gate_linear))
            from .decoder import _apply_noise_gate

            pcm = _apply_noise_gate(pcm, audio.sample_width_bytes, threshold)
        # Optional trailing trim
        if self.trim_tail_ms > 0:
            bytes_per_second = (
                audio.sample_rate * audio.channels * audio.sample_width_bytes
            )
            tail_bytes = int(bytes_per_second * (self.trim_tail_ms / 1000))
            if tail_bytes > 0 and tail_bytes < len(pcm):
                from .decoder import _trim_trailing_silence

                pcm = _trim_trailing_silence(pcm, audio.sample_width_bytes, threshold=64)
        audio = audio.__class__(
            samples=pcm,
            sample_rate=audio.sample_rate,
            channels=audio.channels,
            duration_s=len(pcm)
            / (audio.sample_rate * audio.channels * audio.sample_width_bytes),
            sample_width_bytes=audio.sample_width_bytes,
        )

        yield from self.decoder.to_chunks(audio, self.chunk_ms)


class MicrophoneSource(AudioSource):
    """Streams live microphone audio via an injectable recorder."""

    def __init__(
        self,
        device_name: str | None = None,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_ms: int = 960,
        sample_width_bytes: int = 2,
        recorder: MicrophoneRecorder | None = None,
    ) -> None:
        self.device_name = device_name
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_ms = chunk_ms
        self.sample_width_bytes = sample_width_bytes
        self._recorder: MicrophoneRecorder = recorder or SoundDeviceRecorder(device_name)
        self._stop_event = Event()

    def stop(self) -> None:
        self._stop_event.set()

    def stream(self) -> Iterable[AudioChunk]:
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


class PreprocessedFileSource(AudioSource):
    """Streams audio from a file with intelligent preprocessing.
    
    Applies VAD-based boundary detection and silence gap analysis to:
    1. Trim leading/trailing silence with safety margins
    2. Split at significant silence gaps (≥5s by default)
    3. Preserve natural pauses (<5s) for semantic completeness
    
    All processing happens in-memory using FFmpeg pipes.
    """
    
    def __init__(
        self,
        path: str | Path,
        *,
        config: PreprocessingConfig | None = None,
        chunk_ms: int = 30000,
    ) -> None:
        """Initialize preprocessed file source.
        
        Args:
            path: Path to audio file
            config: Preprocessing configuration (uses defaults if None)
            chunk_ms: Chunk size for streaming (default: 30000ms = 30s)
        """
        self.path = Path(path)
        self.config = config or PreprocessingConfig()
        self.chunk_ms = chunk_ms
    
    def stream(self) -> Iterable[AudioChunk]:
        """Stream preprocessed audio chunks.
        
        Performs the full preprocessing pipeline:
        1. VAD analysis to detect speech boundaries and gaps
        2. FFmpeg-based trimming and splitting
        3. In-memory streaming of resulting segments
        
        Yields:
            AudioChunk objects from preprocessed segments
        """
        from .preprocessing import AudioPreProcessor
        from .ffmpeg_editor import InMemoryFFmpegEditor
        from .memory_source import InMemoryAudioSource
        
        if not self.path.exists():
            raise FileNotFoundError(f"Audio file not found: {self.path}")
        if not self.path.is_file():
            raise ConfigurationError(f"Path is not a file: {self.path}")
        
        # Phase 1: Analyze speech boundaries
        preprocessor = AudioPreProcessor(self.config)
        speech_map = preprocessor.analyze_speech_boundaries(self.path)
        
        # Phase 2: Trim and split using FFmpeg
        editor = InMemoryFFmpegEditor()
        
        if self.config.split_on_gaps:
            # Split at significant gaps
            pcm_segments = editor.trim_and_split_in_memory(
                self.path,
                speech_map,
                head_margin_ms=self.config.head_margin_ms if self.config.trim_head else 0,
                tail_margin_ms=self.config.tail_margin_ms if self.config.trim_tail else 0,
            )
        else:
            # Just trim, don't split
            trimmed = editor.trim_only(
                self.path,
                speech_map,
                head_margin_ms=self.config.head_margin_ms if self.config.trim_head else 0,
                tail_margin_ms=self.config.tail_margin_ms if self.config.trim_tail else 0,
            )
            pcm_segments = [trimmed] if trimmed else []
        
        # Phase 3: Stream from memory
        memory_source = InMemoryAudioSource(
            pcm_segments=pcm_segments,
            sample_rate=16000,
            channels=1,
            chunk_ms=self.chunk_ms,
        )
        
        yield from memory_source.stream()

