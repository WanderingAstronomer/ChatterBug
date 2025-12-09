"""O(n) audio condensation with intelligent splitting for long files.

Uses FFmpeg concat demuxer for single-pass O(n) performance, with intelligent
splitting for files exceeding maximum duration limits.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence

from vociferous.domain.exceptions import AudioDecodeError

logger = logging.getLogger(__name__)


class AudioProcessingError(Exception):
    """Raised when audio processing fails."""
    pass


class FFmpegCondenser:
    """Single-pass O(n) audio condensation with intelligent splitting.
    
    Condenses audio by extracting only speech segments using FFmpeg's concat
    demuxer, achieving O(n) performance where n is the total audio duration.
    For files exceeding max_duration_minutes, intelligently splits at silence
    gaps to produce multiple output files.
    
    Example:
        >>> condenser = FFmpegCondenser()
        >>> timestamps = [{'start': 1.0, 'end': 5.0}, {'start': 7.0, 'end': 12.0}]
        >>> files = condenser.condense("lecture.mp3", timestamps)
        >>> files
        [PosixPath('lecture_condensed.wav')]
    """
    
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        """Initialize condenser.
        
        Args:
            ffmpeg_path: Path to FFmpeg binary (default: "ffmpeg")
        """
        self.ffmpeg_path = ffmpeg_path
    
    def condense(
        self,
        audio_path: Path | str,
        speech_timestamps: list[dict[str, float]],
        output_dir: Path | None = None,
        max_duration_minutes: int = 30,
        min_gap_for_split_s: float = 5.0,
        boundary_margin_s: float = 1.0,
    ) -> list[Path]:
        """Condense audio, splitting intelligently if over max_duration.
        
        Args:
            audio_path: Input audio file
            speech_timestamps: List of {'start': seconds, 'end': seconds} from SileroVAD
            output_dir: Directory for output (default: same as input)
            max_duration_minutes: Maximum duration per file (default: 30)
            min_gap_for_split_s: Minimum silence gap for safe split (default: 5.0)
            boundary_margin_s: Silence preserved at file edges (default: 1.0)
            
        Returns:
            List of output file paths (1 if short, N if split)
            
        Raises:
            AudioProcessingError: If no safe cut points found for long audio
        """
        audio_path = Path(audio_path)
        output_dir = output_dir or audio_path.parent
        output_dir = Path(output_dir)
        
        if not speech_timestamps:
            # No speech detected - return empty list
            logger.warning(f"No speech timestamps provided for {audio_path}")
            return []
        
        # Calculate total condensed duration
        total_duration_s = sum(ts['end'] - ts['start'] for ts in speech_timestamps)
        max_duration_s = max_duration_minutes * 60
        
        if total_duration_s <= max_duration_s:
            # Single file output
            output_path = output_dir / f"{audio_path.stem}_condensed.wav"
            self._condense_segments(
                audio_path,
                speech_timestamps,
                output_path,
                boundary_margin_s,
            )
            return [output_path]
        
        # Need to split - find safe cut points
        return self._condense_with_splitting(
            audio_path,
            speech_timestamps,
            output_dir,
            max_duration_s,
            min_gap_for_split_s,
            boundary_margin_s,
        )
    
    def _condense_segments(
        self,
        audio_path: Path,
        timestamps: list[dict[str, float]],
        output_path: Path,
        margin_s: float,
    ) -> None:
        """Condense audio segments into a single output file using FFmpeg concat demuxer."""
        if not timestamps:
            return
        
        # Create concat file list for FFmpeg
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as concat_file:
            concat_path = Path(concat_file.name)
            
            for i, ts in enumerate(timestamps):
                start = ts['start']
                end = ts['end']
                
                if end - start <= 0:
                    continue
                
                # Add margin at start/end of file
                if i == 0:
                    start = max(0, start - margin_s)
                if i == len(timestamps) - 1:
                    end = end + margin_s
                
                # Write segment specification
                concat_file.write(f"file '{audio_path}'\n")
                concat_file.write(f"inpoint {start}\n")
                concat_file.write(f"outpoint {end}\n")
        
        try:
            # Run FFmpeg with concat demuxer
            cmd = [
                self.ffmpeg_path,
                "-nostdin",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_path),
                "-ar", "16000",
                "-ac", "1",
                "-acodec", "pcm_s16le",
                str(output_path),
            ]
            
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            
            if proc.returncode != 0:
                error_text = proc.stderr.decode(errors='ignore')
                raise AudioDecodeError(f"FFmpeg condensation failed: {error_text}")
                
        finally:
            # Clean up concat file
            concat_path.unlink(missing_ok=True)
    
    def _condense_with_splitting(
        self,
        audio_path: Path,
        timestamps: list[dict[str, float]],
        output_dir: Path,
        max_duration_s: float,
        min_gap_s: float,
        margin_s: float,
    ) -> list[Path]:
        """Condense audio with intelligent splitting at silence gaps."""
        # Calculate silence gaps between speech segments
        silence_gaps = self._calculate_silence_gaps(timestamps)
        
        # Calculate cumulative duration to find split points
        split_points = self._find_split_points(
            timestamps,
            silence_gaps,
            max_duration_s,
            min_gap_s,
        )
        
        if not split_points:
            # No safe split points, but file is too long
            # Try with progressively smaller gap requirements
            for fallback_gap in [4.0, 3.0, 2.0]:
                split_points = self._find_split_points(
                    timestamps,
                    silence_gaps,
                    max_duration_s,
                    fallback_gap,
                )
                if split_points:
                    break
        
        if not split_points:
            total_minutes = sum(ts['end'] - ts['start'] for ts in timestamps) / 60
            raise AudioProcessingError(
                f"Cannot split {total_minutes:.1f}-minute audio: "
                "No silence gaps ≥2 seconds found. "
                "Consider pre-splitting manually or using a different engine."
            )
        
        # Split timestamps at the found points
        output_files = []
        current_start_idx = 0
        part_num = 1
        
        for split_idx in split_points:
            segment_timestamps = timestamps[current_start_idx:split_idx + 1]
            output_path = output_dir / f"{audio_path.stem}_condensed_part_{part_num:03d}.wav"
            
            self._condense_segments(audio_path, segment_timestamps, output_path, margin_s)
            output_files.append(output_path)
            
            current_start_idx = split_idx + 1
            part_num += 1
        
        # Process remaining timestamps
        if current_start_idx < len(timestamps):
            segment_timestamps = timestamps[current_start_idx:]
            output_path = output_dir / f"{audio_path.stem}_condensed_part_{part_num:03d}.wav"
            self._condense_segments(audio_path, segment_timestamps, output_path, margin_s)
            output_files.append(output_path)
        
        return output_files
    
    def _calculate_silence_gaps(
        self,
        timestamps: list[dict[str, float]],
    ) -> list[tuple[float, float]]:
        """Calculate silence gaps between speech segments.
        
        Returns:
            List of (start, end) tuples for each silence gap
        """
        gaps = []
        for i in range(len(timestamps) - 1):
            gap_start = timestamps[i]['end']
            gap_end = timestamps[i + 1]['start']
            if gap_end > gap_start:
                gaps.append((gap_start, gap_end))
        return gaps
    
    def _find_split_points(
        self,
        timestamps: list[dict[str, float]],
        silence_gaps: list[tuple[float, float]],
        max_duration_s: float,
        min_gap_s: float,
    ) -> list[int]:
        """Find indices where to split the timestamps.
        
        Returns:
            List of timestamp indices after which to split
        """
        split_points = []
        cumulative_duration = 0.0
        target_duration = max_duration_s * 0.85  # Target 85% of max to leave room
        
        for i, ts in enumerate(timestamps):
            segment_duration = ts['end'] - ts['start']
            cumulative_duration += segment_duration
            
            if cumulative_duration >= target_duration:
                # Find a suitable gap near this point
                cut_point = self._find_safe_cut_point(
                    i,
                    timestamps,
                    silence_gaps,
                    min_gap_s,
                )
                
                if cut_point is not None:
                    split_points.append(cut_point)
                    # Reset cumulative duration from the cut point
                    cumulative_duration = sum(
                        timestamps[j]['end'] - timestamps[j]['start']
                        for j in range(cut_point + 1, i + 1)
                    )
        
        return split_points
    
    def _find_safe_cut_point(
        self,
        target_idx: int,
        timestamps: list[dict[str, float]],
        silence_gaps: list[tuple[float, float]],
        min_gap_s: float,
    ) -> int | None:
        """Find optimal cut point near target index.
        
        Strategy:
            1. Search within ±2 indices of target for gaps >= min_gap_s
            2. Expand search to ±5 indices
            3. Expand to ±10 indices
            
        Returns:
            Index of timestamp after which to split, or None
        """
        for search_radius in [2, 5, 10]:
            start_idx = max(0, target_idx - search_radius)
            end_idx = min(len(timestamps) - 1, target_idx + search_radius)
            
            # Check gaps in this range
            best_gap_idx = None
            best_gap_duration = 0.0
            
            for gap_idx in range(start_idx, min(end_idx, len(silence_gaps))):
                gap_start, gap_end = silence_gaps[gap_idx]
                gap_duration = gap_end - gap_start
                
                if gap_duration >= min_gap_s and gap_duration > best_gap_duration:
                    best_gap_idx = gap_idx
                    best_gap_duration = gap_duration
            
            if best_gap_idx is not None:
                return best_gap_idx
        
        return None
