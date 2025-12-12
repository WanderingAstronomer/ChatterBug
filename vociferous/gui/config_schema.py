"""Config schema extraction for GUI auto-generation.

This module provides tools for extracting GUI-friendly metadata from
Vociferous configuration classes, enabling automatic generation of
settings panels with appropriate widgets (dropdowns, sliders, etc.).

The schema extraction works with:
- Pydantic models (EngineConfig, TranscriptionOptions)
- Frozen dataclasses (SegmentationProfile, EngineProfile)

Example:
    >>> from vociferous.domain.model import SegmentationProfile
    >>> schema = get_config_schema(SegmentationProfile)
    >>> for field in schema:
    ...     print(f"{field.name}: {field.widget_type}")
    threshold: slider
    min_silence_ms: slider
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Literal, get_args, get_origin

from pydantic import BaseModel

__all__ = [
    "ConfigFieldSchema",
    "get_config_schema",
    "FIELD_METADATA",
]


# Pre-defined field metadata for known fields
# This provides GUI hints without modifying the domain models
FIELD_METADATA: dict[str, dict[str, Any]] = {
    # Engine fields
    "engine_name": {
        "description": "ASR engine to use",
        "choices": ["canary_qwen", "whisper_turbo"],
        "choice_labels": {
            "canary_qwen": "Canary-Qwen (High Quality, CUDA only)",
            "whisper_turbo": "Whisper Turbo (Fast, CPU/CUDA)",
        },
        "help": "Canary-Qwen provides best quality but requires NVIDIA GPU. Whisper Turbo is faster and works on CPU.",
    },
    "model_name": {
        "description": "Model variant",
        "help": "Leave blank to use default model for selected engine",
    },
    "device": {
        "description": "Compute device",
        "choices": ["auto", "cuda", "cpu"],
        "choice_labels": {
            "auto": "Auto-detect",
            "cuda": "GPU (NVIDIA CUDA)",
            "cpu": "CPU (slower)",
        },
        "help": "GPU is 10-100x faster than CPU for transcription",
    },
    "compute_type": {
        "description": "Precision type",
        "choices": ["auto", "float32", "float16", "bfloat16", "int8"],
        "choice_labels": {
            "auto": "Auto (recommended)",
            "float32": "FP32 (Highest Quality, Slowest)",
            "float16": "FP16 (Balanced)",
            "bfloat16": "BF16 (Canary-Qwen optimized)",
            "int8": "INT8 (Fastest, Lower Quality)",
        },
        "help": "Lower precision is faster but may reduce accuracy. Auto selects the best option for your hardware.",
    },
    "language": {
        "description": "Target language",
        "help": "Language of the audio content. Use 'en' for English, 'es' for Spanish, etc.",
    },
    # Segmentation fields
    "threshold": {
        "description": "VAD sensitivity",
        "slider": {"min": 0.1, "max": 0.9, "step": 0.05},
        "help": "Lower values detect quieter speech but may include background noise. Higher values require clearer speech.",
    },
    "min_silence_ms": {
        "description": "Minimum silence duration (ms)",
        "slider": {"min": 100, "max": 2000, "step": 100},
        "help": "Shorter values detect pauses faster but may split mid-sentence.",
    },
    "min_speech_ms": {
        "description": "Minimum speech duration (ms)",
        "slider": {"min": 100, "max": 2000, "step": 50},
        "help": "Filters out very short sounds like coughs or clicks.",
    },
    "speech_pad_ms": {
        "description": "Speech padding (ms)",
        "slider": {"min": 0, "max": 500, "step": 50},
        "help": "Padding added around detected speech segments.",
    },
    "max_chunk_s": {
        "description": "Maximum chunk duration (seconds)",
        "slider": {"min": 10.0, "max": 120.0, "step": 5.0},
        "help": "Audio is split into chunks to fit engine limits. 60s is optimal for Canary-Qwen.",
    },
    "chunk_search_start_s": {
        "description": "Split search start (seconds)",
        "slider": {"min": 10.0, "max": 60.0, "step": 5.0},
        "help": "When to start looking for natural split points in long audio.",
    },
    "min_gap_for_split_s": {
        "description": "Natural split gap threshold (seconds)",
        "slider": {"min": 0.5, "max": 10.0, "step": 0.5},
        "help": "Prefers splitting at silences longer than this.",
    },
    # Transcription options
    "beam_size": {
        "description": "Beam search width",
        "slider": {"min": 1, "max": 10, "step": 1},
        "help": "Higher values may improve accuracy but are slower.",
    },
    "temperature": {
        "description": "Sampling temperature",
        "slider": {"min": 0.0, "max": 1.0, "step": 0.1},
        "help": "Lower values are more deterministic, higher values add randomness.",
    },
}


@dataclass(frozen=True)
class ConfigFieldSchema:
    """Metadata about a config field for GUI rendering.
    
    Attributes:
        name: Field name (e.g., "threshold")
        field_type: Python type as string (e.g., "float")
        default: Default value
        description: Short description for label
        required: Whether field is required
        choices: List of valid options (for dropdowns)
        choice_labels: Human-readable labels for choices
        help_text: Detailed help for tooltips
        widget_type: Suggested widget type
        widget_params: Widget-specific parameters (e.g., slider min/max)
    """
    
    name: str
    field_type: str
    default: Any
    description: str = ""
    required: bool = False
    choices: tuple[Any, ...] = ()
    choice_labels: dict[str, str] | None = None
    help_text: str = ""
    widget_type: Literal["text", "number", "slider", "dropdown", "checkbox"] = "text"
    widget_params: dict[str, Any] | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for GUI consumption."""
        return {
            "name": self.name,
            "type": self.field_type,
            "default": self.default,
            "description": self.description,
            "required": self.required,
            "choices": list(self.choices),
            "choice_labels": self.choice_labels or {},
            "help_text": self.help_text,
            "widget_type": self.widget_type,
            "widget_params": self.widget_params or {},
        }


