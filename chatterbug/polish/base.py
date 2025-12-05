from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PolisherConfig:
    """Configuration for transcript polishing.

    The polisher should be lightweight and local-first. The config keeps the
    chosen model name and a free-form params mapping for model-specific knobs.
    Empty/whitespace-only params are stripped by consumers.
    """

    model: str | None = None
    enabled: bool = False
    params: dict[str, str] | None = None


class Polisher(Protocol):
    """Interface for transcript polishers.

    Implementations should be inexpensive and ideally fully local. The polisher
    receives the full transcript text and returns a polished string.
    """

    def polish(self, text: str) -> str:  # pragma: no cover - Protocol definition
        ...


class NullPolisher:
    """No-op polisher used when polishing is disabled."""

    def polish(self, text: str) -> str:
        return text


class RuleBasedPolisher:
    """Lightweight heuristic polisher.

    This avoids heavy models and keeps the polishing step fully local. It
    normalizes whitespace, fixes mid-word hyphen splits, and trims stray
    punctuation spacing.
    """

    def __init__(self) -> None:
        self._hyphen_gap_pattern = re.compile(r"(?<=\w)-\s+(?=\w)")

    def polish(self, text: str) -> str:
        cleaned = " ".join(text.split())
        cleaned = self._hyphen_gap_pattern.sub("", cleaned)
        cleaned = cleaned.replace(" ,", ",").replace(" .", ".")
        return cleaned
