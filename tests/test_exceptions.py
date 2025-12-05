"""Tests for domain-specific exceptions."""
import pytest

from chatterbug.domain.exceptions import (
    ChatterBugError,
    EngineError,
    AudioDecodeError,
    ConfigurationError,
    SessionError,
    DependencyError,
)


def test_exception_hierarchy():
    """Test that all custom exceptions inherit from ChatterBugError."""
    assert issubclass(EngineError, ChatterBugError)
    assert issubclass(AudioDecodeError, ChatterBugError)
    assert issubclass(ConfigurationError, ChatterBugError)
    assert issubclass(SessionError, ChatterBugError)
    assert issubclass(DependencyError, ChatterBugError)


def test_chatterbug_error_is_exception():
    """Test that ChatterBugError inherits from Exception."""
    assert issubclass(ChatterBugError, Exception)


def test_engine_error_can_be_raised():
    """Test that EngineError can be raised and caught."""
    with pytest.raises(EngineError, match="test error"):
        raise EngineError("test error")


def test_audio_decode_error_can_be_raised():
    """Test that AudioDecodeError can be raised and caught."""
    with pytest.raises(AudioDecodeError, match="decode failed"):
        raise AudioDecodeError("decode failed")


def test_configuration_error_can_be_raised():
    """Test that ConfigurationError can be raised and caught."""
    with pytest.raises(ConfigurationError, match="invalid config"):
        raise ConfigurationError("invalid config")


def test_session_error_can_be_raised():
    """Test that SessionError can be raised and caught."""
    with pytest.raises(SessionError, match="session error"):
        raise SessionError("session error")


def test_dependency_error_can_be_raised():
    """Test that DependencyError can be raised and caught."""
    with pytest.raises(DependencyError, match="missing dependency"):
        raise DependencyError("missing dependency")


def test_catch_chatterbug_error():
    """Test that ChatterBugError catches all custom exceptions."""
    with pytest.raises(ChatterBugError):
        raise EngineError("engine error")
    
    with pytest.raises(ChatterBugError):
        raise AudioDecodeError("decode error")
    
    with pytest.raises(ChatterBugError):
        raise ConfigurationError("config error")
    
    with pytest.raises(ChatterBugError):
        raise SessionError("session error")
    
    with pytest.raises(ChatterBugError):
        raise DependencyError("dependency error")