def get_config_schema(config_class: type[Any]) -> list[ConfigFieldSchema]:
    """Extract GUI schema from config class.
    
    Supports both Pydantic models and dataclasses. Uses FIELD_METADATA
    for GUI hints where available.
    
    Args:
        config_class: Pydantic model or dataclass
    
    Returns:
        List of ConfigFieldSchema for each field
    
    Example:
        >>> from vociferous.domain.model import SegmentationProfile
        >>> schema = get_config_schema(SegmentationProfile)
        >>> for field in schema:
        ...     print(f"{field.name}: {field.widget_type}")
    """
    if is_dataclass(config_class):
        return _extract_dataclass_schema(config_class)
    elif issubclass(config_class, BaseModel):
        return _extract_pydantic_schema(config_class)
    else:
        raise TypeError(f"Unsupported config type: {config_class}")


def _extract_dataclass_schema(dc_class: type[Any]) -> list[ConfigFieldSchema]:
    """Extract schema from a dataclass."""
    result: list[ConfigFieldSchema] = []
    
    for dc_field in fields(dc_class):
        field_schema = _create_field_schema(
            name=dc_field.name,
            field_type=dc_field.type,
            default=dc_field.default if dc_field.default is not dc_field.default_factory else None,
        )
        result.append(field_schema)
    
    return result


def _extract_pydantic_schema(model_class: type[BaseModel]) -> list[ConfigFieldSchema]:
    """Extract schema from a Pydantic model."""
    result: list[ConfigFieldSchema] = []
    
    for field_name, field_info in model_class.model_fields.items():
        default = field_info.default
        if default is None and field_info.default_factory is not None:
            try:
                default = field_info.default_factory()
            except Exception:
                default = None
        
        field_schema = _create_field_schema(
            name=field_name,
            field_type=field_info.annotation,
            default=default,
        )
        result.append(field_schema)
    
    return result


def _create_field_schema(
    name: str,
    field_type: Any,
    default: Any,
) -> ConfigFieldSchema:
    """Create schema for a single field."""
    # Get metadata from our pre-defined hints
    metadata = FIELD_METADATA.get(name, {})
    
    # Determine type string
    type_str = _get_type_string(field_type)
    
    # Extract choices from Literal type or metadata
    choices: tuple[Any, ...] = ()
    if get_origin(field_type) is Literal:
        choices = get_args(field_type)
    elif "choices" in metadata:
        choices = tuple(metadata["choices"])
    
    # Get choice labels
    choice_labels = metadata.get("choice_labels")
    
    # Infer widget type
    widget_type = _infer_widget_type(
        field_type=field_type,
        choices=choices,
        metadata=metadata,
    )
    
    # Get widget params
    widget_params = metadata.get("slider") if "slider" in metadata else None
    
    return ConfigFieldSchema(
        name=name,
        field_type=type_str,
        default=default,
        description=metadata.get("description", ""),
        required=default is None,
        choices=choices,
        choice_labels=choice_labels,
        help_text=metadata.get("help", ""),
        widget_type=widget_type,
        widget_params=widget_params,
    )


def _get_type_string(field_type: Any) -> str:
    """Get a simple string representation of the type."""
    if field_type is None:
        return "None"
    
    origin = get_origin(field_type)
    if origin is Literal:
        return "literal"
    elif origin is not None:
        # Generic type like Optional, Union, etc.
        args = get_args(field_type)
        if len(args) == 2 and type(None) in args:
            # Optional[X] -> "X | None"
            non_none = [a for a in args if a is not type(None)][0]
            return f"{_get_type_string(non_none)} | None"
        return str(field_type)
    
    if hasattr(field_type, "__name__"):
        return field_type.__name__
    
    return str(field_type)


def _infer_widget_type(
    field_type: Any,
    choices: tuple[Any, ...],
    metadata: dict[str, Any],
) -> Literal["text", "number", "slider", "dropdown", "checkbox"]:
    """Infer appropriate widget type from field metadata."""
    # Dropdown if choices exist
    if choices:
        return "dropdown"
    
    # Slider if slider params exist
    if "slider" in metadata:
        return "slider"
    
    # Get base type
    base_type = field_type
    if get_origin(field_type) is not None:
        args = get_args(field_type)
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            base_type = non_none[0]
    
    # Bool -> checkbox
    if base_type is bool:
        return "checkbox"
    
    # Int/float -> number
    if base_type in (int, float):
        return "number"
    
    # Default to text
    return "text"
