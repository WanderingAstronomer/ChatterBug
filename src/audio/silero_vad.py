"""Pure speech detection component using Silero VAD.

Returns timestamps only, never modifies audio. Wraps the internal VadWrapper
from vad.py to provide a cleaner API focused on speech detection.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from .vad import VadWrapper

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
        save_json: bool = False,
        output_path: Path | None = None,
    ) -> list[dict[str, float]]:
        """Analyze audio and return speech timestamps.
        
        Args:
            audio_path: Path to audio file
            threshold: VAD threshold (0.0-1.0, higher = stricter)
            min_silence_ms: Minimum silence duration to end a speech segment
            min_speech_ms: Minimum speech duration to be considered speech
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
        )
        
        # Convert sample indices to seconds
        timestamps = []
        for start_sample, end_sample in spans:
            timestamps.append({
                'start': start_sample / self.sample_rate,
                'end': end_sample / self.sample_rate,
            })
        
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
