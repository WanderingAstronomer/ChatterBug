"""Domain-specific exceptions for ChatterBug.

This module defines custom exception types to replace generic RuntimeError and ValueError,
providing better error categorization and handling throughout the application.
"""

from __future__ import annotations


class ChatterBugError(Exception):
    """Base exception for all ChatterBug errors."""
    pass


class EngineError(ChatterBugError):
    """Raised when an ASR engine encounters an error during initialization or inference."""
    pass


class AudioDecodeError(ChatterBugError):
    """Raised when audio decoding fails."""
    pass


class ConfigurationError(ChatterBugError):
    """Raised when configuration validation fails."""
    pass


class SessionError(ChatterBugError):
    """Raised when a transcription session encounters an error."""
    pass


class DependencyError(ChatterBugError):
    """Raised when a required dependency is missing."""
    pass
