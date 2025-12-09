"""Tests for MemorySource audio streaming."""

import pytest

from vociferous.sources.memory import MemorySource


class TestMemorySourceInitialization:
    """Test MemorySource initialization."""
    
    def test_initialization_default_params(self) -> None:
        """MemorySource initializes with default parameters."""
        source = MemorySource(pcm_segments=[])
        
        assert source.sample_rate == 16000
        assert source.channels == 1
        assert source.chunk_ms == 30000
    
    def test_initialization_custom_params(self) -> None:
        """MemorySource accepts custom parameters."""
        source = MemorySource(
            pcm_segments=[],
            sample_rate=8000,
            channels=2,
            chunk_ms=10000,
        )
        
        assert source.sample_rate == 8000
        assert source.channels == 2
        assert source.chunk_ms == 10000


class TestMemorySourceStream:
    """Test stream method."""
    
    def test_streams_empty_segments(self) -> None:
        """Empty segments list yields no chunks."""
        source = MemorySource(pcm_segments=[])
        
        chunks = list(source.stream())
        
        assert chunks == []
    
    def test_streams_single_segment(self) -> None:
        """Single segment is streamed correctly."""
        # 1 second of audio at 16kHz mono
        pcm = b"\x00\x00" * 16000  # 32000 bytes
        
        source = MemorySource(
            pcm_segments=[pcm],
            sample_rate=16000,
            channels=1,
            chunk_ms=500,  # 0.5 second chunks
        )
        
        chunks = list(source.stream())
        
        assert len(chunks) == 2
        assert chunks[0].start_s == 0.0
        assert chunks[0].end_s == 0.5
        assert chunks[1].start_s == 0.5
        assert chunks[1].end_s == 1.0
    
    def test_streams_multiple_segments(self) -> None:
        """Multiple segments are concatenated correctly."""
        # Two 0.5 second segments
        pcm1 = b"\x00\x00" * 8000  # 16000 bytes
        pcm2 = b"\x00\x00" * 8000
        
        source = MemorySource(
            pcm_segments=[pcm1, pcm2],
            sample_rate=16000,
            channels=1,
            chunk_ms=500,  # Each segment fits in one chunk
        )
        
        chunks = list(source.stream())
        
        assert len(chunks) == 2
        assert chunks[0].start_s == 0.0
        assert chunks[1].start_s == 0.5  # Continues from first segment
    
    def test_skips_empty_segments(self) -> None:
        """Empty segments are skipped."""
        pcm = b"\x00\x00" * 8000
        
        source = MemorySource(
            pcm_segments=[pcm, b"", pcm],
            sample_rate=16000,
            channels=1,
            chunk_ms=500,
        )
        
        chunks = list(source.stream())
        
        assert len(chunks) == 2
    
    def test_chunk_sample_rate_preserved(self) -> None:
        """Chunk sample rate matches source."""
        pcm = b"\x00\x00" * 8000
        
        source = MemorySource(
            pcm_segments=[pcm],
            sample_rate=8000,
            channels=1,
            chunk_ms=1000,
        )
        
        chunks = list(source.stream())
        
        assert chunks[0].sample_rate == 8000
    
    def test_chunk_channels_preserved(self) -> None:
        """Chunk channels matches source."""
        # Stereo audio
        pcm = b"\x00\x00" * 16000  # 0.5 second stereo
        
        source = MemorySource(
            pcm_segments=[pcm],
            sample_rate=16000,
            channels=2,
            chunk_ms=500,
        )
        
        chunks = list(source.stream())
        
        assert chunks[0].channels == 2


class TestMemorySourceAlias:
    """Test backward compatibility alias."""
    
    def test_inmemoryaudiosource_alias(self) -> None:
        """InMemoryAudioSource is alias for MemorySource."""
        from vociferous.sources.memory import InMemoryAudioSource
        
        assert InMemoryAudioSource is MemorySource
