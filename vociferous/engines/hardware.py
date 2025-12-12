"""Hardware detection utilities for engine configuration.

Provides functions to detect optimal device (CPU/CUDA) and compute type
for inference, with robust error handling and logging.
"""

from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger(__name__)

DeviceType = Literal["cpu", "cuda"]
ComputeTypeValue = Literal["float32", "float16", "bfloat16", "int8"]


def get_optimal_device() -> DeviceType:
    """Detect optimal device for inference.
    
    Returns 'cuda' if a working CUDA GPU is available, 'cpu' otherwise.
    Logs warnings on CUDA initialization failures to aid debugging.
    
    Returns:
        'cuda' if GPU available, 'cpu' otherwise
    """
    try:
        import torch
        if torch.cuda.is_available():
            # Verify CUDA actually works by getting device properties
            try:
                torch.cuda.get_device_properties(0)
                return "cuda"
            except (RuntimeError, AssertionError) as exc:
                logger.warning(
                    "CUDA device exists but initialization failed: %s. Falling back to CPU.",
                    exc,
                )
                return "cpu"
    except ImportError:
        # PyTorch not installed; CPU-only operation
        logger.debug("PyTorch not installed; using CPU for inference")
    except (OSError, RuntimeError) as exc:
        logger.warning(
            "CUDA detection failed: %s. Falling back to CPU.",
            exc,
        )
    return "cpu"


def get_optimal_compute_type(device: DeviceType) -> ComputeTypeValue:
    """Get optimal compute type for the given device.
    
    For CUDA devices, returns 'float16' for best performance on most GPUs.
    For CPU, returns 'float32' as it's most compatible (int8 requires
    specific model formats and quantization).
    
    Args:
        device: Target device ('cpu' or 'cuda')
        
    Returns:
        Recommended compute type for the device
    """
    if device == "cuda":
        return "float16"
    # CPU: float32 is most compatible; int8 requires quantized models
    return "float32"
