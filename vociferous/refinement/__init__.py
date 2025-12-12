"""Refinement module - dual-pass LLM-based transcript polishing."""

from __future__ import annotations

from .base import (
    PROMPT_TEMPLATES,
    NullRefiner,
    Refiner,
    RefinerConfig,
)
from .canary_refiner import CanaryRefiner
from .factory import build_refiner

__all__ = [
    "PROMPT_TEMPLATES",
    "CanaryRefiner",
    "NullRefiner",
    "Refiner",
    "RefinerConfig",
    "build_refiner",
]
