"""Unit tests for EngineMetadata dataclass (TDD)."""
from __future__ import annotations

import pytest

from chatterbug.domain.model import EngineMetadata


def test_engine_metadata_creation():
    """Test that EngineMetadata can be created with required fields."""
    metadata = EngineMetadata(
        model_name="whisper-large-v3",
        device="cuda",
        precision="float16"
    )
    
    assert metadata.model_name == "whisper-large-v3"
    assert metadata.device == "cuda"
    assert metadata.precision == "float16"


def test_engine_metadata_is_frozen():
    """Test that EngineMetadata is immutable (frozen)."""
    metadata = EngineMetadata(
        model_name="test-model",
        device="cpu",
        precision="int8"
    )
    
    with pytest.raises(Exception):  # Pydantic raises ValidationError or AttributeError
        metadata.model_name = "new-model"


def test_engine_metadata_equality():
    """Test that two EngineMetadata instances with same values are equal."""
    metadata1 = EngineMetadata(
        model_name="test-model",
        device="cpu",
        precision="int8"
    )
    metadata2 = EngineMetadata(
        model_name="test-model",
        device="cpu",
        precision="int8"
    )
    
    assert metadata1 == metadata2


def test_engine_metadata_inequality():
    """Test that EngineMetadata instances with different values are not equal."""
    metadata1 = EngineMetadata(
        model_name="model1",
        device="cpu",
        precision="int8"
    )
    metadata2 = EngineMetadata(
        model_name="model2",
        device="cpu",
        precision="int8"
    )
    
    assert metadata1 != metadata2


def test_engine_metadata_repr():
    """Test that EngineMetadata has a useful string representation."""
    metadata = EngineMetadata(
        model_name="test-model",
        device="cuda",
        precision="float16"
    )
    
    repr_str = repr(metadata)
    assert "EngineMetadata" in repr_str
    assert "test-model" in repr_str
    assert "cuda" in repr_str
    assert "float16" in repr_str


def test_engine_metadata_different_devices():
    """Test metadata with various device types."""
    for device in ["cpu", "cuda", "auto"]:
        metadata = EngineMetadata(
            model_name="test-model",
            device=device,
            precision="int8"
        )
        assert metadata.device == device


def test_engine_metadata_different_precisions():
    """Test metadata with various precision types."""
    for precision in ["int8", "int8_float16", "float16", "float32", "fp16", "fp32"]:
        metadata = EngineMetadata(
            model_name="test-model",
            device="cpu",
            precision=precision
        )
        assert metadata.precision == precision


def test_engine_metadata_model_copy():
    """Test that model_copy creates a new instance with updated fields."""
    original = EngineMetadata(
        model_name="original-model",
        device="cpu",
        precision="int8"
    )
    
    updated = original.model_copy(update={"device": "cuda", "precision": "float16"})
    
    assert original.model_name == "original-model"
    assert original.device == "cpu"
    assert original.precision == "int8"
    
    assert updated.model_name == "original-model"
    assert updated.device == "cuda"
    assert updated.precision == "float16"
