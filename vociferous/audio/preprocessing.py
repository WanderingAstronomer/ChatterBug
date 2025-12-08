"""Audio preprocessing module for speech boundary detection and silence analysis.

This module provides VAD-based analysis to detect:
1. First and last speech boundaries
2. Silence gaps for intelligent segmentation
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from vociferous.domain.model import SpeechMap, PreprocessingConfig


class AudioPreProcessor:
    """Analyzes audio to detect speech boundaries and silence gaps.
    
    Uses energy-based VAD to identify speech regions and natural pause points
    for intelligent audio segmentation.
    """
    
    def __init__(self, config: PreprocessingConfig) -> None:
        """Initialize preprocessor with configuration.
        
        Args:
            config: Preprocessing configuration with VAD thresholds
        """
        self.config = config
    
    def analyze_speech_boundaries(self, audio_path: Path) -> SpeechMap:
        """Analyze audio to detect speech boundaries and silence gaps.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            SpeechMap with:
              - first_speech_ms: timestamp of first speech
              - last_speech_ms: timestamp of last speech  
              - silence_gaps: List[(start_ms, end_ms, duration_ms)] for gaps ≥ gap_threshold_ms
        """
        from vociferous.domain.model import SpeechMap
        from vociferous.audio.decoder import FfmpegDecoder
        
        # Decode audio to PCM16
        decoder = FfmpegDecoder()
        decoded = decoder.decode(str(audio_path))
        
        # Convert bytes to numpy array for analysis
        audio_np = np.frombuffer(decoded.samples, dtype=np.int16)
        sample_rate = decoded.sample_rate
        
        # Calculate energy-based speech detection
        # Window size for energy calculation (50ms frames)
        frame_size = int(sample_rate * 0.05)
        hop_size = int(sample_rate * 0.01)  # 10ms hop
        
        # Calculate energy threshold from dB
        energy_threshold_linear = 10 ** (self.config.energy_threshold_db / 20.0)
        threshold = max(1, int(32768 * energy_threshold_linear))
        
        # Detect speech frames
        speech_frames = []
        for i in range(0, len(audio_np) - frame_size, hop_size):
            frame = audio_np[i:i + frame_size]
            energy = np.abs(frame).mean()
            is_speech = energy > threshold
            timestamp_ms = int((i / sample_rate) * 1000)
            speech_frames.append((timestamp_ms, is_speech))
        
        if not speech_frames:
            # Empty audio
            return SpeechMap(
                first_speech_ms=0,
                last_speech_ms=0,
                silence_gaps=[]
            )
        
        # Find first and last speech
        first_speech_ms = 0
        last_speech_ms = int((len(audio_np) / sample_rate) * 1000)
        
        for timestamp_ms, is_speech in speech_frames:
            if is_speech:
                first_speech_ms = timestamp_ms
                break
        
        for timestamp_ms, is_speech in reversed(speech_frames):
            if is_speech:
                last_speech_ms = timestamp_ms
                break
        
        # Find silence gaps
        silence_gaps = []
        silence_start_ms = None
        min_silence_ms = self.config.min_silence_duration_ms
        
        for timestamp_ms, is_speech in speech_frames:
            # Only look for gaps within speech boundaries
            if timestamp_ms < first_speech_ms or timestamp_ms > last_speech_ms:
                continue
                
            if not is_speech and silence_start_ms is None:
                silence_start_ms = timestamp_ms
            elif is_speech and silence_start_ms is not None:
                duration_ms = timestamp_ms - silence_start_ms
                if duration_ms >= min_silence_ms:
                    silence_gaps.append((silence_start_ms, timestamp_ms, duration_ms))
                silence_start_ms = None
        
        # Filter gaps to only those >= gap_threshold_ms for splitting
        significant_gaps = [
            gap for gap in silence_gaps
            if gap[2] >= self.config.gap_threshold_ms
        ]
        
        return SpeechMap(
            first_speech_ms=first_speech_ms,
            last_speech_ms=last_speech_ms,
            silence_gaps=tuple(significant_gaps)
        )
    
    def analyze_pcm_speech_boundaries(
        self, 
        pcm_data: bytes, 
        sample_rate: int = 16000
    ) -> SpeechMap:
        """Analyze PCM audio data to detect speech boundaries.
        
        Args:
            pcm_data: Raw PCM16 audio bytes
            sample_rate: Sample rate of audio (default: 16000)
            
        Returns:
            SpeechMap with speech boundaries and silence gaps
        """
        from vociferous.domain.model import SpeechMap
        
        # Convert bytes to numpy array
        audio_np = np.frombuffer(pcm_data, dtype=np.int16)
        
        # Calculate energy-based speech detection
        frame_size = int(sample_rate * 0.05)  # 50ms frames
        hop_size = int(sample_rate * 0.01)  # 10ms hop
        
        # Calculate energy threshold from dB
        energy_threshold_linear = 10 ** (self.config.energy_threshold_db / 20.0)
        threshold = max(1, int(32768 * energy_threshold_linear))
        
        # Detect speech frames
        speech_frames = []
        for i in range(0, len(audio_np) - frame_size, hop_size):
            frame = audio_np[i:i + frame_size]
            energy = np.abs(frame).mean()
            is_speech = energy > threshold
            timestamp_ms = int((i / sample_rate) * 1000)
            speech_frames.append((timestamp_ms, is_speech))
        
        if not speech_frames:
            return SpeechMap(
                first_speech_ms=0,
                last_speech_ms=0,
                silence_gaps=[]
            )
        
        # Find first and last speech
        first_speech_ms = 0
        last_speech_ms = int((len(audio_np) / sample_rate) * 1000)
        
        for timestamp_ms, is_speech in speech_frames:
            if is_speech:
                first_speech_ms = timestamp_ms
                break
        
        for timestamp_ms, is_speech in reversed(speech_frames):
            if is_speech:
                last_speech_ms = timestamp_ms
                break
        
        # Find silence gaps
        silence_gaps = []
        silence_start_ms = None
        min_silence_ms = self.config.min_silence_duration_ms
        
        for timestamp_ms, is_speech in speech_frames:
            if timestamp_ms < first_speech_ms or timestamp_ms > last_speech_ms:
                continue
                
            if not is_speech and silence_start_ms is None:
                silence_start_ms = timestamp_ms
            elif is_speech and silence_start_ms is not None:
                duration_ms = timestamp_ms - silence_start_ms
                if duration_ms >= min_silence_ms:
                    silence_gaps.append((silence_start_ms, timestamp_ms, duration_ms))
                silence_start_ms = None
        
        # Filter to significant gaps
        significant_gaps = [
            gap for gap in silence_gaps
            if gap[2] >= self.config.gap_threshold_ms
        ]
        
        return SpeechMap(
            first_speech_ms=first_speech_ms,
            last_speech_ms=last_speech_ms,
            silence_gaps=tuple(significant_gaps)
        )
