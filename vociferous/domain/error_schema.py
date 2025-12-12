"""JSON schema for error serialization (documentation and type checking).

This module provides TypedDict definitions for the error serialization format
used by VociferousError.to_dict(), enabling type-safe handling of serialized
errors in GUI and API contexts.
"""

from __future__ import annotations

from typing import Any, TypedDict

__all__ = ["ErrorDict"]


class ErrorDict(TypedDict):
    """Type definition for serialized error dictionary.
    
    This documents the structure returned by VociferousError.to_dict()
    for GUI and API consumers.
    
    Attributes:
        error_type: Exception class name (e.g., 'AudioDecodeError')
        message: Human-readable error message
        context: Additional context (file paths, error codes, parameters)
        suggestions: List of actionable suggestions for the user
        timestamp: ISO 8601 timestamp when error occurred
        cause: Stringified original exception, or None
    
    Example:
        >>> def handle_error(error_dict: ErrorDict) -> None:
        ...     print(f"Error: {error_dict['message']}")
        ...     for suggestion in error_dict['suggestions']:
        ...         print(f"  - {suggestion}")
    """
    
    error_type: str
    """Exception class name (e.g., 'AudioDecodeError', 'VADError')."""
    
    message: str
    """Human-readable error message."""
    
    context: dict[str, Any]
    """Additional context (file paths, durations, error codes, etc.)."""
    
    suggestions: list[str]
    """List of actionable suggestions for user."""
    
    timestamp: str
    """ISO 8601 timestamp when error occurred."""
    
    cause: str | None
    """Stringified original exception, if any."""
