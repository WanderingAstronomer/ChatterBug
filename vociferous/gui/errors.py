"""Error display helpers for GUI dialogs.

This module provides utilities for formatting VociferousError instances
for display in GUI error dialogs, converting structured error data
into user-friendly text suitable for KivyMD dialogs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vociferous.domain.exceptions import VociferousError

__all__ = ["format_error_for_dialog", "DialogErrorData"]


class DialogErrorData:
    """Formatted error data for GUI dialog display.
    
    Contains pre-formatted strings ready for display in an error dialog,
    with appropriate formatting for title, message, details, and suggestions.
    
    Attributes:
        title: Dialog title (e.g., "Audio Decode Error")
        message: Main error message
        details: Formatted details section (may be empty)
        suggestions: Formatted suggestions section (may be empty)
    """
    
    __slots__ = ("title", "message", "details", "suggestions")
    
    def __init__(
        self,
        title: str,
        message: str,
        details: str,
        suggestions: str,
    ) -> None:
        self.title = title
        self.message = message
        self.details = details
        self.suggestions = suggestions
    
    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for flexible consumption.
        
        Returns:
            Dictionary with title, message, details, suggestions keys
        """
        return {
            "title": self.title,
            "message": self.message,
            "details": self.details,
            "suggestions": self.suggestions,
        }


def format_error_for_dialog(error: VociferousError) -> DialogErrorData:
    """Format VociferousError for GUI error dialog display.
    
    Converts a VociferousError into formatted strings suitable for
    display in a GUI error dialog, with user-friendly formatting.
    
    Args:
        error: VociferousError instance to format
    
    Returns:
        DialogErrorData with formatted strings for dialog display
    
    Example:
        >>> error = AudioDecodeError(
        ...     "Failed to decode audio file",
        ...     context={"file": "/path/test.mp3", "exit_code": 1},
        ...     suggestions=["Install ffmpeg", "Check file format"],
        ... )
        >>> dialog_data = format_error_for_dialog(error)
        >>> print(dialog_data.title)
        Audio Decode Error
        >>> print(dialog_data.suggestions)
        1. Install ffmpeg
        2. Check file format
    """
    # Format title from class name
    # "AudioDecodeError" -> "Audio Decode Error"
    error_name = error.__class__.__name__
    title = _format_class_name_as_title(error_name)
    
    # Main message
    message = error.message
    
    # Format context details
    details_lines: list[str] = []
    if error.context:
        for key, value in error.context.items():
            # Format key: remove underscores, capitalize words
            formatted_key = key.replace("_", " ").title()
            details_lines.append(f"{formatted_key}: {value}")
    
    details = "\n".join(details_lines)
    
    # Format suggestions as numbered list
    suggestions_lines: list[str] = []
    if error.suggestions:
        for i, suggestion in enumerate(error.suggestions, 1):
            suggestions_lines.append(f"{i}. {suggestion}")
    
    suggestions = "\n".join(suggestions_lines)
    
    return DialogErrorData(
        title=title,
        message=message,
        details=details,
        suggestions=suggestions,
    )


def _format_class_name_as_title(class_name: str) -> str:
    """Convert CamelCase class name to human-readable title.
    
    Examples:
        AudioDecodeError -> Audio Decode Error
        VADError -> VAD Error
        ConfigurationError -> Configuration Error
    """
    import re
    
    # Insert space before capital letters (but not at start or for consecutive caps)
    # Handle "VAD" specially - it's an acronym
    result = re.sub(r"([a-z])([A-Z])", r"\1 \2", class_name)
    
    # Handle consecutive capitals followed by lowercase
    # e.g., "VADError" should become "VAD Error"
    result = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", result)
    
    return result
