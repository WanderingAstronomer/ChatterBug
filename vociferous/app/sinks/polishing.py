"""Refining sink decorator for transcript post-processing."""
from __future__ import annotations

from vociferous.domain import TranscriptionResult, TranscriptSegment, TranscriptSink
from vociferous.refinement.base import Refiner


class RefiningSink(TranscriptSink):
    """Decorator that refines text before forwarding to inner sink.

    This implements the Decorator pattern to keep polishing as a separate
    concern from core transcription, following the Single Responsibility Principle.
    """

    def __init__(self, inner: TranscriptSink, refiner: Refiner) -> None:
        self._inner = inner
        self._refiner = refiner

    def handle_segment(self, segment: TranscriptSegment) -> None:
        """Forward segments directly to inner sink without polishing."""
        self._inner.handle_segment(segment)

    def complete(self, result: TranscriptionResult) -> None:
        """Refine the final text and forward to inner sink."""
        refined_text = self._refiner.refine(result.text, None)
        refined_result = result.model_copy(update={"text": refined_text})
        self._inner.complete(refined_result)

