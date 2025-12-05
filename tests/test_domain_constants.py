"""Unit tests for domain constants (TDD)."""
from __future__ import annotations

import pytest

from chatterbug.domain.constants import Device, ComputeType


def test_device_enum_values():
    """Test that Device enum has expected values."""
    assert Device.CPU.value == "cpu"
    assert Device.CUDA.value == "cuda"
    assert Device.AUTO.value == "auto"


def test_device_enum_membership():
    """Test Device enum membership checks."""
    assert "cpu" in [d.value for d in Device]
    assert "cuda" in [d.value for d in Device]
    assert "auto" in [d.value for d in Device]
    assert "invalid" not in [d.value for d in Device]


def test_device_enum_iteration():
    """Test that Device enum can be iterated."""
    devices = list(Device)
    
    assert len(devices) == 3
    assert Device.CPU in devices
    assert Device.CUDA in devices
    assert Device.AUTO in devices


def test_device_enum_from_string():
    """Test creating Device enum from string value."""
    assert Device("cpu") == Device.CPU
    assert Device("cuda") == Device.CUDA
    assert Device("auto") == Device.AUTO


def test_device_enum_invalid_value():
    """Test that invalid Device value raises ValueError."""
    with pytest.raises(ValueError):
        Device("invalid")


def test_compute_type_enum_values():
    """Test that ComputeType enum has expected values."""
    assert ComputeType.INT8.value == "int8"
    assert ComputeType.INT8_FLOAT16.value == "int8_float16"
    assert ComputeType.FLOAT16.value == "float16"
    assert ComputeType.FLOAT32.value == "float32"
    assert ComputeType.FP16.value == "fp16"
    assert ComputeType.FP32.value == "fp32"


def test_compute_type_enum_membership():
    """Test ComputeType enum membership checks."""
    valid_types = [ct.value for ct in ComputeType]
    
    assert "int8" in valid_types
    assert "int8_float16" in valid_types
    assert "float16" in valid_types
    assert "float32" in valid_types
    assert "fp16" in valid_types
    assert "fp32" in valid_types
    assert "invalid" not in valid_types


def test_compute_type_enum_iteration():
    """Test that ComputeType enum can be iterated."""
    types = list(ComputeType)
    
    assert len(types) == 6
    assert ComputeType.INT8 in types
    assert ComputeType.FLOAT16 in types


def test_compute_type_enum_from_string():
    """Test creating ComputeType enum from string value."""
    assert ComputeType("int8") == ComputeType.INT8
    assert ComputeType("float16") == ComputeType.FLOAT16
    assert ComputeType("fp16") == ComputeType.FP16


def test_compute_type_enum_invalid_value():
    """Test that invalid ComputeType value raises ValueError."""
    with pytest.raises(ValueError):
        ComputeType("invalid")


def test_device_enum_string_comparison():
    """Test that Device enum values compare correctly as strings."""
    # Since Device(str, Enum), the enum members ARE strings
    assert Device.CPU.value == "cpu"
    assert Device.CPU == "cpu"  # str Enum compares equal to its value
    assert Device.CPU.value == Device("cpu").value


def test_compute_type_enum_string_comparison():
    """Test that ComputeType enum values compare correctly as strings."""
    # Since ComputeType(str, Enum), the enum members ARE strings
    assert ComputeType.INT8.value == "int8"
    assert ComputeType.INT8 == "int8"  # str Enum compares equal to its value
    assert ComputeType.INT8.value == ComputeType("int8").value


def test_device_enum_in_set():
    """Test that Device enum works in sets."""
    devices = {Device.CPU, Device.CUDA, Device.CPU}
    
    assert len(devices) == 2  # CPU appears once
    assert Device.CPU in devices
    assert Device.CUDA in devices


def test_compute_type_enum_in_set():
    """Test that ComputeType enum works in sets."""
    types = {ComputeType.INT8, ComputeType.FLOAT16, ComputeType.INT8}
    
    assert len(types) == 2  # INT8 appears once
    assert ComputeType.INT8 in types
    assert ComputeType.FLOAT16 in types


def test_enums_work_with_validators():
    """Test that enums can be used for validation."""
    from chatterbug.domain.model import EngineConfig
    
    # Should accept valid enum values
    config = EngineConfig(device="cpu", compute_type="int8")
    assert config.device == "cpu"
    assert config.compute_type == "int8"
    
    # Should reject invalid values
    with pytest.raises(Exception):  # Pydantic validation error
        EngineConfig(device="invalid_device")
    
    with pytest.raises(Exception):  # Pydantic validation error
        EngineConfig(compute_type="invalid_type")


def test_device_enum_names():
    """Test Device enum member names."""
    assert Device.CPU.name == "CPU"
    assert Device.CUDA.name == "CUDA"
    assert Device.AUTO.name == "AUTO"


def test_compute_type_enum_names():
    """Test ComputeType enum member names."""
    assert ComputeType.INT8.name == "INT8"
    assert ComputeType.FLOAT16.name == "FLOAT16"
    assert ComputeType.FP16.name == "FP16"
