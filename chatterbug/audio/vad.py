import numpy as np
from typing import Protocol

try:
    from silero_vad import load_silero_vad
    HAS_SILERO = True
except ImportError:  # Optional dependency; degrade gracefully without it.
    load_silero_vad = None
    HAS_SILERO = False


class VadService(Protocol):
    """Protocol for VAD (Voice Activity Detection) services."""

    def speech_spans(
        self,
        audio: bytes,
        *,
        threshold: float = 0.5,
        neg_threshold: float | None = None,
        min_silence_ms: int | None = None,
        min_speech_ms: int | None = None,
        speech_pad_ms: int | None = None,
    ) -> list[tuple[int, int]]:
        """Return speech spans as (start_sample, end_sample)."""
        ...


class NullVad:
    """No-op VAD that skips voice activity detection entirely."""

    def speech_spans(
        self,
        audio: bytes,
        *,
        threshold: float = 0.5,
        neg_threshold: float | None = None,
        min_silence_ms: int | None = None,
        min_speech_ms: int | None = None,
        speech_pad_ms: int | None = None,
    ) -> list[tuple[int, int]]:
        """Return empty spans to indicate no VAD filtering."""
        return []


class VadWrapper:
    """Silero VAD adapter with GPU support and safe fallback."""

    def __init__(self, sample_rate: int = 16000, device: str = "cpu"):
        self.sample_rate = sample_rate
        self.device = device
        self.model = None
        self.utils = None
        self._enabled = False
        self._torch = None

        if HAS_SILERO:
            self._torch = self._try_import_torch()
            if self._torch:
                try:
                    self.model, self.utils = load_silero_vad()
                    if device == "cuda" and self._torch.cuda.is_available():
                        self.model = self.model.to(device)
                    self._enabled = True
                except Exception:
                    self._enabled = False

    def is_speech(self, audio: bytes) -> bool:
        if not self._enabled or not self.model or not self._torch:
            return True  # Treat all audio as speech if VAD is unavailable

        audio_np = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        audio_tensor = self._torch.from_numpy(audio_np)
        if self.device == "cuda" and self._torch.cuda.is_available():
            audio_tensor = audio_tensor.to(self.device)

        get_speech_timestamps = self.utils[0]

        timestamps = get_speech_timestamps(
            audio_tensor,
            self.model,
            sampling_rate=self.sample_rate,
            threshold=0.5
        )
        return len(timestamps) > 0

    def trim(self, audio: bytes) -> bytes:
        """Return only the voiced parts of the audio."""
        if not self._enabled or not self.model or not self._torch:
            return audio

        audio_np = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        audio_tensor = self._torch.from_numpy(audio_np)
        if self.device == "cuda" and self._torch.cuda.is_available():
            audio_tensor = audio_tensor.to(self.device)
        get_speech_timestamps = self.utils[0]

        timestamps = get_speech_timestamps(
            audio_tensor,
            self.model,
            sampling_rate=self.sample_rate
        )

        if not timestamps:
            return b""

        voiced_audio = bytearray()
        for ts in timestamps:
            start = int(ts['start'])
            end = int(ts['end'])
            voiced_audio.extend(audio[start*2 : end*2])

        return bytes(voiced_audio)

    def speech_spans(
        self,
        audio: bytes,
        *,
        threshold: float = 0.5,
        neg_threshold: float | None = None,
        min_silence_ms: int | None = None,
        min_speech_ms: int | None = None,
        speech_pad_ms: int | None = None,
    ) -> list[tuple[int, int]]:
        """Return speech spans as (start_sample, end_sample). Empty if VAD unavailable."""
        if not self._enabled or not self.model or not self._torch:
            return []

        audio_np = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        audio_tensor = self._torch.from_numpy(audio_np)
        if self.device == "cuda" and self._torch.cuda.is_available():
            audio_tensor = audio_tensor.to(self.device)
        get_speech_timestamps = self.utils[0]

        vad_kwargs = {
            "sampling_rate": self.sample_rate,
            "threshold": threshold,
        }
        if neg_threshold is not None:
            vad_kwargs["neg_threshold"] = neg_threshold
        if min_silence_ms is not None:
            vad_kwargs["min_silence_duration_ms"] = min_silence_ms
        if min_speech_ms is not None:
            vad_kwargs["min_speech_duration_ms"] = min_speech_ms
        if speech_pad_ms is not None:
            vad_kwargs["speech_pad_ms"] = speech_pad_ms

        timestamps = get_speech_timestamps(
            audio_tensor,
            self.model,
            **vad_kwargs,
        )

        spans: list[tuple[int, int]] = []
        for ts in timestamps:
            start = int(ts["start"])
            end = int(ts["end"])
            if end > start:
                spans.append((start, end))
        return spans

    @staticmethod
    def _try_import_torch():
        try:
            import torch
        except ImportError:
            return None
        return torch
