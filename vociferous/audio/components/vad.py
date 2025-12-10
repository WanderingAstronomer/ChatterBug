from __future__ import annotations

from pathlib import Path
from typing import Any

from vociferous.audio.silero_vad import SileroVAD


class VADComponent:
    """Speech timestamp detection via Silero VAD."""

    def __init__(self, sample_rate: int = 16000, device: str = "cpu") -> None:
        self._vad = SileroVAD(sample_rate=sample_rate, device=device)

    def detect(
        self,
        audio_path: Path | str,
        *,
        output_path: Path | None = None,
        threshold: float = 0.5,
        min_silence_ms: int = 500,
        min_speech_ms: int = 250,
    ) -> list[dict[str, Any]]:
        """Detect speech timestamps and optionally write JSON."""
        return self._vad.detect_speech(
            Path(audio_path),
            threshold=threshold,
            min_silence_ms=min_silence_ms,
            min_speech_ms=min_speech_ms,
            save_json=True,
            output_path=output_path,
        )
