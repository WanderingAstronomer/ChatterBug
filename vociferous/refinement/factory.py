"""Refinement engine factory.

Provides a factory function for constructing refiner instances based on
configuration. Refiners improve transcript quality through grammar and
punctuation correction using LLM-based text processing.
"""

from __future__ import annotations

import logging

from vociferous.refinement.base import (
    NullRefiner,
    Refiner,
    RefinerConfig,
)

logger = logging.getLogger(__name__)


def build_refiner(config: RefinerConfig | None = None) -> Refiner:
    """Construct a refiner from configuration.
    
    Returns NullRefiner (pass-through) if refinement is disabled or config
    is not provided. Otherwise returns CanaryRefiner for LLM-based text
    polishing.
    
    The CanaryRefiner uses the same Canary-Qwen model as the ASR engine,
    leveraging its LLM mode for grammar and punctuation correction without
    additional model loading overhead.
    
    Args:
        config: Refiner configuration with enabled flag and optional params.
                If None or config.enabled is False, returns NullRefiner.
        
    Returns:
        Refiner instance:
        - NullRefiner: Pass-through (no refinement applied)
        - CanaryRefiner: LLM-based refinement via Canary-Qwen
        
    Example:
        >>> config = RefinerConfig(enabled=True)
        >>> refiner = build_refiner(config)
        >>> refined = refiner.refine("raw transcr ipt text")
    """
    if config is None or not config.enabled:
        logger.debug("Refinement disabled; using NullRefiner")
        return NullRefiner()
    
    # Import here to avoid circular dependency and defer heavy import
    from vociferous.refinement.canary_refiner import CanaryRefiner
    
    logger.debug("Building CanaryRefiner for LLM-based refinement")
    return CanaryRefiner()

