from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal, Protocol

from vociferous.domain.model import TranscriptSegment

RefinementMode = Literal["grammar_only", "summary", "bullet_points"]

PROMPT_TEMPLATES: dict[str, str] = {
    "grammar_only": (
        "Refine the following transcript by:\n"
        "1. Correcting grammar and punctuation\n"
        "2. Fixing capitalization\n"
        "3. Removing filler words and false starts\n"
        "4. Improving fluency while preserving meaning\n"
        "5. Maintaining the speaker's intent\n\n"
        "Do not add or remove information. Only improve clarity and correctness."
    ),
    "summary": (
        "Summarize the following transcript concisely while preserving key points and main ideas. "
        "Focus on clarity and brevity."
    ),
    "bullet_points": (
        "Convert the following transcript into concise bullet points. "
        "Extract key information and organize it in a clear, structured format."
    ),
}


@dataclass(frozen=True)
class RefinerConfig:
    """Configuration for transcript refinement.

    The refiner uses Canary-Qwen LLM for lightweight, local-first polishing.
    Refinement can be toggled on/off via the enabled flag.
    """

    enabled: bool = False
    params: dict[str, str] = field(default_factory=dict)


class Refiner(Protocol):
    """Interface for transcript refiners.

    Implementations should be local and lightweight. The refiner receives
    the full transcript text and returns an improved string.
    """

    def refine(self, text: str, instructions: str | None = None) -> str:  # pragma: no cover - Protocol definition
        ...

    def refine_segments(
        self,
        segments: list[TranscriptSegment],
        mode: str | None = None,
        instructions: str | None = None,
    ) -> list[TranscriptSegment]:  # pragma: no cover - Protocol definition
        """Refine segments, filling refined_text while preserving alignment."""
        ...


class NullRefiner:
    """No-op refiner used when refinement is disabled."""

    def refine(self, text: str, instructions: str | None = None) -> str:
        return text

    def refine_segments(
        self,
        segments: list[TranscriptSegment],
        mode: str | None = None,
        instructions: str | None = None,
    ) -> list[TranscriptSegment]:
        """Pass-through: no refinement applied."""
        return segments

