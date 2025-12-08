"""Centralized cache management for model files.

This module ensures consistent caching behavior across all engines:
- Single source of truth for cache location
- Prevents duplicate downloads
- Configures Hugging Face Hub to use our cache directory
- Avoids disk space duplication via symlinks
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator
from contextlib import contextmanager

from vociferous.domain.model import DEFAULT_MODEL_CACHE_DIR


def get_cache_root() -> Path:
    """Get the root directory for all model caches.
    
    Returns the configured cache directory, creating it if necessary.
    """
    cache_root = Path(os.environ.get("VOCIFEROUS_CACHE_DIR", DEFAULT_MODEL_CACHE_DIR)).expanduser()
    cache_root.mkdir(parents=True, exist_ok=True)
    return cache_root


@contextmanager
def configure_hf_cache(cache_dir: Path | None = None) -> Generator[Path, None, None]:
    """Context manager to temporarily configure Hugging Face cache location.
    
    This prevents models from being downloaded to both ~/.cache/huggingface/hub
    and ~/.cache/vociferous/models, eliminating disk space duplication.
    
    Args:
        cache_dir: Directory to use for HF cache. If None, uses get_cache_root().
    
    Yields:
        The configured cache directory path.
    
    Example:
        with configure_hf_cache() as cache:
            model = AutoModel.from_pretrained("model-name", cache_dir=str(cache))
    """
    if cache_dir is None:
        cache_dir = get_cache_root()
    
    # Save original environment variables
    original_hf_home = os.environ.get("HF_HOME")
    original_hf_hub_cache = os.environ.get("HF_HUB_CACHE")
    original_transformers_cache = os.environ.get("TRANSFORMERS_CACHE")
    
    try:
        # Set all HF-related cache environment variables to our cache directory
        os.environ["HF_HOME"] = str(cache_dir)
        os.environ["HF_HUB_CACHE"] = str(cache_dir / "hub")
        os.environ["TRANSFORMERS_CACHE"] = str(cache_dir / "hub")
        
        yield cache_dir
    finally:
        # Restore original environment variables
        if original_hf_home is not None:
            os.environ["HF_HOME"] = original_hf_home
        else:
            os.environ.pop("HF_HOME", None)
        
        if original_hf_hub_cache is not None:
            os.environ["HF_HUB_CACHE"] = original_hf_hub_cache
        else:
            os.environ.pop("HF_HUB_CACHE", None)
        
        if original_transformers_cache is not None:
            os.environ["TRANSFORMERS_CACHE"] = original_transformers_cache
        else:
            os.environ.pop("TRANSFORMERS_CACHE", None)


def ensure_model_cached(
    model_path: Path,
    repo_id: str,
    filename: str,
    skip_download: bool = False,
) -> Path:
    """Ensure a model file exists in cache, downloading if necessary.
    
    Args:
        model_path: Expected path to the cached model file
        repo_id: Hugging Face repository ID (e.g., "Qwen/Qwen2.5-1.5B-Instruct-GGUF")
        filename: Filename within the repository
        skip_download: If True, raise error instead of downloading
    
    Returns:
        Path to the cached model file
    
    Raises:
        ValueError: If skip_download=True and file not found
        RuntimeError: If huggingface_hub is not installed or download fails
    """
    # Check if file exists AND has non-zero size (catches incomplete downloads)
    if model_path.exists() and model_path.stat().st_size > 0:
        return model_path
    
    if skip_download:
        raise ValueError(f"Model not found at {model_path}")
    
    try:
        import warnings
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub is required to download models; pip install vociferous[engine] or vociferous[polish]"
        ) from exc
    
    # Ensure parent directory exists
    model_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Download with our cache configuration
    with configure_hf_cache(model_path.parent.parent):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="huggingface_hub")
            downloaded_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=str(model_path.parent),
                local_dir_use_symlinks=False,
            )
    
    # Verify the download succeeded
    if not Path(downloaded_path).exists():
        raise RuntimeError(f"Download succeeded but file not found at {downloaded_path}")
    
    return Path(downloaded_path)
