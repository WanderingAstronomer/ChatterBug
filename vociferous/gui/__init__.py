"""KivyMD-based GUI for Vociferous."""

from .app import VociferousGUIApp
from .config_schema import (
    FIELD_METADATA,
    ConfigFieldSchema,
    get_config_schema,
)
from .errors import (
    DialogErrorData,
    format_error_for_dialog,
)
from .validation import (
    ValidationErrorInfo,
    format_validation_errors,
    validate_config_value,
)

__all__ = [
    "ConfigFieldSchema",
    "DialogErrorData",
    "FIELD_METADATA",
    "ValidationErrorInfo",
    "VociferousGUIApp",
    "format_error_for_dialog",
    "format_validation_errors",
    "get_config_schema",
    "validate_config_value",
]
