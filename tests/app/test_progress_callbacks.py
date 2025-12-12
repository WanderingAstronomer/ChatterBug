"""Tests for progress callback system (GUI mode).

These tests verify that the callback-based progress tracking works correctly,
enabling GUI integration without depending on any specific UI framework.
"""

from __future__ import annotations

import time

import pytest

from vociferous.app.progress import (
    CallbackProgressTracker,
    TranscriptionProgress,
    transcription_progress,
)
from vociferous.domain.protocols import ProgressUpdateData


class TestCallbackProgressTracker:
    """Tests for CallbackProgressTracker."""

    def test_callback_receives_updates(self) -> None:
        """Test that callback receives all updates."""
        updates: list[ProgressUpdateData] = []
        
        def callback(update: ProgressUpdateData) -> None:
            updates.append(update)
        
        tracker = CallbackProgressTracker(callback=callback)
        
        task = tracker.add_step("Testing...", total=100)
        tracker.update(task, completed=50)
        tracker.complete(task)
        
        # Should receive 3 updates: start, update, complete
        assert len(updates) == 3
        
        # Check first update (start)
        assert updates[0].progress == 0.0
        assert updates[0].elapsed_s == 0.0
        
        # Check second update (progress)
        assert updates[1].progress == 0.5
        
        # Check third update (complete)
        assert updates[2].progress == 1.0

    def test_callback_required(self) -> None:
        """Test that callback parameter is required."""
        with pytest.raises(ValueError, match="callback parameter required"):
            CallbackProgressTracker(callback=None)  # type: ignore[arg-type]

    def test_stage_extraction(self) -> None:
        """Test that stage names are extracted from descriptions."""
        updates: list[ProgressUpdateData] = []
        
        def callback(update: ProgressUpdateData) -> None:
            updates.append(update)
        
        tracker = CallbackProgressTracker(callback=callback)
        
        # Test various stage descriptions
        task1 = tracker.add_step("[cyan]Decoding audio...")
        tracker.complete(task1)
        
        task2 = tracker.add_step("Detecting speech segments...")
        tracker.complete(task2)
        
        task3 = tracker.add_step("Transcribing audio files...")
        tracker.complete(task3)
        
        # Verify stages were extracted
        assert updates[0].stage == "decode"
        assert updates[2].stage == "vad"
        assert updates[4].stage == "transcribe"

    def test_rich_markup_cleaned(self) -> None:
        """Test that Rich markup is removed from messages."""
        updates: list[ProgressUpdateData] = []
        
        def callback(update: ProgressUpdateData) -> None:
            updates.append(update)
        
        tracker = CallbackProgressTracker(callback=callback)
        
        task = tracker.add_step("[cyan]Processing [bold]audio[/bold]...")
        tracker.complete(task)
        
        # Message should have Rich markup removed
        assert "[cyan]" not in updates[0].message
        assert "[bold]" not in updates[0].message
        assert "[/bold]" not in updates[0].message
        assert "Processing audio..." in updates[0].message

    def test_indeterminate_progress(self) -> None:
        """Test indeterminate progress (no total)."""
        updates: list[ProgressUpdateData] = []
        
        def callback(update: ProgressUpdateData) -> None:
            updates.append(update)
        
        tracker = CallbackProgressTracker(callback=callback)
        
        # No total = indeterminate
        task = tracker.add_step("Processing...", total=None)
        tracker.update(task, description="Still processing...")
        tracker.complete(task)
        
        # Progress should be None for indeterminate until complete
        assert updates[0].progress is None
        assert updates[1].progress is None
        assert updates[2].progress == 1.0  # Complete is always 1.0


class TestTranscriptionProgressModes:
    """Tests for TranscriptionProgress mode parameter."""

    def test_callback_mode_basic(self) -> None:
        """Test basic callback mode operation."""
        updates: list[ProgressUpdateData] = []
        
        def callback(update: ProgressUpdateData) -> None:
            updates.append(update)
        
        progress = TranscriptionProgress(mode="callback", callback=callback)
        
        with progress:
            task = progress.start_decode()
            progress.complete_decode(task)
        
        # Verify we got updates
        assert len(updates) >= 2
        assert any(u.stage == "decode" for u in updates)

    def test_callback_mode_requires_callback(self) -> None:
        """Test that callback mode requires callback parameter."""
        with pytest.raises(ValueError, match="callback parameter required"):
            TranscriptionProgress(mode="callback", callback=None)

    def test_silent_mode(self) -> None:
        """Test silent mode produces no output and doesn't raise."""
        # Silent mode should not raise
        progress = TranscriptionProgress(mode="silent")
        
        with progress:
            task = progress.start_decode()
            progress.complete_decode(task)
            task = progress.start_vad()
            progress.complete_vad(task, 10)
            progress.success("Done")

    def test_rich_mode_default(self) -> None:
        """Test that rich mode is the default for verbose."""
        # This shouldn't raise
        progress = TranscriptionProgress(mode="rich")
        
        with progress:
            task = progress.add_step("Testing...", total=None)
            progress.complete(task)

    def test_backward_compatibility_verbose(self) -> None:
        """Test backward compatibility with verbose parameter."""
        # Legacy usage with verbose=True should still work
        progress = TranscriptionProgress(verbose=True)
        
        with progress:
            task = progress.add_step("Testing...")
            progress.complete(task)
        
        # Legacy usage with verbose=False should be silent
        progress_silent = TranscriptionProgress(verbose=False)
        
        with progress_silent:
            task = progress_silent.add_step("Testing...")
            progress_silent.complete(task)


