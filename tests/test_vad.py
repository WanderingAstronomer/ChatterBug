"""Unit tests for VAD (Voice Activity Detection) abstractions (TDD)."""
from __future__ import annotations

import pytest

from chatterbug.audio.vad import VadService, NullVad, VadWrapper


def test_null_vad_returns_empty_spans():
    """Test that NullVad returns empty spans (no VAD filtering)."""
    vad = NullVad()
    
    audio = b"fake audio data" * 1000
    spans = vad.speech_spans(audio)
    
    assert spans == []


def test_null_vad_accepts_all_parameters():
    """Test that NullVad accepts all VadService parameters without error."""
    vad = NullVad()
    
    audio = b"fake audio data" * 1000
    spans = vad.speech_spans(
        audio,
        threshold=0.5,
        neg_threshold=0.3,
        min_silence_ms=1000,
        min_speech_ms=250,
        speech_pad_ms=100
    )
    
    assert spans == []  # Always returns empty regardless of parameters


def test_null_vad_is_protocol_compliant():
    """Test that NullVad implements VadService protocol."""
    vad = NullVad()
    
    # Should be usable as VadService
    assert hasattr(vad, 'speech_spans')
    assert callable(vad.speech_spans)


def test_vad_wrapper_initialization():
    """Test that VadWrapper can be initialized."""
    vad = VadWrapper()
    
    assert vad is not None
    assert vad.sample_rate == 16000


def test_vad_wrapper_with_custom_sample_rate():
    """Test that VadWrapper accepts custom sample rate."""
    vad = VadWrapper(sample_rate=8000)
    
    assert vad.sample_rate == 8000


def test_vad_wrapper_graceful_degradation_without_silero():
    """Test that VadWrapper works (returns empty) when silero is unavailable."""
    vad = VadWrapper()
    
    # VadWrapper should initialize even if silero is not available
    # In that case, _enabled will be False and methods should degrade gracefully
    assert vad is not None


def test_vad_wrapper_speech_spans_signature():
    """Test that VadWrapper.speech_spans has correct signature."""
    vad = VadWrapper()
    
    # Should accept the same parameters as the protocol
    audio = b"\x00\x00" * 16000  # 1 second of silence at 16kHz
    
    # Should not raise even if VAD is not enabled
    result = vad.speech_spans(
        audio,
        threshold=0.5,
        neg_threshold=0.3,
        min_silence_ms=1000,
        min_speech_ms=250,
        speech_pad_ms=100
    )
    
    # Result should be a list (empty if VAD not enabled)
    assert isinstance(result, list)


def test_vad_service_protocol_duck_typing():
    """Test that objects implementing speech_spans work as VadService."""
    
    class CustomVad:
        def speech_spans(
            self,
            audio: bytes,
            *,
            threshold: float = 0.5,
            neg_threshold: float | None = None,
            min_silence_ms: int | None = None,
            min_speech_ms: int | None = None,
            speech_pad_ms: int | None = None,
        ) -> list[tuple[int, int]]:
            # Return a fake span
            return [(0, 1000)]
    
    vad = CustomVad()
    
    # Should work as VadService via duck typing
    spans = vad.speech_spans(b"audio")
    assert spans == [(0, 1000)]


def test_null_vad_different_audio_sizes():
    """Test that NullVad handles various audio buffer sizes."""
    vad = NullVad()
    
    for size in [0, 1, 100, 10000]:
        audio = b"\x00" * size
        spans = vad.speech_spans(audio)
        assert spans == []


def test_vad_wrapper_is_speech_method_exists():
    """Test that VadWrapper has is_speech method for backward compatibility."""
    vad = VadWrapper()
    
    assert hasattr(vad, 'is_speech')
    assert callable(vad.is_speech)
    
    # Should return True (everything is speech) when VAD is not enabled
    result = vad.is_speech(b"\x00\x00" * 100)
    assert isinstance(result, bool)


def test_vad_wrapper_trim_method_exists():
    """Test that VadWrapper has trim method for backward compatibility."""
    vad = VadWrapper()
    
    assert hasattr(vad, 'trim')
    assert callable(vad.trim)
    
    # Should return audio unchanged when VAD is not enabled
    audio = b"test audio"
    result = vad.trim(audio)
    assert isinstance(result, bytes)
