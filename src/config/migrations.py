from __future__ import annotations

"""Configuration migrations kept separate from schema validation."""

import logging
from typing import Mapping

from vociferous.domain.model import DEFAULT_WHISPER_MODEL

logger = logging.getLogger(__name__)


def migrate_raw_config(data: Mapping[str, object]) -> dict[str, object]:
    """Apply backward-compatible migrations to raw config dicts."""
    migrated = dict(data)
    engine = migrated.get("engine")

    if engine == "parakeet_rnnt":
        logger.warning(
            "⚠ Parakeet engine removed; migrated to whisper_turbo with large-v3-turbo "
            "(comparable accuracy). Update ~/.config/vociferous/config.toml."
        )
        migrated["engine"] = "whisper_turbo"
        if "model_name" not in migrated or migrated["model_name"] == DEFAULT_WHISPER_MODEL:
            migrated["model_name"] = "openai/whisper-large-v3-turbo"

    elif engine == "whisper_vllm":
        logger.warning(
            "⚠ vLLM engines removed; migrated to whisper_turbo (local). "
            "Update config to keep running without a server."
        )
        migrated["engine"] = "whisper_turbo"
        if "model_name" not in migrated:
            migrated["model_name"] = DEFAULT_WHISPER_MODEL

    elif engine == "voxtral_vllm":
        logger.warning(
            "⚠ vLLM engines removed; migrated to voxtral_local (offline). "
            "Update config to keep running without a server."
        )
        migrated["engine"] = "voxtral_local"
        if "model_name" not in migrated:
            migrated["model_name"] = "mistralai/Voxtral-Mini-3B-2507"

    elif engine == "voxtral":
        logger.warning(
            "⚠ Engine 'voxtral' renamed to 'voxtral_local'. "
            "Update config; existing behavior unchanged."
        )
        migrated["engine"] = "voxtral_local"

    return migrated
