"""In-memory FFmpeg audio editor for surgical trimming and splitting.

Uses FFmpeg pipes to process audio entirely in RAM without temporary files.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vociferous.domain.model import SpeechMap


class InMemoryFFmpegEditor:
    """Uses FFmpeg pipes to process audio entirely in RAM.
    
    Zero temp files, operates at I/O speed with frame-accurate cuts.
    """
    
    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        """Initialize editor with FFmpeg path.
        
        Args:
            ffmpeg_path: Path to ffmpeg binary (default: "ffmpeg")
        """
        self.ffmpeg_path = ffmpeg_path
    
    def trim_and_split_in_memory(
        self,
        input_path: Path,
        speech_map: SpeechMap,
        head_margin_ms: int = 500,
        tail_margin_ms: int = 500,
    ) -> list[bytes]:
        """Trim and split audio using FFmpeg pipes.
        
        Args:
            input_path: Path to input audio file
            speech_map: Speech boundary and gap information
            head_margin_ms: Safety margin before first speech (default: 500ms)
            tail_margin_ms: Safety margin after last speech (default: 500ms)
            
        Returns:
            List of PCM16 audio bytes (one per segment), all in RAM
        """
        # Calculate trim boundaries with safety margins
        trim_start_ms = max(0, speech_map.first_speech_ms - head_margin_ms)
        trim_end_ms = speech_map.last_speech_ms + tail_margin_ms
        
        # If no significant gaps, return single trimmed segment
        if not speech_map.silence_gaps:
            segment = self._extract_segment(
                input_path,
                start_ms=trim_start_ms,
                end_ms=trim_end_ms
            )
            return [segment] if segment else []
        
        # Split at significant gaps
        segments = []
        current_start_ms = trim_start_ms
        
        for gap_start_ms, gap_end_ms, _ in speech_map.silence_gaps:
            # Extract segment before gap
            segment = self._extract_segment(
                input_path,
                start_ms=current_start_ms,
                end_ms=gap_start_ms
            )
            if segment:
                segments.append(segment)
            
            # Next segment starts after gap
            current_start_ms = gap_end_ms
        
        # Extract final segment after last gap
        final_segment = self._extract_segment(
            input_path,
            start_ms=current_start_ms,
            end_ms=trim_end_ms
        )
        if final_segment:
            segments.append(final_segment)
        
        return segments
    
    def _extract_segment(
        self,
        input_path: Path,
        start_ms: int,
        end_ms: int
    ) -> bytes | None:
        """Extract a segment from audio file using FFmpeg pipes.
        
        Args:
            input_path: Path to input audio file
            start_ms: Start time in milliseconds
            end_ms: End time in milliseconds
            
        Returns:
            PCM16 audio bytes, or None if extraction fails
        """
        # Convert ms to seconds for FFmpeg
        start_s = start_ms / 1000.0
        duration_s = (end_ms - start_ms) / 1000.0
        
        if duration_s <= 0:
            return None
        
        # FFmpeg command: extract segment and convert to PCM16
        cmd = [
            self.ffmpeg_path,
            "-nostdin",
            "-y",
            "-ss", str(start_s),
            "-t", str(duration_s),
            "-i", str(input_path),
            "-ar", "16000",
            "-ac", "1",
            "-f", "s16le",
            "-acodec", "pcm_s16le",
            "pipe:1"
        ]
        
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            
            if proc.returncode != 0:
                # Log error but don't crash - return None
                return None
            
            return proc.stdout
            
        except FileNotFoundError:
            raise FileNotFoundError(
                f"ffmpeg binary not found at {self.ffmpeg_path}; "
                "install ffmpeg or adjust PATH"
            )
        except Exception:
            return None
    
    def trim_only(
        self,
        input_path: Path,
        speech_map: SpeechMap,
        head_margin_ms: int = 500,
        tail_margin_ms: int = 500,
    ) -> bytes | None:
        """Trim audio without splitting, ignoring gaps.
        
        Args:
            input_path: Path to input audio file
            speech_map: Speech boundary information
            head_margin_ms: Safety margin before first speech
            tail_margin_ms: Safety margin after last speech
            
        Returns:
            Single PCM16 audio segment with head/tail trimmed
        """
        trim_start_ms = max(0, speech_map.first_speech_ms - head_margin_ms)
        trim_end_ms = speech_map.last_speech_ms + tail_margin_ms
        
        return self._extract_segment(
            input_path,
            start_ms=trim_start_ms,
            end_ms=trim_end_ms
        )
