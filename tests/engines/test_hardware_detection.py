"""Real-world hardware detection tests.

Tests the hardware detection module with actual system probing (no mocks).
Validates device detection logic for both CPU and GPU systems.
"""

from __future__ import annotations

from vociferous.engines.hardware import get_optimal_compute_type, get_optimal_device


class TestHardwareDetection:
    """Hardware detection for device and compute type selection."""

    def test_get_optimal_device_returns_string(self) -> None:
        """Device detection returns either 'cuda' or 'cpu'."""
        device = get_optimal_device()
        assert isinstance(device, str)
        assert device in ("cpu", "cuda")

    def test_get_optimal_compute_type_cpu_returns_float32(self) -> None:
        """CPU systems default to float32 for compatibility.
        
        Note: int8 would require quantized models (e.g., faster-whisper),
        but official OpenAI Whisper uses float32 on CPU.
        """
        compute_type = get_optimal_compute_type("cpu")
        assert compute_type == "float32"

    def test_get_optimal_compute_type_cuda_returns_float16(self) -> None:
        """CUDA systems default to float16 for precision."""
        compute_type = get_optimal_compute_type("cuda")
        assert compute_type == "float16"


