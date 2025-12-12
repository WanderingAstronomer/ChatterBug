"""Tests for progress tracking module."""

from vociferous.app.progress import (
    NullProgressTracker,
    RichProgressTracker,
    SimpleProgressTracker,
    TranscriptionProgress,
    transcription_progress,
)


class TestNullProgressTracker:
    """Tests for the no-op progress tracker."""

    def test_add_step_returns_none(self):
        """add_step should return None for null tracker."""
        tracker = NullProgressTracker()
        result = tracker.add_step("Test step", total=100)
        assert result is None

    def test_update_does_nothing(self):
        """update should not raise errors."""
        tracker = NullProgressTracker()
        task_id = tracker.add_step("Test")
        # Should not raise
        tracker.update(task_id, description="Updated", completed=50)

    def test_advance_does_nothing(self):
        """advance should not raise errors."""
        tracker = NullProgressTracker()
        task_id = tracker.add_step("Test")
        tracker.advance(task_id, 1.0)

    def test_complete_does_nothing(self):
        """complete should not raise errors."""
        tracker = NullProgressTracker()
        task_id = tracker.add_step("Test")
        tracker.complete(task_id)

    def test_print_does_nothing(self):
        """print should not raise errors."""
        tracker = NullProgressTracker()
        tracker.print("Test message", style="bold")


class TestSimpleProgressTracker:
    """Tests for the simple text-based progress tracker."""

    def test_add_step_returns_task_id(self):
        """add_step should return a task ID string."""
        tracker = SimpleProgressTracker(verbose=True)
        task_id = tracker.add_step("Test step")
        assert task_id is not None
        assert isinstance(task_id, str)
        assert task_id.startswith("task-")

    def test_add_step_silent_when_not_verbose(self):
        """add_step should return empty string when not verbose."""
        tracker = SimpleProgressTracker(verbose=False)
        task_id = tracker.add_step("Test step")
        assert task_id == ""

    def test_complete_removes_task(self):
        """complete should remove task from active tasks."""
        tracker = SimpleProgressTracker(verbose=True)
        task_id = tracker.add_step("Test step")
        assert task_id in tracker._active_tasks
        tracker.complete(task_id)
        assert task_id not in tracker._active_tasks


class TestRichProgressTracker:
    """Tests for the Rich-based progress tracker."""

    def test_lazy_initialization(self):
        """Progress should not be initialized until used."""
        tracker = RichProgressTracker(verbose=True)
        assert tracker._progress is None
        assert not tracker._started

    def test_enter_initializes_progress(self):
        """Entering context should initialize Rich progress."""
        tracker = RichProgressTracker(verbose=True)
        with tracker:
            assert tracker._started

    def test_exit_stops_progress(self):
        """Exiting context should stop Rich progress."""
        tracker = RichProgressTracker(verbose=True)
        with tracker:
            pass
        assert tracker._progress is None

    def test_add_step_returns_task_id(self):
        """add_step should return a valid task ID."""
        tracker = RichProgressTracker(verbose=True)
        with tracker:
            task_id = tracker.add_step("Test step", total=100)
            # Rich returns TaskID which is an int
            assert task_id is not None

    def test_not_verbose_returns_none(self):
        """add_step should return None when not verbose."""
        tracker = RichProgressTracker(verbose=False)
        with tracker:
            task_id = tracker.add_step("Test step")
            assert task_id is None


class TestTranscriptionProgress:
    """Tests for the high-level TranscriptionProgress class."""

    def test_uses_null_tracker_when_not_verbose(self):
        """Should use NullProgressTracker when verbose=False."""
        progress = TranscriptionProgress(verbose=False)
        assert isinstance(progress._tracker, NullProgressTracker)

    def test_start_decode_returns_task_id(self):
        """start_decode should return a task ID."""
        progress = TranscriptionProgress(verbose=True)
        with progress:
            task_id = progress.start_decode()
            assert task_id is not None

    def test_complete_decode_marks_complete(self):
        """complete_decode should mark the task as complete."""
        progress = TranscriptionProgress(verbose=True)
        with progress:
            task_id = progress.start_decode()
            # Should not raise
            progress.complete_decode(task_id)

    def test_workflow_steps_complete_cycle(self):
        """All workflow step methods should work together."""
        progress = TranscriptionProgress(verbose=True)
        
        with progress:
            # Decode
            decode_task = progress.start_decode()
            progress.complete_decode(decode_task)
            
            # VAD
            vad_task = progress.start_vad()
            progress.complete_vad(vad_task, segment_count=5)
            
            # Condense
            condense_task = progress.start_condense()
            progress.complete_condense(condense_task, chunk_count=3)
            
            # Transcribe
            transcribe_task = progress.start_transcribe(chunk_count=3)
            progress.update_transcribe(transcribe_task, current=1, total=3)
            progress.update_transcribe(transcribe_task, current=2, total=3)
            progress.update_transcribe(transcribe_task, current=3, total=3)
            progress.complete_transcribe(transcribe_task)
            
            # Refine
            refine_task = progress.start_refine()
            progress.complete_refine(refine_task)
            
            # Success
            progress.success("All done!")

    def test_warning_method(self):
        """warning method should not raise."""
        progress = TranscriptionProgress(verbose=True)
        with progress:
            progress.warning("This is a warning")

    def test_error_method(self):
        """error method should not raise."""
        progress = TranscriptionProgress(verbose=True)
        with progress:
            progress.error("This is an error")


class TestTranscriptionProgressContextManager:
    """Tests for the transcription_progress context manager."""

    def test_context_manager_creates_progress(self):
        """Context manager should yield a TranscriptionProgress instance."""
        with transcription_progress(verbose=True) as progress:
            assert isinstance(progress, TranscriptionProgress)

    def test_context_manager_verbose_false(self):
        """Context manager should respect verbose=False."""
        with transcription_progress(verbose=False) as progress:
            assert isinstance(progress._tracker, NullProgressTracker)
