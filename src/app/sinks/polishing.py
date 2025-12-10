"""Polishing sink decorator for transcript post-processing."""
from __future__ import annotations

from vociferous.domain import TranscriptSegment, TranscriptSink, TranscriptionResult
from vociferous.polish.base import Polisher


class PolishingSink(TranscriptSink):
    """Decorator that polishes text before forwarding to inner sink.

    This implements the Decorator pattern to keep polishing as a separate
    concern from core transcription, following the Single Responsibility Principle.
    """

    def __init__(self, inner: TranscriptSink, polisher: Polisher) -> None:
        self._inner = inner
        self._polisher = polisher

    def handle_segment(self, segment: TranscriptSegment) -> None:
        """Forward segments directly to inner sink without polishing."""
        self._inner.handle_segment(segment)

    def complete(self, result: TranscriptionResult) -> None:
        """Polish the final text and forward to inner sink."""
        polished_text = self._polisher.polish(result.text)
        polished_result = result.model_copy(update={"text": polished_text})
        self._inner.complete(polished_result)
