from __future__ import annotations

"""Refinement module - dual-pass LLM-based transcript polishing."""

from .base import (
	PROMPT_TEMPLATES,
	Refiner,
	RefinerConfig,
	NullRefiner,
)
from .factory import build_refiner
from .canary_refiner import CanaryRefiner

__all__ = [
	"PROMPT_TEMPLATES",
	"Refiner",
	"RefinerConfig",
	"NullRefiner",
	"build_refiner",
	"CanaryRefiner",
]

