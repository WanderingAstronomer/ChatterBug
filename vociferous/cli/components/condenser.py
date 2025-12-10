from __future__ import annotations

import json
from pathlib import Path

from vociferous.audio.ffmpeg_condenser import FFmpegCondenser


class CondenserComponent:
    """Condense audio using precomputed timestamps."""

    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        self._condenser = FFmpegCondenser(ffmpeg_path=ffmpeg_path)

    def condense(
        self,
        timestamps_path: Path | str,
        audio_path: Path | str,
        *,
        output_path: Path | None = None,
        margin_ms: int = 1000,
        max_duration_min: int = 30,
        min_gap_for_split_s: float = 5.0,
    ) -> list[Path]:
        """Condense audio using JSON timestamps, returning output files."""
        timestamps_path = Path(timestamps_path)
        audio_path = Path(audio_path)
        with open(timestamps_path, "r") as f:
            timestamps = json.load(f)

        output_dir = output_path.parent if output_path else None
        outputs = self._condenser.condense(
            audio_path,
            timestamps,
            output_dir=output_dir,
            max_duration_minutes=max_duration_min,
            min_gap_for_split_s=min_gap_for_split_s,
            boundary_margin_s=margin_ms / 1000.0,
        )

        if output_path is not None:
            if len(outputs) != 1:
                raise ValueError("Custom output requires a single condensed file")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            outputs[0].rename(output_path)
            outputs = [output_path]

        return outputs
