from __future__ import annotations

from pathlib import Path
from typing import Mapping

from vociferous.engines.cache_manager import get_cache_root, ensure_model_cached
from vociferous.polish.base import NullPolisher, Polisher, PolisherConfig, RuleBasedPolisher
from vociferous.polish.llama_cpp_polisher import LlamaCppPolisher, LlamaPolisherOptions

DEFAULT_POLISH_MODEL = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
DEFAULT_POLISH_REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
DEFAULT_POLISH_CACHE = get_cache_root() / "polish"


def build_polisher(config: PolisherConfig | None) -> Polisher:
    """Construct a polisher from config.

    The default is a no-op polisher to keep behavior unchanged unless the user
    opts in. A lightweight rule-based polisher is provided as a local-first
    baseline when enabled without a model.
    """

    if config is None or not config.enabled:
        return NullPolisher()

    model = config.model.strip() if config.model else None
    params: Mapping[str, str] | None = config.params
    if params is not None:
        params = {k: v for k, v in params.items() if v.strip()}

    if model is None:
        model = DEFAULT_POLISH_MODEL

    model_lower = model.lower()
    if model_lower in {"rule", "rule_based", "heuristic"}:
        return RuleBasedPolisher()

    if model_lower.endswith(".gguf"):
        return _build_llama_polisher(model, params)

    raise ValueError(f"Unknown polisher model '{model}'")


def _build_llama_polisher(model_name: str, params: Mapping[str, str] | None) -> Polisher:
    parsed_params = params or {}
    model_dir = Path(parsed_params.get("model_dir", DEFAULT_POLISH_CACHE))
    model_path_override = parsed_params.get("model_path")
    max_tokens = int(parsed_params.get("max_tokens", "128") or 128)
    temperature = float(parsed_params.get("temperature", "0.2") or 0.2)
    gpu_layers = int(parsed_params.get("gpu_layers", "0") or 0)
    ctx_len = int(parsed_params.get("context_length", "2048") or 2048)
    skip_download = parsed_params.get("skip_download", "false").lower() == "true"
    repo_id = parsed_params.get("repo_id", DEFAULT_POLISH_REPO)

    if model_path_override:
        path = Path(model_path_override)
        # For overridden paths, just verify existence
        if not path.exists():
            raise ValueError(f"Custom polisher model not found at {path}")
    else:
        path = model_dir / model_name
        # Use centralized cache manager to handle download/caching
        path = ensure_model_cached(
            model_path=path,
            repo_id=repo_id,
            filename=model_name,
            skip_download=skip_download,
        )

    options = LlamaPolisherOptions(
        model_path=path,
        max_tokens=max_tokens,
        temperature=temperature,
        gpu_layers=gpu_layers,
        context_length=ctx_len,
    )
    return LlamaCppPolisher(options)
