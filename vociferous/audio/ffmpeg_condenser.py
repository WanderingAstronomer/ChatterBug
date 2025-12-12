"""O(n) audio condensation with intelligent splitting for long files.

Uses FFmpeg concat demuxer for single-pass O(n) performance, with intelligent
splitting that respects engine duration limits (e.g., 60s for Canary-Qwen).

Key features:
- Correct duration accounting: speech + preserved gaps + margins
- Natural splits at 3s+ silence gaps when possible
- Force-split fallback with backwards scan to find optimal cut point
- Overlap/overrun prevention with proper boundary clamping
- Comprehensive logging at all decision points
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from vociferous.domain.exceptions import (
    AudioDecodeError,
    AudioProcessingError,
    UnsplittableSegmentError,
)

logger = logging.getLogger(__name__)


class FFmpegCondenser:
    """Single-pass O(n) audio condensation with intelligent splitting.
    
    Condenses audio by extracting only speech segments using FFmpeg's concat
    demuxer, achieving O(n) performance where n is the total audio duration.
    For files exceeding max_chunk_s, intelligently splits at silence gaps
    to produce multiple output files that respect engine input limits.
    
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
        max_chunk_s: float = 60.0,
        chunk_search_start_s: float = 30.0,
        min_gap_for_split_s: float = 3.0,
        boundary_margin_s: float = 0.30,
        max_intra_gap_s: float = 0.8,
    ) -> list[Path]:
        """Condense audio with intelligent chunking that respects duration limits.
        
        Args:
            audio_path: Input audio file
            speech_timestamps: List of {'start': seconds, 'end': seconds} from SileroVAD
            output_dir: Directory for output (default: same as input)
            max_chunk_s: Hard ceiling for chunk duration (default: 60s for Canary)
            chunk_search_start_s: When to start looking for split points (default: 30s)
            min_gap_for_split_s: Minimum silence gap for natural splits (default: 3s)
            boundary_margin_s: Silence preserved at file edges (default: 0.3s)
            max_intra_gap_s: Maximum preserved gap inside chunks (default: 0.8s)
            
        Returns:
            List of output file paths (1 if short, N if split)
            
        Raises:
            AudioProcessingError: If no speech timestamps provided
            UnsplittableSegmentError: If a single segment exceeds max_chunk_s
        """
        audio_path = Path(audio_path)
        output_dir = output_dir or audio_path.parent
        output_dir = Path(output_dir)
        
        if not speech_timestamps:
            raise AudioProcessingError(
                f"No speech timestamps provided for {audio_path}. "
                "Run SileroVAD.detect_speech() before condensing audio."
            )
        
        # Calculate silence gaps between segments
        silence_gaps = self._calculate_silence_gaps(speech_timestamps)
        
        # Find split points using new algorithm
        split_indices = self._find_split_points(
            speech_timestamps,
            silence_gaps,
            min_gap_s=min_gap_for_split_s,
            search_start_s=chunk_search_start_s,
            max_chunk_s=max_chunk_s,
            max_intra_gap_s=max_intra_gap_s,
            boundary_margin_s=boundary_margin_s,
        )
        
        # Split timestamps into chunks
        chunks = self._split_timestamps_into_chunks(speech_timestamps, split_indices)
        
        # Log chunking summary (DEBUG level to avoid polluting progress display)
        chunk_durations = [
            self._calculate_chunk_duration(c, max_intra_gap_s, boundary_margin_s)
            for c in chunks
        ]
        logger.debug(
            f"Chunking {audio_path.name}: {len(chunks)} chunks, "
            f"durations=[{', '.join(f'{d:.1f}s' for d in chunk_durations)}]"
        )
        
        # Get total audio duration for clamping
        total_duration_s = self._get_audio_duration(audio_path)
        
        # Render each chunk to file
        output_files: list[Path] = []
        for chunk_num, chunk_timestamps in enumerate(chunks, start=1):
            if len(chunks) == 1:
                output_path = output_dir / f"{audio_path.stem}_condensed.wav"
            else:
                output_path = output_dir / f"{audio_path.stem}_condensed_part_{chunk_num:03d}.wav"
            
            self._condense_segments(
                audio_path,
                chunk_timestamps,
                output_path,
                margin_s=boundary_margin_s,
                max_intra_gap_s=max_intra_gap_s,
                total_audio_duration_s=total_duration_s,
            )
            output_files.append(output_path)
        
        return output_files
    
    def _calculate_chunk_duration(
        self,
        segments: list[dict[str, float]],
        max_intra_gap_s: float = 0.8,
        boundary_margin_s: float = 0.3,
    ) -> float:
        """Calculate true chunk duration including speech + preserved gaps + margins.
        
        This is the ground truth for chunk duration and must be used everywhere
        to ensure we never exceed max_chunk_s.
        
        Args:
            segments: Speech segments in the chunk
            max_intra_gap_s: Maximum preserved gap between segments
            boundary_margin_s: Margin at chunk boundaries
            
        Returns:
            Total duration in seconds
        """
        if not segments:
            return 0.0
        
        total = 0.0
        
        # Add all speech segment durations
        for seg in segments:
            total += seg['end'] - seg['start']
        
        # Add preserved gaps between segments (capped at max_intra_gap_s)
        for i in range(len(segments) - 1):
            gap_duration = segments[i + 1]['start'] - segments[i]['end']
            preserved_gap = min(gap_duration, max_intra_gap_s)
            total += preserved_gap
        
        # Add boundary margins (start + end)
        total += 2 * boundary_margin_s
        
        return total
    
    def _calculate_silence_gaps(
        self,
        timestamps: list[dict[str, float]],
    ) -> list[tuple[float, float, float, int]]:
        """Calculate silence gaps between consecutive speech segments.
        
        Uses GLOBAL indexing: silence_gaps[i] corresponds to the gap AFTER timestamps[i].
        
        Args:
            timestamps: Speech segments from VAD
            
        Returns:
            List of (gap_start, gap_end, duration, after_segment_idx)
            Length will be len(timestamps) - 1
        """
        gaps: list[tuple[float, float, float, int]] = []
        
        for i in range(len(timestamps) - 1):
            gap_start = timestamps[i]['end']
            gap_end = timestamps[i + 1]['start']
            gap_duration = gap_end - gap_start
            
            if gap_duration > 0:
                gaps.append((gap_start, gap_end, gap_duration, i))
            else:
                # Overlapping or touching segments - treat as zero gap
                gaps.append((gap_start, gap_start, 0.0, i))
                logger.debug(
                    f"Overlapping/touching segments at {i}: "
                    f"seg[{i}] ends at {gap_start:.3f}s, "
                    f"seg[{i+1}] starts at {gap_end:.3f}s"
                )
        
        # Log summary statistics
        if gaps:
            gap_durations = [g[2] for g in gaps]
            large_gaps = sum(1 for d in gap_durations if d >= 3.0)
            logger.debug(
                f"Silence gaps: count={len(gaps)}, "
                f"mean={sum(gap_durations)/len(gaps):.2f}s, "
                f"max={max(gap_durations):.2f}s, "
                f"gaps≥3s={large_gaps}"
            )
        
        return gaps
    
    def _find_split_points(
        self,
        timestamps: list[dict[str, float]],
        silence_gaps: list[tuple[float, float, float, int]],
        min_gap_s: float = 3.0,
        search_start_s: float = 30.0,
        max_chunk_s: float = 60.0,
        max_intra_gap_s: float = 0.8,
        boundary_margin_s: float = 0.3,
    ) -> list[int]:
        """Find split points with correct duration accounting and global indexing.
        
        Algorithm:
        1. Accumulate segments into chunks
        2. Start looking for natural splits (3s+ gaps) after 30s
        3. Force-split if hitting 60s ceiling with no natural gaps
        
        Args:
            timestamps: All speech segments
            silence_gaps: Gaps between segments (global indexed)
            min_gap_s: Minimum silence for natural splits
            search_start_s: When to start looking for splits
            max_chunk_s: Hard ceiling for chunk duration
            max_intra_gap_s: Max preserved gap inside chunks
            boundary_margin_s: Margin at chunk edges
            
        Returns:
            List of segment indices after which to split
        """
        split_points: list[int] = []
        current_chunk_start_idx = 0
        
        while current_chunk_start_idx < len(timestamps):
            chunk_segments: list[dict[str, float]] = []
            looking_for_split = False
            
            for i in range(current_chunk_start_idx, len(timestamps)):
                chunk_segments.append(timestamps[i])
                
                # Calculate true chunk duration
                chunk_duration = self._calculate_chunk_duration(
                    chunk_segments,
                    max_intra_gap_s,
                    boundary_margin_s,
                )
                
                # Start looking for splits after search_start_s
                if chunk_duration >= search_start_s:
                    looking_for_split = True
                
                # Check for natural split (good gap) using GLOBAL index
                if looking_for_split and i < len(silence_gaps):
                    gap = silence_gaps[i]
                    if gap[2] >= min_gap_s:
                        # Found natural split point
                        logger.debug(
                            f"Natural split after segment {i}: "
                            f"{gap[2]:.1f}s silence gap, "
                            f"chunk duration {chunk_duration:.1f}s"
                        )
                        split_points.append(i)
                        current_chunk_start_idx = i + 1
                        break
                
                # Force-split if hitting ceiling
                if chunk_duration >= max_chunk_s:
                    logger.debug(
                        f"Force-split triggered: chunk duration {chunk_duration:.1f}s "
                        f"exceeds {max_chunk_s:.1f}s, no {min_gap_s:.1f}s+ gap found"
                    )
                    
                    force_split_idx = self._find_force_split_location(
                        chunk_segments,
                        current_chunk_start_idx,
                        max_chunk_s=max_chunk_s,
                        max_intra_gap_s=max_intra_gap_s,
                        boundary_margin_s=boundary_margin_s,
                    )
                    
                    split_points.append(force_split_idx)
                    current_chunk_start_idx = force_split_idx + 1
                    break
            else:
                # Processed all remaining segments without needing a split
                break
        
        return split_points
    
    def _find_force_split_location(
        self,
        chunk_segments: list[dict[str, float]],
        chunk_start_idx: int,
        max_chunk_s: float = 60.0,
        max_intra_gap_s: float = 0.8,
        boundary_margin_s: float = 0.3,
    ) -> int:
        """Find best force-split location within chunk.
        
        Scans backwards from end to find the largest valid chunk under max_chunk_s.
        
        Args:
            chunk_segments: Segments in current chunk only
            chunk_start_idx: Global index of first segment in chunk
            max_chunk_s: Hard ceiling for chunk duration
            max_intra_gap_s: Max preserved gap
            boundary_margin_s: Edge margin
            
        Returns:
            Global segment index where to split
            
        Raises:
            UnsplittableSegmentError: If no valid split point exists
        """
        # Special case: single segment that's too long
        if len(chunk_segments) == 1:
            single_duration = self._calculate_chunk_duration(
                chunk_segments,
                max_intra_gap_s,
                boundary_margin_s,
            )
            
            if single_duration > max_chunk_s:
                seg = chunk_segments[0]
                raise UnsplittableSegmentError(
                    segment_start=seg["start"],
                    segment_end=seg["end"],
                    max_chunk_s=max_chunk_s,
                )
        
        # Scan backwards to find largest valid chunk under max
        target_duration = max_chunk_s - 2.0  # 58s safety margin
        best_idx: int | None = None
        best_duration: float | None = None
        best_distance = float('inf')
        
        # Scan from largest to smallest (backwards)
        # Range includes 0 to allow splitting after first segment
        for local_idx in range(len(chunk_segments) - 1, -1, -1):
            test_segments = chunk_segments[:local_idx + 1]
            test_duration = self._calculate_chunk_duration(
                test_segments,
                max_intra_gap_s,
                boundary_margin_s,
            )
            
            # Must be under max (strict)
            if test_duration > max_chunk_s:
                continue
            
            # Prefer closest to target (58s)
            distance = abs(test_duration - target_duration)
            if distance < best_distance:
                best_distance = distance
                best_idx = chunk_start_idx + local_idx
                best_duration = test_duration
        
        # No valid split point found
        if best_idx is None:
            # Use the overall range of the chunk
            first_seg = chunk_segments[0]
            last_seg = chunk_segments[-1]
            raise UnsplittableSegmentError(
                segment_start=first_seg["start"],
                segment_end=last_seg["end"],
                max_chunk_s=max_chunk_s,
            )
        
        logger.debug(
            f"Force-split at segment {best_idx}: "
            f"chunk duration {best_duration:.1f}s "
            f"(target was {target_duration:.1f}s)"
        )
        
        return best_idx
    
    def _split_timestamps_into_chunks(
        self,
        timestamps: list[dict[str, float]],
        split_indices: list[int],
    ) -> list[list[dict[str, float]]]:
        """Split timestamp list at specified indices.
        
        Args:
            timestamps: Full list of speech segments
            split_indices: Indices where to split (inclusive)
            
        Returns:
            List of chunk timestamp lists
            
        Example:
            timestamps = [seg0, seg1, seg2, seg3, seg4]
            split_indices = [1, 3]
            Returns: [[seg0, seg1], [seg2, seg3], [seg4]]
        """
        if not split_indices:
            return [timestamps]
        
        chunks: list[list[dict[str, float]]] = []
        start_idx = 0
        
        for split_idx in split_indices:
            # Include segment at split_idx in current chunk
            chunk = timestamps[start_idx:split_idx + 1]
            chunks.append(chunk)
            start_idx = split_idx + 1
        
        # Add remaining segments as final chunk
        if start_idx < len(timestamps):
            chunks.append(timestamps[start_idx:])
        
        return chunks
    
    def _get_audio_duration(self, audio_path: Path) -> float:
        """Get total audio duration using ffprobe.
        
        Args:
            audio_path: Audio file to measure
            
        Returns:
            Duration in seconds
        """
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            
            return float(result.stdout.strip())
        
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.warning(
                f"Could not get audio duration via ffprobe: {e}. "
                f"Using timestamp-based estimate."
            )
            # Return a safe overestimate - effectively no clamping
            return 999999.0
    
    def _condense_segments(
        self,
        audio_path: Path,
        timestamps: list[dict[str, float]],
        output_path: Path,
        margin_s: float = 0.30,
        max_intra_gap_s: float = 0.8,
        total_audio_duration_s: float | None = None,
    ) -> None:
        """Condense audio segments with proper boundary clamping.
        
        Prevents overlap between segments and overrun past file end.
        
        Args:
            audio_path: Input audio file
            timestamps: Speech segments for this chunk
            output_path: Output file path
            margin_s: Silence margin at edges
            max_intra_gap_s: Maximum preserved gap between segments
            total_audio_duration_s: Total file duration for clamping
        """
        if not timestamps:
            return
        
        # Get total duration if not provided
        if total_audio_duration_s is None:
            total_audio_duration_s = self._get_audio_duration(audio_path)
        
        logger.debug(
            f"Rendering chunk: {len(timestamps)} segments to {output_path.name}"
        )
        
        # Create concat file list for FFmpeg
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=True) as concat_file:
            concat_path = Path(concat_file.name)
            previous_end = 0.0
            
            for i, seg in enumerate(timestamps):
                start = seg['start']
                end = seg['end']
                
                if end - start <= 0:
                    continue
                
                # Add margin at start of first segment, clamp overlap otherwise
                start = max(0, start - margin_s) if i == 0 else max(start, previous_end)
                
                # Extend into gap or add trailing margin
                if i < len(timestamps) - 1:
                    next_start = timestamps[i + 1]['start']
                    gap_duration = next_start - end
                    # Preserve gap up to max_intra_gap_s
                    preserved_gap = min(gap_duration, max_intra_gap_s)
                    end += preserved_gap
                else:
                    # Last segment: add trailing margin
                    end += margin_s
                
                # Clamp to file bounds
                end = min(end, total_audio_duration_s)
                
                # Ensure start < end after all adjustments
                if start >= end:
                    logger.warning(
                        f"Segment {i} has invalid range after adjustments: "
                        f"start={start:.3f}, end={end:.3f}. Skipping."
                    )
                    continue
                
                # Store for next iteration
                previous_end = end
                
                # Write segment specification (use absolute path)
                concat_file.write(f"file '{audio_path.absolute()}'\n")
                concat_file.write(f"inpoint {start}\n")
                concat_file.write(f"outpoint {end}\n")
            
            concat_file.flush()
            
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
                capture_output=True,
                check=False,
            )
            
            if proc.returncode != 0:
                error_text = proc.stderr.decode(errors='ignore')
                raise AudioDecodeError(f"FFmpeg condensation failed: {error_text}")
