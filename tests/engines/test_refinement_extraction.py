"""Tests for Canary-Qwen refinement output extraction.

These tests verify that the _extract_assistant_response method correctly
parses Qwen's chat template format and handles edge cases like incomplete
thinking mode output.
"""

from __future__ import annotations

import pytest


class TestRefinementExtraction:
    """Test the _extract_assistant_response helper method."""

    @pytest.fixture
    def mock_engine(self):
        """Create a minimal engine instance for testing extraction."""
        from vociferous.engines.canary_qwen import CanaryQwenEngine
        # Create instance without full initialization
        engine = object.__new__(CanaryQwenEngine)
        return engine

    def test_full_chat_template_with_think_tags(self, mock_engine):
        """Verify extraction works with full chat template and think tags."""
        raw = """<|im_start|>user
Refine the following transcript by:
1. Correcting grammar and punctuation

test input here
<|im_end|>
<|im_start|>assistant
<think>
Okay, let me analyze this...
</think>
This is the refined output with proper punctuation.
<|im_end|>"""

        result = mock_engine._extract_assistant_response(raw, "original")
        
        assert "Refine the following" not in result, "Prompt leaked into output"
        assert "<think>" not in result, "Think tag leaked into output"
        assert "</think>" not in result, "Think close tag leaked"
        assert "<|im_start|>" not in result, "Chat marker leaked"
        assert result == "This is the refined output with proper punctuation."

    def test_incomplete_think_mode_fallback(self, mock_engine):
        """When model gets stuck in thinking with only think content, fallback to original."""
        # This input has ONLY think content with no useful text before or after
        raw = """<|im_start|>user
Refine the following...
<|im_end|>
<|im_start|>assistant
<think>
thinking"""

        original = "Today is Monday december 8th 2025..."
        result = mock_engine._extract_assistant_response(raw, original)
        
        # Should return the original text as fallback (think content is too short)
        assert result == original, f"Should fallback to original, got: {result}"

    def test_incomplete_think_with_salvageable_content(self, mock_engine):
        """When think block has a newline with useful content, salvage it."""
        raw = """<|im_start|>assistant
<think>
Okay, let me analyze this transcript. The user wants me to fix grammar.

This is the actual refined output that I should return."""

        original = "original text"
        result = mock_engine._extract_assistant_response(raw, original)
        
        # Should salvage the content after the newline in the think block
        assert "actual refined output" in result.lower(), f"Should salvage content, got: {result}"

    def test_clean_output_no_markers(self, mock_engine):
        """Clean text without any markers passes through unchanged."""
        raw = "Just clean text with proper punctuation."
        result = mock_engine._extract_assistant_response(raw, "original")
        
        assert result == "Just clean text with proper punctuation."

    def test_content_before_incomplete_think(self, mock_engine):
        """If there's valid content before <think>, use that."""
        raw = """<|im_start|>assistant
Today is Monday, December 8th, 2025.
<think>
Let me also fix the rest..."""

        result = mock_engine._extract_assistant_response(raw, "original")
        
        assert "December 8th" in result, "Should keep pre-think content"
        assert "<think>" not in result, "Think tag leaked"

    def test_assistant_label_on_newline(self, mock_engine):
        """Handle case where 'assistant' is on its own line (after marker strip)."""
        raw = """<|im_start|>assistant
Today is Monday, December 8th, 2025 at 8 PM.
<|im_end|>"""

        result = mock_engine._extract_assistant_response(raw, "original")
        
        assert "Today is Monday" in result
        assert "<|im_start|>" not in result
        assert "<|im_end|>" not in result

    def test_empty_original_with_failed_extraction(self, mock_engine):
        """When extraction fails and original is empty, return empty string."""
        # This input has only a short think content that can't be salvaged
        raw = """<|im_start|>assistant
<think>
short"""

        result = mock_engine._extract_assistant_response(raw, "")
        
        # Should return empty string as fallback (content too short to salvage)
        assert result == ""

    def test_empty_original_with_salvageable_think_content(self, mock_engine):
        """When original is empty but think has useful content, salvage it."""
        raw = """<|im_start|>assistant
<think>
Let me think...

Actually this is the refined text I should output."""

        result = mock_engine._extract_assistant_response(raw, "")
        
        # Should salvage the longer content after newline
        assert "refined text" in result.lower()

    def test_multiple_think_blocks(self, mock_engine):
        """Handle output with multiple think blocks - all should be removed."""
        raw = """<|im_start|>assistant
<think>First thought</think>
Intermediate text.
<think>Second thought</think>
Final refined output here.
<|im_end|>"""

        result = mock_engine._extract_assistant_response(raw, "original")
        
        # All think blocks should be removed, leaving both text parts
        assert "Intermediate text." in result
        assert "Final refined output here." in result
        assert "<think>" not in result
        assert "</think>" not in result

    def test_endoftext_marker_removed(self, mock_engine):
        """The <|endoftext|> marker should be stripped."""
        raw = "This is the refined text with proper grammar and punctuation.<|endoftext|>"
        result = mock_engine._extract_assistant_response(raw, "original")
        
        assert result == "This is the refined text with proper grammar and punctuation."
        assert "<|endoftext|>" not in result

    def test_prompt_leakage_detection(self, mock_engine):
        """Prompt leakage is detected by _validate_refinement, not extraction."""
        raw = """Refine the following transcript by:
1. Correcting grammar and punctuation

This should not happen."""

        original = "Clean original text"
        # Extraction returns the text as-is (no chat markers to strip)
        extracted = mock_engine._extract_assistant_response(raw, original)
        
        # Validation should catch the prompt leakage and return original
        result = mock_engine._validate_refinement(original, extracted)
        assert result == original, f"Should detect prompt leakage, got: {result}"

    def test_short_output_validation(self, mock_engine):
        """Very short output triggers fallback via _validate_refinement."""
        raw = "<|im_start|>assistant\nOK\n<|im_end|>"
        original = "This is the original transcript with more content."
        
        # Extraction just extracts
        extracted = mock_engine._extract_assistant_response(raw, original)
        
        # Validation catches short output
        result = mock_engine._validate_refinement(original, extracted)
        
        # "OK" is too short, should fallback
        assert result == original
