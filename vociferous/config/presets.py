"""Configuration presets for common use cases.

This module provides ready-to-use configuration presets for different
use cases, making it easy for GUI users to quickly select appropriate
settings without understanding all the options.

Usage:
    >>> from vociferous.config.presets import get_engine_preset
    >>> profile = get_engine_preset("balanced")
    >>> print(profile.compute_type)
    float16
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from vociferous.domain.model import EngineConfig, SegmentationProfile

__all__ = [
    "PresetInfo",
    "EnginePresetInfo",
    "SegmentationPresetInfo",
    "ENGINE_PRESETS",
    "SEGMENTATION_PRESETS",
    "get_engine_preset",
    "get_segmentation_preset",
    "list_engine_presets",
    "list_segmentation_presets",
]


T = TypeVar("T")


@dataclass(frozen=True)
class PresetInfo(Generic[T]):
    """Information about a configuration preset.
    
    Attributes:
        name: Preset identifier (e.g., "balanced")
        display_name: Human-readable name (e.g., "Balanced Quality")
        description: Detailed description of the preset
        config: The actual configuration object
    """
    
    name: str
    display_name: str
    description: str
    config: T
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize for GUI consumption."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
        }


# Type aliases for typed presets
EnginePresetInfo = PresetInfo[EngineConfig]
SegmentationPresetInfo = PresetInfo[SegmentationProfile]


# Engine configuration presets
ENGINE_PRESETS: dict[str, EnginePresetInfo] = {
    "balanced": PresetInfo(
        name="balanced",
        display_name="Balanced (Recommended)",
        description="Good balance of quality and speed. Uses Canary-Qwen with FP16 precision.",
        config=EngineConfig(
            model_name="nvidia/canary-qwen-2.5b",
            device="cuda",
            compute_type="float16",
        ),
    ),
    "high_quality": PresetInfo(
        name="high_quality",
        display_name="High Quality",
        description="Maximum accuracy using BF16 precision. Slightly slower but best results.",
        config=EngineConfig(
            model_name="nvidia/canary-qwen-2.5b",
            device="cuda",
            compute_type="bfloat16",
        ),
    ),
    "fast": PresetInfo(
        name="fast",
        display_name="Fast",
        description="Optimized for speed using INT8 quantization. Slightly reduced quality.",
        config=EngineConfig(
            model_name="nvidia/canary-qwen-2.5b",
            device="cuda",
            compute_type="int8",
        ),
    ),
    "cpu_compatible": PresetInfo(
        name="cpu_compatible",
        display_name="CPU Compatible",
        description="Works without NVIDIA GPU. Uses Whisper Turbo on CPU. Slower but widely compatible.",
        config=EngineConfig(
            model_name="turbo",
            device="cpu",
            compute_type="float32",
        ),
    ),
}


# Segmentation configuration presets
SEGMENTATION_PRESETS: dict[str, SegmentationPresetInfo] = {
    "balanced": PresetInfo(
        name="balanced",
        display_name="Balanced (Recommended)",
        description="Good for most audio. Detects speech reliably while ignoring brief noises.",
        config=SegmentationProfile(
            threshold=0.5,
            min_silence_ms=500,
            min_speech_ms=250,
            speech_pad_ms=250,
            max_chunk_s=60.0,
            chunk_search_start_s=30.0,
            min_gap_for_split_s=3.0,
        ),
    ),
    "sensitive": PresetInfo(
        name="sensitive",
        display_name="Sensitive",
        description="Captures quieter speech. Good for soft-spoken speakers or distant microphones.",
        config=SegmentationProfile(
            threshold=0.3,
            min_silence_ms=300,
            min_speech_ms=200,
            speech_pad_ms=300,
            max_chunk_s=60.0,
            chunk_search_start_s=30.0,
            min_gap_for_split_s=2.0,
        ),
    ),
    "strict": PresetInfo(
        name="strict",
        display_name="Strict",
        description="Ignores background noise. Good for noisy environments or recordings with music.",
        config=SegmentationProfile(
            threshold=0.7,
            min_silence_ms=700,
            min_speech_ms=300,
            speech_pad_ms=200,
            max_chunk_s=60.0,
            chunk_search_start_s=30.0,
            min_gap_for_split_s=4.0,
        ),
    ),
    "podcast": PresetInfo(
        name="podcast",
        display_name="Podcast/Interview",
        description="Optimized for dialogue with multiple speakers. Preserves natural pauses.",
        config=SegmentationProfile(
            threshold=0.5,
            min_silence_ms=400,
            min_speech_ms=300,
            speech_pad_ms=200,
            max_chunk_s=60.0,
            chunk_search_start_s=40.0,
            min_gap_for_split_s=2.5,
        ),
    ),
    "lecture": PresetInfo(
        name="lecture",
        display_name="Lecture/Presentation",
        description="Optimized for single speaker with longer pauses. Good for educational content.",
        config=SegmentationProfile(
            threshold=0.4,
            min_silence_ms=600,
            min_speech_ms=250,
            speech_pad_ms=300,
            max_chunk_s=60.0,
            chunk_search_start_s=35.0,
            min_gap_for_split_s=3.5,
        ),
    ),
}


def get_engine_preset(name: str) -> EngineConfig:
    """Get engine configuration preset by name.
    
    Args:
        name: Preset name (e.g., "balanced", "high_quality", "fast", "cpu_compatible")
    
    Returns:
        EngineConfig with preset values
    
    Raises:
        KeyError: If preset doesn't exist
    
    Example:
        >>> config = get_engine_preset("balanced")
        >>> print(config.compute_type)
        float16
    """
    if name not in ENGINE_PRESETS:
        available = ", ".join(ENGINE_PRESETS.keys())
        raise KeyError(f"Unknown engine preset: {name}. Available: {available}")
    
    return ENGINE_PRESETS[name].config


def get_segmentation_preset(name: str) -> SegmentationProfile:
    """Get segmentation configuration preset by name.
    
    Args:
        name: Preset name (e.g., "balanced", "sensitive", "strict")
    
    Returns:
        SegmentationProfile with preset values
    
    Raises:
        KeyError: If preset doesn't exist
    
    Example:
        >>> profile = get_segmentation_preset("sensitive")
        >>> print(profile.threshold)
        0.3
    """
    if name not in SEGMENTATION_PRESETS:
        available = ", ".join(SEGMENTATION_PRESETS.keys())
        raise KeyError(f"Unknown segmentation preset: {name}. Available: {available}")
    
    return SEGMENTATION_PRESETS[name].config


def list_engine_presets() -> list[EnginePresetInfo]:
    """List all available engine presets.
    
    Returns:
        List of PresetInfo for all engine presets
    
    Example:
        >>> for preset in list_engine_presets():
        ...     print(f"{preset.name}: {preset.description}")
    """
    return list(ENGINE_PRESETS.values())


def list_segmentation_presets() -> list[SegmentationPresetInfo]:
    """List all available segmentation presets.
    
    Returns:
        List of PresetInfo for all segmentation presets
    
    Example:
        >>> for preset in list_segmentation_presets():
        ...     print(f"{preset.name}: {preset.description}")
    """
    return list(SEGMENTATION_PRESETS.values())
