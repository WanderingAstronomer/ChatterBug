"""Constants and enums for ChatterBug domain model.

This module centralizes magic strings and configuration values to improve
type safety and maintainability.
"""
from __future__ import annotations

from enum import Enum


class Device(str, Enum):
    """Valid device types for engine execution."""
    CPU = "cpu"
    CUDA = "cuda"
    AUTO = "auto"


class ComputeType(str, Enum):
    """Valid compute/precision types for engines."""
    INT8 = "int8"
    INT8_FLOAT16 = "int8_float16"
    FLOAT16 = "float16"
    FLOAT32 = "float32"
    FP16 = "fp16"
    FP32 = "fp32"


class EngineKind(str, Enum):
    """Available transcription engine types."""
    WHISPER_TURBO = "whisper_turbo"
    VOXTRAL = "voxtral"
    PARAKEET_RNNT = "parakeet_rnnt"
