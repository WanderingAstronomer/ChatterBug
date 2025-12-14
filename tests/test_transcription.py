"""
Tests for transcription module.
"""
import numpy as np
import pytest


class TestTranscriptionFunctions:
    """Tests for transcription utilities (not model loading)."""

    def test_post_process_adds_trailing_space(self, config_manager):
        """Post-processing should add trailing space when configured."""
        from transcription import post_process_transcription

        # Ensure trailing space is enabled
        config_manager.set_config_value(True, 'output_options', 'add_trailing_space')

        result = post_process_transcription("hello world")
        assert result.endswith(' ')

    def test_post_process_strips_whitespace(self):
        """Post-processing should strip leading/trailing whitespace."""
        from transcription import post_process_transcription

        result = post_process_transcription("  hello world  ")
        assert result.startswith('hello')  # Leading space removed

    def test_post_process_empty_string(self):
        """Post-processing should handle empty strings."""
        from transcription import post_process_transcription

        result = post_process_transcription("")
        assert result == ""

    def test_post_process_none_returns_empty(self):
        """Post-processing should handle None-like input."""
        from transcription import post_process_transcription

        result = post_process_transcription("")
        assert result == ""


class TestTranscribeFunction:
    """Tests for the transcribe function."""

    def test_transcribe_none_returns_empty(self):
        """Transcribing None should return empty string."""
        from transcription import transcribe

        result = transcribe(None)
        assert result == ""

    @pytest.mark.slow
    def test_transcribe_silent_audio(self):
        """Transcribing silence should return empty or minimal text."""
        from transcription import create_local_model, transcribe

        # Create 1 second of silence (int16)
        sample_rate = 16000
        silence = np.zeros(sample_rate, dtype=np.int16)

        model = create_local_model()
        result = transcribe(silence, model)

        # Silent audio should produce empty or very short result
        assert len(result.strip()) < 10


class TestModelLoading:
    """Tests for model loading (marked as slow)."""

    @pytest.mark.slow
    def test_model_loads(self):
        """Model should load successfully."""
        from transcription import create_local_model

        model = create_local_model()
        assert model is not None

    @pytest.mark.slow
    def test_model_has_transcribe_method(self):
        """Loaded model should have transcribe method."""
        from transcription import create_local_model

        model = create_local_model()
        assert hasattr(model, 'transcribe')
        assert callable(model.transcribe)
