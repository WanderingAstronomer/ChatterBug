"""Pure speech detection component using Silero VAD.

Returns timestamps only, never modifies audio. Wraps the internal VadWrapper
from vad.py to provide a cleaner API focused on speech detection.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from vociferous.domain.exceptions import DependencyError
from .vad import HAS_SILERO, VadWrapper

if TYPE_CHECKING:
    pass


class SileroVAD:
    """Pure speech detection component - returns timestamps only.
    
    This class provides a high-level interface for detecting speech segments
    in audio files. It returns timestamps of speech regions but never modifies
    the audio itself.
    
    Example:
        >>> vad = SileroVAD()
        >>> timestamps = vad.detect_speech("lecture.mp3")
        >>> for ts in timestamps:
        ...     print(f"Speech from {ts['start']:.2f}s to {ts['end']:.2f}s")
    """
    
    def __init__(self, sample_rate: int = 16000, device: str = "cpu"):
        """Initialize Silero VAD wrapper.
        
        Args:
            sample_rate: Sample rate for audio processing (default: 16000)
            device: Device for VAD model ('cpu' or 'cuda')
        """
        if not HAS_SILERO:
            raise DependencyError("silero-vad package required for SileroVAD")

        self.sample_rate = sample_rate
        self.device = device
        self._vad = VadWrapper(sample_rate=sample_rate, device=device)
    
    def detect_speech(
        self,
        audio_path: Path | str,
        *,
        threshold: float = 0.5,
        min_silence_ms: int = 500,
        min_speech_ms: int = 250,
        speech_pad_ms: int = 250,
        max_speech_duration_s: float = 40.0,
        save_json: bool = False,
        output_path: Path | None = None,
    ) -> list[dict[str, float]]:
        """Analyze audio and return speech timestamps.
        
        Args:
            audio_path: Path to audio file
            threshold: VAD threshold (0.0-1.0, higher = stricter)
            min_silence_ms: Minimum silence duration to end a speech segment
            min_speech_ms: Minimum speech duration to be considered speech
            speech_pad_ms: Padding applied to segment boundaries (ms)
            max_speech_duration_s: Maximum allowed speech span length (seconds)
            save_json: If True, writes timestamps to JSON cache file
            output_path: Optional explicit path for saved JSON
            
        Returns:
            List of dicts with 'start' and 'end' keys (values in seconds)
            
        Example:
            >>> timestamps = vad.detect_speech("audio.mp3")
            >>> timestamps
            [{'start': 0.5, 'end': 3.2}, {'start': 4.0, 'end': 7.5}]
        """
        from .decoder import FfmpegDecoder

        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be in [0.0, 1.0], got {threshold}")
        if min_silence_ms < 0:
            raise ValueError(f"min_silence_ms must be non-negative, got {min_silence_ms}")
        if min_speech_ms < 0:
            raise ValueError(f"min_speech_ms must be non-negative, got {min_speech_ms}")
        if speech_pad_ms < 0:
            raise ValueError(f"speech_pad_ms must be non-negative, got {speech_pad_ms}")
        if max_speech_duration_s <= 0:
            raise ValueError("max_speech_duration_s must be positive")

        audio_path = Path(audio_path)
        
        # Decode audio to PCM
        decoder = FfmpegDecoder()
        decoded = decoder.decode(str(audio_path))
        
        # Get speech spans from VAD wrapper
        spans = self._vad.speech_spans(
            decoded.samples,
            threshold=threshold,
            min_silence_ms=min_silence_ms,
            min_speech_ms=min_speech_ms,
            speech_pad_ms=speech_pad_ms,
        )

        timestamps = self._normalize_and_limit(
            spans,
            audio_duration_s=decoded.duration_s,
            speech_pad_ms=speech_pad_ms,
            max_speech_duration_s=max_speech_duration_s,
        )
        
        # Optionally save to JSON cache
        if save_json or output_path is not None:
            cache_path = (
                Path(output_path)
                if output_path is not None
                else audio_path.with_name(f"{audio_path.stem}_vad_timestamps.json")
            )
            with open(cache_path, 'w') as f:
                json.dump(timestamps, f, indent=2)
        
        return timestamps

    def _normalize_and_limit(
        self,
        spans: list[tuple[int, int]],
        *,
        audio_duration_s: float,
        speech_pad_ms: int,
        max_speech_duration_s: float,
    ) -> list[dict[str, float]]:
        """Convert sample spans to padded/merged seconds and enforce max duration.

        This mirrors faster-whisper style consolidation: pad, merge overlaps, then
        split any oversize spans to keep Canary-friendly ≤40s chunks.
        """

        if not spans:
            return []

        pad_s = speech_pad_ms / 1000.0
        timestamps: list[tuple[float, float]] = []
        for start_sample, end_sample in spans:
            start = max(0.0, (start_sample / self.sample_rate) - pad_s)
            end = min(audio_duration_s, (end_sample / self.sample_rate) + pad_s)
            if end > start:
                timestamps.append((start, end))

        if not timestamps:
            return []

        # Merge overlaps/adjacent spans after padding
        merged: list[tuple[float, float]] = []
        for start, end in sorted(timestamps, key=lambda t: t[0]):
            if not merged:
                merged.append((start, end))
                continue
            prev_start, prev_end = merged[-1]
            if start <= prev_end:
                merged[-1] = (prev_start, max(prev_end, end))
            else:
                merged.append((start, end))

        # Enforce max_speech_duration_s by splitting long spans
        limited: list[dict[str, float]] = []
        for start, end in merged:
            span_len = end - start
            if span_len <= max_speech_duration_s:
                limited.append({"start": start, "end": end})
                continue

            cursor = start
            while cursor < end:
                chunk_end = min(cursor + max_speech_duration_s, end)
                limited.append({"start": cursor, "end": chunk_end})
                cursor = chunk_end

        return limited
    
    @staticmethod
    def load_cached_timestamps(audio_path: Path | str) -> list[dict[str, float]] | None:
        """Load previously saved timestamps from JSON cache.
        
        Args:
            audio_path: Path to original audio file
            
        Returns:
            List of timestamp dicts if cache exists, None otherwise
        """
        audio_path = Path(audio_path)
        cache_path = audio_path.with_name(f"{audio_path.stem}_vad_timestamps.json")
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
