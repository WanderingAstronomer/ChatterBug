"""Unit tests for SessionConfig dataclass (TDD)."""
from __future__ import annotations

import pytest

from chatterbug.app.transcription_session import SessionConfig


def test_session_config_default_values():
    """Test that SessionConfig has sensible defaults."""
    config = SessionConfig()
    
    assert config.audio_queue_size == 200
    assert config.segment_queue_size == 32
    assert config.thread_join_timeout_sec == 10.0


def test_session_config_custom_values():
    """Test that SessionConfig accepts custom values."""
    config = SessionConfig(
        audio_queue_size=500,
        segment_queue_size=64,
        thread_join_timeout_sec=20.0
    )
    
    assert config.audio_queue_size == 500
    assert config.segment_queue_size == 64
    assert config.thread_join_timeout_sec == 20.0


def test_session_config_is_frozen():
    """Test that SessionConfig is immutable (frozen)."""
    config = SessionConfig()
    
    with pytest.raises(Exception):  # dataclass(frozen=True) raises FrozenInstanceError
        config.audio_queue_size = 1000


def test_session_config_partial_override():
    """Test that SessionConfig allows partial overrides with defaults for others."""
    config = SessionConfig(audio_queue_size=1000)
    
    assert config.audio_queue_size == 1000
    assert config.segment_queue_size == 32  # default
    assert config.thread_join_timeout_sec == 10.0  # default


def test_session_config_equality():
    """Test that two SessionConfig instances with same values are equal."""
    config1 = SessionConfig(audio_queue_size=100, segment_queue_size=20)
    config2 = SessionConfig(audio_queue_size=100, segment_queue_size=20)
    
    assert config1 == config2


def test_session_config_inequality():
    """Test that SessionConfig instances with different values are not equal."""
    config1 = SessionConfig(audio_queue_size=100)
    config2 = SessionConfig(audio_queue_size=200)
    
    assert config1 != config2


def test_session_config_small_queue_sizes():
    """Test that SessionConfig accepts small queue sizes (edge case)."""
    config = SessionConfig(
        audio_queue_size=1,
        segment_queue_size=1,
        thread_join_timeout_sec=0.1
    )
    
    assert config.audio_queue_size == 1
    assert config.segment_queue_size == 1
    assert config.thread_join_timeout_sec == 0.1


def test_session_config_large_queue_sizes():
    """Test that SessionConfig accepts large queue sizes."""
    config = SessionConfig(
        audio_queue_size=10000,
        segment_queue_size=1000,
        thread_join_timeout_sec=300.0
    )
    
    assert config.audio_queue_size == 10000
    assert config.segment_queue_size == 1000
    assert config.thread_join_timeout_sec == 300.0


def test_session_config_repr():
    """Test that SessionConfig has a useful string representation."""
    config = SessionConfig(audio_queue_size=500)
    
    repr_str = repr(config)
    assert "SessionConfig" in repr_str
    assert "500" in repr_str


def test_session_config_in_transcription_session():
    """Test that SessionConfig can be used with TranscriptionSession."""
    from chatterbug.app.transcription_session import TranscriptionSession
    
    config = SessionConfig(
        audio_queue_size=100,
        segment_queue_size=10,
        thread_join_timeout_sec=5.0
    )
    
    session = TranscriptionSession(config=config)
    
    # Verify session was created (internal config is private, so we can't check it directly)
    assert session is not None
    # Verify we can create session without config (uses defaults)
    session_default = TranscriptionSession()
    assert session_default is not None
