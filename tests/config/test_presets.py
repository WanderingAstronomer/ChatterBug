"""Tests for configuration presets."""

from __future__ import annotations

import pytest

from vociferous.config.presets import (
    ENGINE_PRESETS,
    SEGMENTATION_PRESETS,
    PresetInfo,
    get_engine_preset,
    get_segmentation_preset,
    list_engine_presets,
    list_segmentation_presets,
)
from vociferous.domain.model import EngineConfig, SegmentationProfile


class TestEnginePresets:
    """Tests for engine configuration presets."""

    def test_balanced_preset_exists(self) -> None:
        """Test balanced preset is defined."""
        assert "balanced" in ENGINE_PRESETS

    def test_high_quality_preset_exists(self) -> None:
        """Test high_quality preset is defined."""
        assert "high_quality" in ENGINE_PRESETS

    def test_fast_preset_exists(self) -> None:
        """Test fast preset is defined."""
        assert "fast" in ENGINE_PRESETS

    def test_cpu_compatible_preset_exists(self) -> None:
        """Test cpu_compatible preset is defined."""
        assert "cpu_compatible" in ENGINE_PRESETS

    def test_preset_has_display_name(self) -> None:
        """Test presets have display names."""
        preset = ENGINE_PRESETS["balanced"]
        assert preset.display_name
        assert len(preset.display_name) > 0

    def test_preset_has_description(self) -> None:
        """Test presets have descriptions."""
        preset = ENGINE_PRESETS["balanced"]
        assert preset.description
        assert len(preset.description) > 10


class TestGetEnginePreset:
    """Tests for get_engine_preset function."""

    def test_get_balanced_preset(self) -> None:
        """Test getting balanced preset returns valid config."""
        config = get_engine_preset("balanced")

        assert isinstance(config, EngineConfig)
        assert config.compute_type == "float16"

    def test_get_high_quality_preset(self) -> None:
        """Test high quality preset uses bfloat16."""
        config = get_engine_preset("high_quality")

        assert config.compute_type == "bfloat16"

    def test_get_cpu_compatible_preset(self) -> None:
        """Test CPU preset uses correct device."""
        config = get_engine_preset("cpu_compatible")

        assert config.device == "cpu"

    def test_unknown_preset_raises_keyerror(self) -> None:
        """Test unknown preset name raises KeyError."""
        with pytest.raises(KeyError, match="Unknown engine preset"):
            get_engine_preset("nonexistent_preset")

    def test_keyerror_lists_available_presets(self) -> None:
        """Test KeyError message includes available presets."""
        with pytest.raises(KeyError) as exc_info:
            get_engine_preset("unknown")

        error_msg = str(exc_info.value)
        assert "balanced" in error_msg
        assert "Available" in error_msg


class TestSegmentationPresets:
    """Tests for segmentation configuration presets."""

    def test_balanced_preset_exists(self) -> None:
        """Test balanced preset is defined."""
        assert "balanced" in SEGMENTATION_PRESETS

    def test_sensitive_preset_exists(self) -> None:
        """Test sensitive preset is defined."""
        assert "sensitive" in SEGMENTATION_PRESETS

    def test_strict_preset_exists(self) -> None:
        """Test strict preset is defined."""
        assert "strict" in SEGMENTATION_PRESETS

    def test_podcast_preset_exists(self) -> None:
        """Test podcast preset is defined."""
        assert "podcast" in SEGMENTATION_PRESETS

    def test_lecture_preset_exists(self) -> None:
        """Test lecture preset is defined."""
        assert "lecture" in SEGMENTATION_PRESETS


class TestGetSegmentationPreset:
    """Tests for get_segmentation_preset function."""

    def test_get_balanced_preset(self) -> None:
        """Test getting balanced preset returns valid profile."""
        profile = get_segmentation_preset("balanced")

        assert isinstance(profile, SegmentationProfile)
        assert profile.threshold == 0.5

    def test_get_sensitive_preset_lower_threshold(self) -> None:
        """Test sensitive preset has lower threshold."""
        profile = get_segmentation_preset("sensitive")

        assert profile.threshold < 0.5

    def test_get_strict_preset_higher_threshold(self) -> None:
        """Test strict preset has higher threshold."""
        profile = get_segmentation_preset("strict")

        assert profile.threshold > 0.5

    def test_unknown_preset_raises_keyerror(self) -> None:
        """Test unknown preset name raises KeyError."""
        with pytest.raises(KeyError, match="Unknown segmentation preset"):
            get_segmentation_preset("nonexistent")


class TestListPresets:
    """Tests for list_*_presets functions."""

    def test_list_engine_presets_returns_list(self) -> None:
        """Test list_engine_presets returns a list."""
        presets = list_engine_presets()

        assert isinstance(presets, list)
        assert len(presets) > 0

    def test_list_engine_presets_contains_preset_info(self) -> None:
        """Test list contains PresetInfo objects."""
        presets = list_engine_presets()

        for preset in presets:
            assert isinstance(preset, PresetInfo)
            assert preset.name
            assert preset.display_name
            assert preset.config is not None

    def test_list_segmentation_presets_returns_list(self) -> None:
        """Test list_segmentation_presets returns a list."""
        presets = list_segmentation_presets()

        assert isinstance(presets, list)
        assert len(presets) > 0

    def test_list_segmentation_presets_contains_preset_info(self) -> None:
        """Test list contains PresetInfo objects."""
        presets = list_segmentation_presets()

        for preset in presets:
            assert isinstance(preset, PresetInfo)
            assert preset.name
            assert preset.display_name


class TestPresetInfoToDict:
    """Tests for PresetInfo.to_dict method."""

    def test_preset_info_to_dict(self) -> None:
        """Test PresetInfo serialization."""
        preset = ENGINE_PRESETS["balanced"]
        data = preset.to_dict()

        assert data["name"] == "balanced"
        assert "display_name" in data
        assert "description" in data
        # Config is not included in to_dict (only metadata)
        assert "config" not in data


class TestPresetConfigValidity:
    """Tests that preset configs are valid."""

    def test_all_engine_presets_are_valid_configs(self) -> None:
        """Test all engine preset configs pass validation."""
        for name, preset in ENGINE_PRESETS.items():
            config = preset.config
            # If we got here without error, config is valid
            assert config.model_name, f"Preset {name} has no model_name"

    def test_all_segmentation_presets_are_valid_profiles(self) -> None:
        """Test all segmentation preset profiles pass validation."""
        for name, preset in SEGMENTATION_PRESETS.items():
            profile = preset.config
            # Threshold must be valid
            assert 0 < profile.threshold < 1, f"Preset {name} has invalid threshold"
            # Max chunk must be positive
            assert profile.max_chunk_s > 0, f"Preset {name} has invalid max_chunk_s"