class TestTranscriptionProgressContextManager:
    """Tests for transcription_progress context manager."""

    def test_context_manager_callback_mode(self) -> None:
        """Test context manager with callback mode."""
        updates: list[ProgressUpdateData] = []
        
        def callback(update: ProgressUpdateData) -> None:
            updates.append(update)
        
        with transcription_progress(mode="callback", callback=callback) as progress:
            task = progress.start_decode()
            progress.complete_decode(task)
        
        assert len(updates) >= 2

    def test_context_manager_silent_mode(self) -> None:
        """Test context manager with silent mode."""
        with transcription_progress(mode="silent") as progress:
            task = progress.start_decode()
            progress.complete_decode(task)
            task = progress.start_transcribe(5)
            progress.complete_transcribe(task)


class TestElapsedTimeTracking:
    """Tests for elapsed time tracking in callbacks."""

    def test_elapsed_time_increases(self) -> None:
        """Test that elapsed time increases over time."""
        updates: list[ProgressUpdateData] = []
        
        def callback(update: ProgressUpdateData) -> None:
            updates.append(update)
        
        progress = TranscriptionProgress(mode="callback", callback=callback)
        
        with progress:
            task = progress.start_decode()
            time.sleep(0.1)  # Wait a bit
            progress.update(task, completed=50)
            progress.complete_decode(task)
        
        # Check elapsed time is tracked
        assert updates[0].elapsed_s == 0.0  # Start is always 0
        assert updates[1].elapsed_s is not None
        assert updates[1].elapsed_s >= 0.1  # At least 100ms elapsed
        assert updates[2].elapsed_s is not None
        assert updates[2].elapsed_s >= 0.1


class TestProgressUpdateData:
    """Tests for ProgressUpdateData dataclass."""

    def test_progress_update_data_creation(self) -> None:
        """Test creating ProgressUpdateData."""
        update = ProgressUpdateData(
            stage="decode",
            progress=0.5,
            message="Decoding...",
            elapsed_s=10.5,
            remaining_s=10.5,
        )
        
        assert update.stage == "decode"
        assert update.progress == 0.5
        assert update.message == "Decoding..."
        assert update.elapsed_s == 10.5
        assert update.remaining_s == 10.5

    def test_progress_update_data_optional_fields(self) -> None:
        """Test that optional fields default to None."""
        update = ProgressUpdateData(
            stage="transcribe",
            progress=None,
            message="Processing...",
        )
        
        assert update.elapsed_s is None
        assert update.remaining_s is None

    def test_progress_update_data_frozen(self) -> None:
        """Test that ProgressUpdateData is immutable (frozen)."""
        update = ProgressUpdateData(
            stage="decode",
            progress=0.5,
            message="Test",
        )
        
        with pytest.raises(AttributeError):
            update.stage = "vad"  # type: ignore[misc]


class TestAllWorkflowStages:
    """Tests for all workflow stage methods with callbacks."""

    def test_all_stages_produce_callbacks(self) -> None:
        """Test that all workflow stage methods produce callbacks."""
        updates: list[ProgressUpdateData] = []
        stages_seen: set[str] = set()
        
        def callback(update: ProgressUpdateData) -> None:
            updates.append(update)
            stages_seen.add(update.stage)
        
        progress = TranscriptionProgress(mode="callback", callback=callback)
        
        with progress:
            # Decode
            task = progress.start_decode()
            progress.complete_decode(task)
            
            # Preprocess
            task = progress.start_preprocess()
            progress.complete_preprocess(task, "clean")
            
            # VAD
            task = progress.start_vad()
            progress.complete_vad(task, 25)
            
            # Condense
            task = progress.start_condense()
            progress.complete_condense(task, 3)
            
            # Transcribe
            task = progress.start_transcribe(3)
            progress.complete_transcribe(task)
            
            # Refine
            task = progress.start_refine()
            progress.complete_refine(task)
            
            # Messages
            progress.success("Done!")
            progress.warning("Warning!")
            progress.error("Error!")
        
        # Verify all stages were seen
        assert "decode" in stages_seen
        assert "preprocess" in stages_seen
        assert "vad" in stages_seen
        assert "condense" in stages_seen
        assert "transcribe" in stages_seen
        assert "refine" in stages_seen
        
        # Verify many updates were received
        assert len(updates) >= 12  # At least 2 per stage
