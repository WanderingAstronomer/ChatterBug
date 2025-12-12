"""Audio preprocessing pipeline using FFmpeg filters.

Provides preprocessing options for audio before transcription, including:
- Noise reduction (high/low pass filtering)
- Volume normalization (EBU R128)
- Highpass/lowpass filtering
- Volume adjustment

Presets are available for common use cases:
- none: No preprocessing
- basic: Volume normalization only
- clean: Noise reduction + normalization
- phone: Optimized for phone recordings
- podcast: Optimized for podcast audio

Usage:
    from vociferous.audio.preprocessing import PreprocessingConfig, AudioPreprocessor
    
    # Use a preset
    config = PreprocessingConfig.from_preset("clean")
    preprocessor = AudioPreprocessor(config)
    
    output_path = preprocessor.preprocess(input_path, output_path)
    
    # Or configure manually
    config = PreprocessingConfig(denoise=True, normalize=True, highpass_hz=200)
    preprocessor = AudioPreprocessor(config)
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vociferous.domain.exceptions import AudioProcessingError, DependencyError

if TYPE_CHECKING:
    from vociferous.app.progress import ProgressTracker

logger = logging.getLogger(__name__)


# Available presets with their configurations
PRESETS: dict[str, dict[str, Any]] = {
    "none": {},
    "basic": {"normalize": True},
    "clean": {"denoise": True, "normalize": True},
    "phone": {"denoise": True, "normalize": True, "highpass_hz": 300, "lowpass_hz": 3400},
    "podcast": {"normalize": True, "highpass_hz": 80},
}


@dataclass
class PreprocessingConfig:
    """Configuration for audio preprocessing.

    Attributes:
        denoise: Apply noise reduction (high/low pass filtering)
        normalize: Apply EBU R128 loudness normalization
        highpass_hz: Apply highpass filter at this frequency (Hz)
        lowpass_hz: Apply lowpass filter at this frequency (Hz)
        volume_adjust_db: Adjust volume by this many dB
    """

    denoise: bool = False
    normalize: bool = False
    highpass_hz: int | None = None
    lowpass_hz: int | None = None
    volume_adjust_db: float | None = None

    @classmethod
    def from_preset(cls, preset: str) -> PreprocessingConfig:
        """Create config from preset name.

        Args:
            preset: Preset name (none, basic, clean, phone, podcast)

        Returns:
            PreprocessingConfig with preset settings

        Raises:
            ValueError: If preset name is unknown
        """
        if preset not in PRESETS:
            valid_presets = ", ".join(PRESETS.keys())
            raise ValueError(f"Unknown preset: '{preset}'. Choose from: {valid_presets}")

        return cls(**PRESETS[preset])

    @classmethod
    def available_presets(cls) -> list[str]:
        """Get list of available preset names."""
        return list(PRESETS.keys())

    def needs_preprocessing(self) -> bool:
        """Check if any preprocessing is enabled."""
        return any([
            self.denoise,
            self.normalize,
            self.highpass_hz is not None,
            self.lowpass_hz is not None,
            self.volume_adjust_db is not None,
        ])


class AudioPreprocessor:
    """Applies audio preprocessing filters using FFmpeg.

    Supports noise reduction, volume normalization, and frequency filtering.
    Uses FFmpeg's audio filters for processing.

    Args:
        config: Preprocessing configuration
        ffmpeg_path: Path to ffmpeg binary (default: "ffmpeg")

    Example:
        config = PreprocessingConfig.from_preset("clean")
        preprocessor = AudioPreprocessor(config)
        
        output = preprocessor.preprocess(
            Path("noisy.wav"),
            Path("clean.wav"),
        )
    """

    def __init__(
        self,
        config: PreprocessingConfig,
        ffmpeg_path: str = "ffmpeg",
    ) -> None:
        self.config = config
        self.ffmpeg_path = ffmpeg_path

    def needs_preprocessing(self) -> bool:
        """Check if any preprocessing is enabled."""
        return self.config.needs_preprocessing()

    def preprocess(
        self,
        input_path: Path,
        output_path: Path,
        progress: ProgressTracker | None = None,
    ) -> Path:
        """Apply preprocessing filters to audio file.

        Args:
            input_path: Path to input audio file
            output_path: Path for output audio file
            progress: Optional progress tracker for UI feedback

        Returns:
            Path to preprocessed audio file (may be input_path if no preprocessing needed)

        Raises:
            DependencyError: If FFmpeg is not available
            AudioProcessingError: If preprocessing fails
        """
        if not self.needs_preprocessing():
            logger.debug("No preprocessing needed, returning input path")
            return input_path

        # Check FFmpeg availability
        if not shutil.which(self.ffmpeg_path):
            raise DependencyError.missing_ffmpeg()

        task_id = None
        if progress:
            task_id = progress.add_step("Preprocessing audio...", total=None)

        try:
            filters = self._build_filter_chain()
            
            cmd = [
                self.ffmpeg_path,
                "-i", str(input_path),
                "-af", filters,
                "-ar", "16000",  # Ensure 16kHz for ASR
                "-ac", "1",      # Ensure mono
                "-y",            # Overwrite output
                str(output_path),
            ]

            logger.debug(f"Running FFmpeg: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                check=False,
            )

            if result.returncode != 0:
                stderr = result.stderr.decode(errors="ignore")
                raise AudioProcessingError(
                    "Audio preprocessing failed",
                    context={
                        "input_file": str(input_path),
                        "filters": filters,
                        "ffmpeg_exit_code": result.returncode,
                    },
                    suggestions=[
                        "Try without preprocessing: remove --preprocess flag",
                        "Check FFmpeg is installed: ffmpeg -version",
                        f"FFmpeg error: {stderr[:200] if stderr else 'No error output'}",
                    ],
                )

            if progress and task_id is not None:
                progress.complete(task_id)
                progress.print(f"✓ Preprocessing applied: {self._describe_filters()}")

            logger.info(f"Preprocessing complete: {self._describe_filters()}")
            return output_path

        except subprocess.SubprocessError as e:
            if progress and task_id is not None:
                progress.complete(task_id)

            raise AudioProcessingError(
                "Audio preprocessing failed",
                cause=e,
                suggestions=["Check FFmpeg installation"],
            ) from e

    def _build_filter_chain(self) -> str:
        """Build FFmpeg filter chain from config.

        Returns:
            FFmpeg filter chain string (e.g., "highpass=f=200,loudnorm")
        """
        filters: list[str] = []

        if self.config.highpass_hz:
            filters.append(f"highpass=f={self.config.highpass_hz}")

        if self.config.lowpass_hz:
            filters.append(f"lowpass=f={self.config.lowpass_hz}")

        if self.config.denoise:
            # Simple noise reduction using high/low pass if not already specified
            if not self.config.highpass_hz:
                filters.append("highpass=f=200")  # Remove low-frequency rumble
            if not self.config.lowpass_hz:
                filters.append("lowpass=f=3500")  # Remove high-frequency hiss

        if self.config.volume_adjust_db:
            filters.append(f"volume={self.config.volume_adjust_db}dB")

        if self.config.normalize:
            # EBU R128 loudness normalization
            filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")

        return ",".join(filters)

    def _describe_filters(self) -> str:
        """Human-readable description of applied filters."""
        descriptions: list[str] = []

        if self.config.denoise:
            descriptions.append("noise reduction")
        if self.config.normalize:
            descriptions.append("volume normalization")
        if self.config.highpass_hz:
            descriptions.append(f"highpass {self.config.highpass_hz}Hz")
        if self.config.lowpass_hz:
            descriptions.append(f"lowpass {self.config.lowpass_hz}Hz")
        if self.config.volume_adjust_db:
            descriptions.append(f"{self.config.volume_adjust_db:+.1f}dB gain")

        return ", ".join(descriptions) if descriptions else "none"


# ============================================================================
# Convenience Functions
# ============================================================================


def preprocess_audio(
    input_path: Path,
    output_path: Path,
    preset: str = "none",
    progress: ProgressTracker | None = None,
) -> Path:
    """Convenience function to preprocess audio with a preset.

    Args:
        input_path: Path to input audio file
        output_path: Path for output audio file
        preset: Preset name (none, basic, clean, phone, podcast)
        progress: Optional progress tracker

    Returns:
        Path to preprocessed audio (may be input_path if preset is "none")
    """
    config = PreprocessingConfig.from_preset(preset)
    preprocessor = AudioPreprocessor(config)
    return preprocessor.preprocess(input_path, output_path, progress)
