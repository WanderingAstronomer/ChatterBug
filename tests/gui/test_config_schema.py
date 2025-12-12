"""Tests for config schema extraction and GUI utilities."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vociferous.domain.model import EngineConfig, SegmentationProfile
from vociferous.gui.config_schema import (
    FIELD_METADATA,
    ConfigFieldSchema,
    get_config_schema,
)
from vociferous.gui.validation import (
    ValidationErrorInfo,
    format_validation_errors,
    validate_config_value,
)


class TestConfigFieldSchema:
    """Tests for ConfigFieldSchema dataclass."""

    def test_schema_to_dict(self) -> None:
        """Test ConfigFieldSchema serialization."""
        schema = ConfigFieldSchema(
            name="threshold",
            field_type="float",
            default=0.5,
            description="VAD sensitivity",
            choices=(),
            help_text="Lower values detect quieter speech.",
            widget_type="slider",
            widget_params={"min": 0.0, "max": 1.0},
        )

        data = schema.to_dict()

        assert data["name"] == "threshold"
        assert data["type"] == "float"
        assert data["default"] == 0.5
        assert data["widget_type"] == "slider"
        assert data["widget_params"]["min"] == 0.0

    def test_schema_frozen(self) -> None:
        """Test that ConfigFieldSchema is immutable."""
        schema = ConfigFieldSchema(
            name="test",
            field_type="str",
            default="default",
        )

        with pytest.raises(AttributeError):
            schema.name = "changed"  # type: ignore[misc]


class TestGetConfigSchema:
    """Tests for get_config_schema function."""

    def test_extract_segmentation_profile_schema(self) -> None:
        """Test schema extraction from SegmentationProfile."""
        schema = get_config_schema(SegmentationProfile)

        # Should have all fields
        field_names = [f.name for f in schema]
        assert "threshold" in field_names
        assert "min_silence_ms" in field_names
        assert "min_speech_ms" in field_names
        assert "max_chunk_s" in field_names

    def test_threshold_field_has_slider_widget(self) -> None:
        """Test that threshold field gets slider widget type."""
        schema = get_config_schema(SegmentationProfile)

        threshold_field = next(f for f in schema if f.name == "threshold")

        assert threshold_field.widget_type == "slider"
        assert threshold_field.widget_params is not None
        assert "min" in threshold_field.widget_params
        assert "max" in threshold_field.widget_params

    def test_extract_engine_config_schema(self) -> None:
        """Test schema extraction from EngineConfig Pydantic model."""
        schema = get_config_schema(EngineConfig)

        field_names = [f.name for f in schema]
        assert "model_name" in field_names
        assert "device" in field_names
        assert "compute_type" in field_names

    def test_device_field_has_dropdown_widget(self) -> None:
        """Test that device field gets dropdown widget type."""
        schema = get_config_schema(EngineConfig)

        device_field = next(f for f in schema if f.name == "device")

        # Device has choices in FIELD_METADATA
        assert device_field.widget_type == "dropdown"
        assert len(device_field.choices) > 0

    def test_field_has_help_text(self) -> None:
        """Test that fields with metadata have help text."""
        schema = get_config_schema(SegmentationProfile)

        threshold_field = next(f for f in schema if f.name == "threshold")

        assert threshold_field.help_text
        assert "speech" in threshold_field.help_text.lower()

    def test_unsupported_type_raises(self) -> None:
        """Test that unsupported types raise TypeError."""

        class NotAConfig:
            pass

        with pytest.raises(TypeError):
            get_config_schema(NotAConfig)


class TestFieldMetadata:
    """Tests for FIELD_METADATA constant."""

    def test_threshold_metadata_exists(self) -> None:
        """Test that threshold has pre-defined metadata."""
        assert "threshold" in FIELD_METADATA
        assert "description" in FIELD_METADATA["threshold"]
        assert "slider" in FIELD_METADATA["threshold"]

    def test_device_metadata_has_choices(self) -> None:
        """Test that device has choice labels."""
        assert "device" in FIELD_METADATA
        assert "choices" in FIELD_METADATA["device"]
        assert "choice_labels" in FIELD_METADATA["device"]

    def test_compute_type_metadata(self) -> None:
        """Test compute_type metadata."""
        assert "compute_type" in FIELD_METADATA
        choices = FIELD_METADATA["compute_type"]["choices"]
        assert "float16" in choices
        assert "bfloat16" in choices


class TestValidationErrorInfo:
    """Tests for ValidationErrorInfo dataclass."""

    def test_error_info_to_dict(self) -> None:
        """Test ValidationErrorInfo serialization."""
        error = ValidationErrorInfo(
            field="compute_type",
            message="Invalid selection",
            input_value="invalid",
            help_text="Choose a valid precision type",
            valid_options=("float16", "float32"),
        )

        data = error.to_dict()

        assert data["field"] == "compute_type"
        assert data["message"] == "Invalid selection"
        assert "float16" in data["valid_options"]


class TestFormatValidationErrors:
    """Tests for format_validation_errors function."""

    def test_format_literal_error(self) -> None:
        """Test formatting of literal type error."""
        try:
            EngineConfig(device="invalid_device")
            pytest.fail("Expected ValidationError")
        except ValidationError as e:
            errors = format_validation_errors(e)

            assert len(errors) > 0
            device_error = errors[0]
            assert device_error.field == "device"
            # Should be user-friendly message
            assert "Invalid" in device_error.message or "invalid" in device_error.message.lower()

    def test_format_preserves_input_value(self) -> None:
        """Test that input value is preserved in error."""
        try:
            EngineConfig(device="not_a_device")
            pytest.fail("Expected ValidationError")
        except ValidationError as e:
            errors = format_validation_errors(e)

            assert errors[0].input_value == "not_a_device"


class TestValidateConfigValue:
    """Tests for validate_config_value function."""

    def test_valid_value_returns_none(self) -> None:
        """Test that valid values return None (no error)."""
        error = validate_config_value("device", "cuda", EngineConfig)
        assert error is None

    def test_invalid_value_returns_error(self) -> None:
        """Test that invalid values return error."""
        error = validate_config_value("device", "invalid", EngineConfig)
        assert error is not None
        assert error.field == "device"

    def test_unknown_field_returns_error(self) -> None:
        """Test that unknown fields return error."""
        error = validate_config_value("nonexistent_field", "value", EngineConfig)
        assert error is not None
        assert "Unknown" in error.message
