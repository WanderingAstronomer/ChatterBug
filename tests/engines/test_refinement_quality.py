"""Tests for refinement output quality.

These tests ensure that the refinement extraction produces clean output
without Qwen's <think> blocks or other artifacts.
"""

import os
import re

import pytest


class TestRefinementExtraction:
    """Tests for the _extract_assistant_response method."""

    @pytest.fixture
    def engine_class(self):
        """Get the CanaryQwenEngine class for testing extraction methods."""
        from vociferous.engines.canary_qwen import CanaryQwenEngine
        return CanaryQwenEngine

    def test_extracts_clean_response_from_assistant_marker(self, engine_class):
        """Should extract text after <|im_start|>assistant marker."""
        raw_output = (
            "<|im_start|>user\nSome prompt<|im_end|>\n"
            "<|im_start|>assistant\nThis is the clean response.<|im_end|>"
        )
        
        # Create a minimal mock engine to call the method
        result = engine_class._extract_assistant_response(None, raw_output, "original")
        
        assert result == "This is the clean response."
        assert "<|im_start|>" not in result
        assert "<|im_end|>" not in result

    def test_removes_think_blocks_completely(self, engine_class):
        """Should remove ALL <think>...</think> blocks from output."""
        raw_output = (
            "<|im_start|>assistant\n"
            "<think>Let me analyze this...</think>"
            "This is the actual answer."
            "<|im_end|>"
        )
        
        result = engine_class._extract_assistant_response(None, raw_output, "original")
        
        assert result == "This is the actual answer."
        assert "<think>" not in result.lower()
        assert "</think>" not in result.lower()

    def test_removes_multiple_think_blocks(self, engine_class):
        """Should remove multiple thinking blocks scattered in output."""
        raw_output = (
            "<|im_start|>assistant\n"
            "<think>First thought</think>"
            "Part one. "
            "<think>Second thought</think>"
            "Part two."
            "<|im_end|>"
        )
        
        result = engine_class._extract_assistant_response(None, raw_output, "original")
        
        assert result == "Part one. Part two."
        assert "<think>" not in result.lower()

    def test_handles_incomplete_think_block(self, engine_class):
        """Should fallback when <think> exists without closing tag."""
        raw_output = (
            "<|im_start|>assistant\n"
            "Some valid text before thinking. "
            "<think>I started thinking but never finished..."
        )
        
        result = engine_class._extract_assistant_response(None, raw_output, "original fallback")
        
        # Should return text before <think> or fallback
        assert "<think>" not in result.lower()
        # Either returns text before <think> or original
        assert result in ["Some valid text before thinking.", "original fallback"]

    def test_removes_common_preambles(self, engine_class):
        """Should remove 'Here is the corrected text:' and similar preambles."""
        raw_output = (
            "<|im_start|>assistant\n"
            "Here is the corrected text:\n"
            "This is the actual refined transcript."
            "<|im_end|>"
        )
        
        result = engine_class._extract_assistant_response(None, raw_output, "original")
        
        assert result == "This is the actual refined transcript."
        assert "here is the" not in result.lower()

    def test_removes_edited_text_label(self, engine_class):
        """Should remove 'Edited text:' prefix."""
        raw_output = (
            "<|im_start|>assistant\n"
            "Edited text: This is the cleaned up version."
            "<|im_end|>"
        )
        
        result = engine_class._extract_assistant_response(None, raw_output, "original")
        
        assert result == "This is the cleaned up version."
        assert "edited text:" not in result.lower()


class TestRefinementValidation:
    """Tests for the _validate_refinement method."""

    @pytest.fixture
    def engine_class(self):
        """Get the CanaryQwenEngine class for testing validation methods."""
        from vociferous.engines.canary_qwen import CanaryQwenEngine
        return CanaryQwenEngine

    def test_returns_original_when_refined_is_empty(self, engine_class):
        """Should return original text if refined is empty."""
        original = "This is the original text."
        
        result = engine_class._validate_refinement(None, original, "")
        
        assert result == original

    def test_returns_original_when_refined_too_short(self, engine_class):
        """Should return original if refined is less than expected ratio of original length."""
        original = "This is a reasonably long original transcript that should not be shortened drastically."
        refined = "Short."  # Way too short (< 20% of original for long inputs)
        
        result = engine_class._validate_refinement(None, original, refined)
        
        assert result == original

    def test_returns_original_when_refined_too_long(self, engine_class):
        """Should return original if refined is over expected ratio of original length."""
        original = "Short original text."
        # This needs to be over 3x the original length for short inputs (< 50 chars)
        refined = "This is an extremely extremely extremely extremely long refined output that contains way way too much content and is clearly the result of the model hallucinating or including explanations and other garbage that should absolutely not be in the output."
        
        result = engine_class._validate_refinement(None, original, refined)
        
        assert result == original

    def test_returns_original_when_contains_think_tags(self, engine_class):
        """Should return original if refined still contains <think> tags."""
        original = "Original text here."
        refined = "Refined text with <think> leftover artifact."
        
        result = engine_class._validate_refinement(None, original, refined)
        
        assert result == original

    def test_returns_original_when_contains_explanations(self, engine_class):
        """Should return original if refined contains 'Here is the corrected...'."""
        original = "Original text here."
        refined = "Here is the corrected version of the text. The refined output follows."
        
        result = engine_class._validate_refinement(None, original, refined)
        
        assert result == original

    def test_returns_original_when_contains_prompt_leakage(self, engine_class):
        """Should return original if refined contains prompt fragments."""
        original = "Original text here."
        refined = "Refine the following transcript by correcting grammar..."
        
        result = engine_class._validate_refinement(None, original, refined)
        
        assert result == original

    def test_accepts_valid_refined_output(self, engine_class):
        """Should accept valid refined output that passes all checks."""
        original = "this is a test input without proper punctuation"
        refined = "This is a test input without proper punctuation."
        
        result = engine_class._validate_refinement(None, original, refined)
        
        assert result == refined


class TestRefinementQualityPatterns:
    """Integration tests for expected refinement patterns.
    
    These tests require a GPU and the full Canary-Qwen model loaded.
    They are marked as slow and will be skipped in normal test runs.
    """

    @pytest.mark.slow
    @pytest.mark.skipif(
        not os.environ.get("RUN_SLOW_TESTS"),
        reason="Slow test - requires GPU and model loading. Set RUN_SLOW_TESTS=1 to run."
    )
    @pytest.mark.parametrize("input_text,expected_pattern", [
        # Basic punctuation should be preserved/added
        ("this is a test", r"[Tt]his is a test\.?"),
        # Common patterns should not include artifacts
        ("hello world", r"^[Hh]ello [Ww]orld\.?$"),
    ])
    def test_refinement_output_matches_pattern(self, input_text, expected_pattern):
        """Refined output should match expected pattern (when engine available)."""
        # This test is marked as skippable if engine not available
        pytest.importorskip("nemo.collections.speechlm2.models")
        
        from vociferous.domain.model import EngineConfig
        from vociferous.engines.canary_qwen import CanaryQwenEngine
        
        # Use fp16 which is in the allowed list
        config = EngineConfig(device="cuda", compute_type="fp16")
        engine = CanaryQwenEngine(config)
        
        refined = engine.refine_text(input_text)
        
        assert re.search(expected_pattern, refined), f"'{refined}' does not match '{expected_pattern}'"
        # Ensure no artifacts
        assert "<think>" not in refined.lower()
        assert "here is" not in refined.lower()
        assert "edited text:" not in refined.lower()
