from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from vociferous.audio.ffmpeg_condenser import FFmpegCondenser

if TYPE_CHECKING:
    from vociferous.domain.model import SegmentationProfile


class CondenserComponent:
    """Condense audio using precomputed timestamps with intelligent chunking."""

    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        self._condenser = FFmpegCondenser(ffmpeg_path=ffmpeg_path)

    def condense(
        self,
        timestamps_path: Path | str,
        audio_path: Path | str,
        *,
        output_path: Path | None = None,
        segmentation_profile: SegmentationProfile | None = None,
        # Legacy parameters (deprecated, use profile instead)
        margin_ms: int | None = None,
        max_duration_s: float | None = None,
        min_gap_for_split_s: float | None = None,
    ) -> list[Path]:
        """Condense audio using JSON timestamps with intelligent chunking.
        
        Args:
            timestamps_path: Path to VAD timestamps JSON file
            audio_path: Path to audio file to condense
            output_path: Optional custom output path (disables splitting)
            segmentation_profile: SegmentationProfile with all chunking parameters
            margin_ms: Legacy: boundary margin in milliseconds
            max_duration_s: Legacy: max chunk duration
            min_gap_for_split_s: Legacy: min gap for splits
            
        Returns:
            List of output file paths
        """
        timestamps_path = Path(timestamps_path)
        audio_path = Path(audio_path)
        with open(timestamps_path) as f:
            timestamps = json.load(f)

        output_dir = output_path.parent if output_path else None
        
        # Resolve parameters: profile overrides legacy
        if segmentation_profile:
            params = {
                'max_chunk_s': segmentation_profile.max_chunk_s,
                'chunk_search_start_s': segmentation_profile.chunk_search_start_s,
                'min_gap_for_split_s': segmentation_profile.min_gap_for_split_s,
                'boundary_margin_s': segmentation_profile.boundary_margin_s,
                'max_intra_gap_s': segmentation_profile.max_intra_gap_s,
            }
        else:
            # Legacy path (backward compat)
            params = {
                'max_chunk_s': max_duration_s if max_duration_s is not None else 60.0,
                'chunk_search_start_s': 30.0,
                'min_gap_for_split_s': min_gap_for_split_s if min_gap_for_split_s is not None else 3.0,
                'boundary_margin_s': (margin_ms / 1000.0) if margin_ms is not None else 0.30,
                'max_intra_gap_s': 0.8,
            }
        
        # When custom output is specified, disable splitting to ensure single file
        if output_path:
            params['max_chunk_s'] = float('inf')
        
        outputs = self._condenser.condense(
            audio_path,
            timestamps,
            output_dir=output_dir,
            **params,
        )

        # Handle single output rename (legacy behavior)
        if output_path is not None and len(outputs) == 1:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            outputs[0].rename(output_path)
            outputs = [output_path]

        return outputs
