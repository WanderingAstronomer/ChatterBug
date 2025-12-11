"""CanaryRefiner - Text refinement using Canary-Qwen LLM.

Uses the Canary-Qwen engine's dual-mode refinement capability to polish
transcripts with grammar, punctuation, and fluency fixes.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from vociferous.domain.exceptions import DependencyError
from vociferous.domain.model import EngineConfig, TranscriptSegment
from vociferous.refinement.base import PROMPT_TEMPLATES, Refiner

if TYPE_CHECKING:
    from vociferous.engines.canary_qwen import CanaryQwenEngine


class CanaryRefiner(Refiner):
    """Refiner backed by Canary-Qwen LLM refinement mode.
    
    Delegates to the Canary-Qwen engine's refine_text() method for
    lightweight, local LLM-based text polishing.
    """

    def __init__(self) -> None:
        """Initialize Canary-Qwen refiner (lazy-loads engine)."""
        self._engine: CanaryQwenEngine | None = None

    def refine(self, text: str, instructions: str | None = None) -> str:
        """Refine text using Canary-Qwen.
        
        Args:
            text: Raw transcript to refine
            instructions: Optional custom refinement instructions
            
        Returns:
            Polished transcript with grammar/punctuation fixes
        """
        if self._engine is None:
            self._engine = self._lazy_load_engine()
        
        # At this point engine is guaranteed to be non-None
        engine = self._engine
        assert engine is not None  # Type narrowing for MyPy
        return engine.refine_text(text, instructions)

    def refine_segments(
        self,
        segments: list[TranscriptSegment],
        mode: str | None = None,
        instructions: str | None = None,
    ) -> list[TranscriptSegment]:
        """Refine segments, preserving timestamps and alignment.
        
        Args:
            segments: List of TranscriptSegment with raw_text
            mode: Named refinement mode (grammar_only, summary, bullet_points)
            instructions: Custom instructions override
            
        Returns:
            Same segments with refined_text filled in
        """
        if not segments:
            return segments

        # Resolve prompt from mode or use custom instructions
        prompt = instructions
        if prompt is None and mode in PROMPT_TEMPLATES:
            prompt = PROMPT_TEMPLATES[mode]

        # Join raw text from all segments
        combined_text = " ".join(seg.raw_text.strip() for seg in segments if seg.raw_text.strip())
        
        if not combined_text:
            return segments

        # Refine entire transcript as one pass
        refined_text = self.refine(combined_text, prompt)

        # For simplicity, assign refined text to all segments proportionally
        # More sophisticated approaches could split by sentence boundaries
        if len(segments) == 1:
            return [replace(segments[0], refined_text=refined_text)]

        # Multi-segment: distribute refined text (preserve structure)
        # Simple strategy: assign refined text to first segment, others keep raw
        result = [replace(segments[0], refined_text=refined_text)]
        for seg in segments[1:]:
            result.append(replace(seg, refined_text=seg.raw_text))
        
        return result

    def _lazy_load_engine(self) -> CanaryQwenEngine:
        """Lazy-load Canary-Qwen engine on first refinement call."""
        try:
            from vociferous.engines.canary_qwen import CanaryQwenEngine
        except ImportError as exc:
            raise DependencyError(
                "Canary-Qwen engine not available; ensure transformers and torch are installed."
            ) from exc

        config = EngineConfig(model_name="nvidia/canary-qwen-2.5b")
        return CanaryQwenEngine(config)
