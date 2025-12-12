"""User-friendly validation error formatting for GUI.

This module converts Pydantic's technical validation errors into
user-friendly messages suitable for display in GUI dialogs.

Example:
    >>> try:
    ...     config = EngineConfig(compute_type="invalid")
    ... except ValidationError as e:
    ...     errors = format_validation_errors(e)
    ...     for err in errors:
    ...         show_error_dialog(err.field, err.message)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

__all__ = [
    "ValidationErrorInfo",
    "format_validation_errors",
    "validate_config_value",
]


@dataclass(frozen=True)
class ValidationErrorInfo:
    """User-friendly validation error for GUI display.
    
    Attributes:
        field: Field name that failed validation
        message: User-friendly error message
        input_value: The invalid value that was provided
        help_text: Additional help text
        valid_options: List of valid options (for choice fields)
    """
    
    field: str
    message: str
    input_value: Any = None
    help_text: str = ""
    valid_options: tuple[str, ...] = ()
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize for GUI consumption."""
        return {
            "field": self.field,
            "message": self.message,
            "input_value": self.input_value,
            "help_text": self.help_text,
            "valid_options": list(self.valid_options),
        }


def format_validation_errors(
    validation_error: ValidationError,
) -> list[ValidationErrorInfo]:
    """Convert Pydantic ValidationError to GUI-friendly format.
    
    Takes the technical error messages from Pydantic and converts them
    to human-readable messages appropriate for GUI display.
    
    Args:
        validation_error: Pydantic ValidationError from model validation
    
    Returns:
        List of ValidationErrorInfo with user-friendly messages
    
    Example:
        >>> try:
        ...     config = EngineConfig(compute_type="invalid")
        ... except ValidationError as e:
        ...     errors = format_validation_errors(e)
        ...     for err in errors:
        ...         print(f"{err.field}: {err.message}")
    """
    gui_errors: list[ValidationErrorInfo] = []
    
    for error in validation_error.errors():
        # Build field path
        field_path = ".".join(str(loc) for loc in error["loc"])
        error_type = error["type"]
        input_value = error.get("input")
        ctx = error.get("ctx", {})
        
        # Create user-friendly message based on error type
        message, help_text, valid_options = _format_error_message(
            error_type=error_type,
            ctx=ctx,
            original_msg=error.get("msg", ""),
        )
        
        gui_error = ValidationErrorInfo(
            field=field_path,
            message=message,
            input_value=input_value,
            help_text=help_text,
            valid_options=valid_options,
        )
        
        gui_errors.append(gui_error)
    
    return gui_errors


def _format_error_message(
    error_type: str,
    ctx: dict[str, Any],
    original_msg: str,
) -> tuple[str, str, tuple[str, ...]]:
    """Format error message based on error type.
    
    Returns:
        Tuple of (message, help_text, valid_options)
    """
    valid_options: tuple[str, ...] = ()
    help_text = ""
    
    if error_type == "literal_error":
        # Literal type violation (invalid choice)
        expected = ctx.get("expected", "")
        valid_options = _parse_expected_values(expected)
        message = "Invalid selection"
        if valid_options:
            options_str = ", ".join(valid_options[:5])
            if len(valid_options) > 5:
                options_str += ", ..."
            help_text = f"Valid options: {options_str}"
    
    elif error_type == "greater_than_equal":
        limit = ctx.get("ge", ctx.get("limit_value", "?"))
        message = f"Must be at least {limit}"
        help_text = "Please enter a larger value"
    
    elif error_type == "less_than_equal":
        limit = ctx.get("le", ctx.get("limit_value", "?"))
        message = f"Must be at most {limit}"
        help_text = "Please enter a smaller value"
    
    elif error_type == "greater_than":
        limit = ctx.get("gt", ctx.get("limit_value", "?"))
        message = f"Must be greater than {limit}"
        help_text = "Please enter a larger value"
    
    elif error_type == "less_than":
        limit = ctx.get("lt", ctx.get("limit_value", "?"))
        message = f"Must be less than {limit}"
        help_text = "Please enter a smaller value"
    
    elif error_type == "missing":
        message = "This field is required"
        help_text = "Please provide a value"
    
    elif error_type == "string_type":
        message = "Must be text"
        help_text = "Please enter a text value"
    
    elif error_type in ("int_type", "int_parsing"):
        message = "Must be a whole number"
        help_text = "Please enter a number without decimals"
    
    elif error_type in ("float_type", "float_parsing"):
        message = "Must be a number"
        help_text = "Please enter a valid number"
    
    elif error_type == "bool_type":
        message = "Must be true or false"
        help_text = "Use the checkbox to toggle"
    
    elif error_type == "value_error":
        # Custom validation error
        message = original_msg or "Invalid value"
        help_text = "Please check the input"
    
    elif error_type == "string_too_short":
        min_len = ctx.get("min_length", 1)
        message = f"Must be at least {min_len} characters"
        help_text = "Please enter more text"
    
    elif error_type == "string_too_long":
        max_len = ctx.get("max_length", "?")
        message = f"Must be at most {max_len} characters"
        help_text = "Please shorten the text"
    
    else:
        # Generic fallback
        message = original_msg or "Invalid value"
        help_text = "Please check this field"
    
    return message, help_text, valid_options


def _parse_expected_values(expected_str: str) -> tuple[str, ...]:
    """Parse expected values from Pydantic error message.
    
    Example:
        >>> _parse_expected_values("'float32', 'float16', or 'int8'")
        ('float32', 'float16', 'int8')
    """
    if not expected_str:
        return ()
    
    # Remove quotes and "or"
    cleaned = expected_str.replace("'", "").replace('"', "").replace(" or ", ", ")
    
    # Split by comma
    values = tuple(v.strip() for v in cleaned.split(",") if v.strip())
    
    return values


def validate_config_value(
    field_name: str,
    value: Any,
    config_class: type[Any],
) -> ValidationErrorInfo | None:
    """Validate a single config field value.
    
    This allows the GUI to validate individual fields as the user
    types, providing immediate feedback.
    
    Args:
        field_name: Name of the field to validate
        value: Value to validate
        config_class: Pydantic model class
    
    Returns:
        ValidationErrorInfo if invalid, None if valid
    
    Example:
        >>> error = validate_config_value("compute_type", "invalid", EngineConfig)
        >>> if error:
        ...     show_field_error(error.message)
    """
    from pydantic import BaseModel
    
    if not issubclass(config_class, BaseModel):
        return None
    
    # Get the field info
    if field_name not in config_class.model_fields:
        return ValidationErrorInfo(
            field=field_name,
            message="Unknown field",
        )
    
    # Try to construct a partial model with just this field
    # Use defaults for other fields
    try:
        # Get all field defaults
        field_values = {}
        for fname, finfo in config_class.model_fields.items():
            if fname == field_name:
                field_values[fname] = value
            elif finfo.default is not None:
                field_values[fname] = finfo.default
            elif finfo.default_factory is not None:
                field_values[fname] = finfo.default_factory()
        
        # Try to create the model
        config_class(**field_values)
        return None
        
    except ValidationError as e:
        # Check if this field specifically failed
        for error in e.errors():
            error_field = ".".join(str(loc) for loc in error["loc"])
            if error_field == field_name:
                errors = format_validation_errors(e)
                for err in errors:
                    if err.field == field_name:
                        return err
        
        # Field didn't fail specifically - validation passed for this field
        return None
