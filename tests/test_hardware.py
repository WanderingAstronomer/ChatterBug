"""Tests for hardware heuristics used by engines."""
from types import SimpleNamespace
from typing import Any

from vociferous.engines import hardware


def test_get_optimal_device_prefers_cuda_when_available(monkeypatch: Any) -> None:
    fake_torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True))
    monkeypatch.setattr(hardware, "torch", fake_torch)

    assert hardware.get_optimal_device() == "cuda"


def test_get_optimal_device_defaults_to_cpu_when_missing(monkeypatch: Any) -> None:
    monkeypatch.setattr(hardware, "torch", None)

    assert hardware.get_optimal_device() == "cpu"


def test_get_optimal_compute_type_matches_device() -> None:
    assert hardware.get_optimal_compute_type("cuda") == "float16"
    assert hardware.get_optimal_compute_type("cpu") == "int8"
