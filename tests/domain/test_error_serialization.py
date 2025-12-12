"""Tests for error serialization (to_dict/from_dict).

These tests verify that VociferousError and its subclasses can be
properly serialized to dictionaries for GUI/API consumption.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from vociferous.domain.exceptions import (
    AudioDecodeError,
    ConfigurationError,
    DependencyError,
    EngineError,
    VociferousError,
)


class TestErrorToDict:
    """Tests for VociferousError.to_dict()."""

    def test_basic_error_serialization(self) -> None:
        """Test basic error serialization."""
        error = VociferousError(
            "Test error",
            context={"file": "/path/test.mp3", "duration": 120.5},
            suggestions=["Try this", "Or this"],
        )
        
        data = error.to_dict()
        
        assert data["error_type"] == "VociferousError"
        assert data["message"] == "Test error"
        assert data["context"]["file"] == "/path/test.mp3"
        assert data["context"]["duration"] == 120.5
        assert len(data["suggestions"]) == 2
        assert data["suggestions"][0] == "Try this"
        assert "timestamp" in data
        assert data["cause"] is None

    def test_error_with_cause(self) -> None:
        """Test error serialization with cause exception."""
        original = ValueError("Original error")
        error = VociferousError("Wrapper error", cause=original)
        
        data = error.to_dict()
        
        assert data["cause"] == "Original error"

    def test_error_timestamp_format(self) -> None:
        """Test timestamp is ISO 8601 format and parseable."""
        error = VociferousError("Test")
        data = error.to_dict()
        
        # Should be parseable as ISO 8601
        timestamp = datetime.fromisoformat(data["timestamp"])
        assert isinstance(timestamp, datetime)

    def test_empty_context_and_suggestions(self) -> None:
        """Test error with no context or suggestions."""
        error = VociferousError("Simple error")
        data = error.to_dict()
        
        assert data["context"] == {}
        assert data["suggestions"] == []


class TestErrorFromDict:
    """Tests for VociferousError.from_dict()."""

    def test_roundtrip_serialization(self) -> None:
        """Test error can be serialized and deserialized."""
        original = VociferousError(
            "Test error",
            context={"key": "value"},
            suggestions=["Suggestion"],
        )
        
        # Serialize then deserialize
        data = original.to_dict()
        restored = VociferousError.from_dict(data)
        
        assert restored.message == original.message
        assert restored.context == original.context
        assert restored.suggestions == original.suggestions

    def test_from_dict_with_missing_fields(self) -> None:
        """Test from_dict handles missing optional fields."""
        data = {"message": "Test only message"}
        
        error = VociferousError.from_dict(data)
        
        assert error.message == "Test only message"
        assert error.context == {}
        assert error.suggestions == []


class TestSubclassSerialization:
    """Tests for subclass serialization."""

    def test_audio_decode_error_serialization(self) -> None:
        """Test AudioDecodeError serialization includes class name."""
        error = AudioDecodeError(
            "Failed to decode audio",
            context={"file": "/path/test.mp3", "exit_code": 1},
            suggestions=["Install ffmpeg"],
        )
        
        data = error.to_dict()
        
        assert data["error_type"] == "AudioDecodeError"
        assert "test.mp3" in data["context"]["file"]

    def test_audio_decode_error_from_ffmpeg(self) -> None:
        """Test AudioDecodeError.from_ffmpeg_error() serialization."""
        error = AudioDecodeError.from_ffmpeg_error(
            audio_path=Path("/path/test.mp3"),
            returncode=1,
            stderr="invalid data found",
        )
        
        data = error.to_dict()
        
        assert data["error_type"] == "AudioDecodeError"
        assert data["context"]["ffmpeg_exit_code"] == 1
        assert len(data["suggestions"]) > 0

    def test_configuration_error_serialization(self) -> None:
        """Test ConfigurationError serialization."""
        error = ConfigurationError.invalid_profile(
            profile_name="nonexistent",
            valid_profiles=["default", "fast"],
        )
        
        data = error.to_dict()
        
        assert data["error_type"] == "ConfigurationError"
        assert data["context"]["requested_profile"] == "nonexistent"

    def test_dependency_error_serialization(self) -> None:
        """Test DependencyError serialization."""
        error = DependencyError.missing_ffmpeg()
        
        data = error.to_dict()
        
        assert data["error_type"] == "DependencyError"
        assert len(data["suggestions"]) > 0
        assert any("ffmpeg" in s.lower() for s in data["suggestions"])

    def test_engine_error_serialization(self) -> None:
        """Test EngineError serialization."""
        error = EngineError(
            "Model failed to load",
            context={"model": "canary_qwen", "device": "cuda"},
            suggestions=["Check CUDA installation"],
        )
        
        data = error.to_dict()
        
        assert data["error_type"] == "EngineError"
        assert data["context"]["model"] == "canary_qwen"


class TestGUIErrorFormatting:
    """Tests for GUI error formatting."""

    def test_format_error_for_dialog(self) -> None:
        """Test error formatting for GUI dialogs."""
        from vociferous.gui.errors import format_error_for_dialog
        
        error = AudioDecodeError(
            "Failed to decode audio file",
            context={"file": "/path/test.mp3", "exit_code": 1},
            suggestions=["Install ffmpeg", "Check file format"],
        )
        
        dialog_data = format_error_for_dialog(error)
        
        assert dialog_data.title == "Audio Decode Error"
        assert dialog_data.message == "Failed to decode audio file"
        assert "File: /path/test.mp3" in dialog_data.details
        assert "Exit Code: 1" in dialog_data.details
        assert "1. Install ffmpeg" in dialog_data.suggestions
        assert "2. Check file format" in dialog_data.suggestions

    def test_format_error_for_dialog_empty_context(self) -> None:
        """Test formatting error with no context."""
        from vociferous.gui.errors import format_error_for_dialog
        
        error = VociferousError("Simple error")
        
        dialog_data = format_error_for_dialog(error)
        
        assert dialog_data.title == "Vociferous Error"
        assert dialog_data.message == "Simple error"
        assert dialog_data.details == ""
        assert dialog_data.suggestions == ""

    def test_dialog_error_data_to_dict(self) -> None:
        """Test DialogErrorData.to_dict()."""
        from vociferous.gui.errors import DialogErrorData
        
        data = DialogErrorData(
            title="Test Error",
            message="Test message",
            details="Some details",
            suggestions="1. Suggestion",
        )
        
        result = data.to_dict()
        
        assert result["title"] == "Test Error"
        assert result["message"] == "Test message"
        assert result["details"] == "Some details"
        assert result["suggestions"] == "1. Suggestion"

    def test_class_name_formatting(self) -> None:
        """Test various class name to title conversions."""
        from vociferous.gui.errors import _format_class_name_as_title
        
        assert _format_class_name_as_title("AudioDecodeError") == "Audio Decode Error"
        assert _format_class_name_as_title("VADError") == "VAD Error"
        assert _format_class_name_as_title("ConfigurationError") == "Configuration Error"
        assert _format_class_name_as_title("VociferousError") == "Vociferous Error"


class TestErrorSchema:
    """Tests for ErrorDict TypedDict."""

    def test_error_dict_structure(self) -> None:
        """Test that to_dict() returns structure matching ErrorDict."""
        from vociferous.domain.error_schema import ErrorDict
        
        error = VociferousError(
            "Test error",
            context={"key": "value"},
            suggestions=["Suggestion"],
        )
        
        data = error.to_dict()
        
        # Verify all ErrorDict keys are present
        assert "error_type" in data
        assert "message" in data
        assert "context" in data
        assert "suggestions" in data
        assert "timestamp" in data
        assert "cause" in data
        
        # Verify types
        assert isinstance(data["error_type"], str)
        assert isinstance(data["message"], str)
        assert isinstance(data["context"], dict)
        assert isinstance(data["suggestions"], list)
        assert isinstance(data["timestamp"], str)
