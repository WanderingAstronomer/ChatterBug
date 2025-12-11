from __future__ import annotations

import pytest
from pydantic import ValidationError

from vociferous.config.schema import AppConfig, get_engine_profile, get_segmentation_profile


def test_default_profiles_resolve() -> None:
    cfg = AppConfig()

    engine_profile = get_engine_profile(cfg)
    segmentation_profile = get_segmentation_profile(cfg)

    assert engine_profile.kind == "canary_qwen"
    assert segmentation_profile.max_speech_duration_s == pytest.approx(40.0)
    assert segmentation_profile.threshold == pytest.approx(0.5)


def test_invalid_segmentation_threshold_raises() -> None:
    with pytest.raises(ValidationError):
        AppConfig.model_validate({"segmentation_profiles": {"bad": {"threshold": 2.0}}})


def test_missing_default_profile_raises() -> None:
    with pytest.raises(ValidationError):
        AppConfig.model_validate({
            "engine_profiles": {},
            "segmentation_profiles": {"default": {}},
            "default_engine_profile": "does_not_exist",
        })
