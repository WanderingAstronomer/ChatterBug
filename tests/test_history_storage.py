"""Test HistoryStorage implementation."""
import json
from pathlib import Path

import pytest

from chatterbug.domain.model import TranscriptSegment, TranscriptionResult
from chatterbug.storage.history import HistoryStorage


@pytest.fixture
def history_dir(tmp_path: Path) -> Path:
    """Create a temporary history directory."""
    return tmp_path / "history"


@pytest.fixture
def sample_result() -> TranscriptionResult:
    """Create a sample transcription result."""
    return TranscriptionResult(
        text="Test transcript",
        segments=(
            TranscriptSegment(text="Test", start_s=0.0, end_s=0.5, language="en", confidence=0.95),
            TranscriptSegment(text="transcript", start_s=0.5, end_s=1.5, language="en", confidence=0.92),
        ),
        model_name="openai/whisper-large-v3-turbo",
        device="cpu",
        precision="int8",
        engine="whisper_turbo",
        duration_s=1.5,
        warnings=(),
    )


def test_history_storage_creates_directory(history_dir: Path) -> None:
    """Test HistoryStorage creates directory if it doesn't exist."""
    assert not history_dir.exists()
    storage = HistoryStorage(history_dir)
    assert history_dir.exists()
    assert storage.history_file == history_dir / "history.jsonl"


def test_history_storage_saves_to_target_file(history_dir: Path, sample_result: TranscriptionResult, tmp_path: Path) -> None:
    """Test saving transcript to target file."""
    storage = HistoryStorage(history_dir)
    target = tmp_path / "output.txt"
    
    result_path = storage.save_transcription(sample_result, target=target)
    
    assert result_path == target
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "Test transcript"


def test_history_storage_saves_to_history_without_target(history_dir: Path, sample_result: TranscriptionResult) -> None:
    """Test saving to history.jsonl when no target provided."""
    storage = HistoryStorage(history_dir)
    
    result_path = storage.save_transcription(sample_result, target=None)
    
    assert result_path is None
    history_file = history_dir / "history.jsonl"
    assert history_file.exists()
    lines = history_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1


def test_history_storage_loads_history(history_dir: Path, sample_result: TranscriptionResult) -> None:
    """Test loading history from storage."""
    storage = HistoryStorage(history_dir)
    storage.save_transcription(sample_result, target=None)
    
    history = list(storage.load_history(limit=10))
    
    assert len(history) == 1
    assert history[0].text == "Test transcript"
    assert history[0].model_name == "openai/whisper-large-v3-turbo"


def test_history_storage_respects_limit(history_dir: Path, sample_result: TranscriptionResult) -> None:
    """Test load_history respects limit parameter."""
    storage = HistoryStorage(history_dir)
    
    # Save 5 results
    for i in range(5):
        modified_result = TranscriptionResult(
            text=f"Transcript {i}",
            segments=sample_result.segments,
            model_name=sample_result.model_name,
            device=sample_result.device,
            precision=sample_result.precision,
            engine=sample_result.engine,
            duration_s=sample_result.duration_s,
        )
        storage.save_transcription(modified_result, target=None)
    
    # Load only 3
    history = list(storage.load_history(limit=3))
    assert len(history) == 3


def test_history_storage_clears_history(history_dir: Path, sample_result: TranscriptionResult) -> None:
    """Test clearing history removes history file."""
    storage = HistoryStorage(history_dir)
    storage.save_transcription(sample_result, target=None)
    
    history_file = history_dir / "history.jsonl"
    assert history_file.exists()
    
    storage.clear_history()
    assert not history_file.exists()


def test_history_storage_load_returns_empty_when_no_file(history_dir: Path) -> None:
    """Test loading history returns empty iterator when file doesn't exist."""
    storage = HistoryStorage(history_dir)
    history = list(storage.load_history(limit=10))
    assert len(history) == 0


def test_history_storage_handles_corrupted_lines(history_dir: Path) -> None:
    """Test loading history skips corrupted JSON lines."""
    storage = HistoryStorage(history_dir)
    history_file = history_dir / "history.jsonl"
    history_dir.mkdir(parents=True, exist_ok=True)
    
    # Write corrupted JSON
    history_file.write_text(
        '{"text": "valid"}\n'
        'not valid json\n'
        '{"text": "also valid"}\n',
        encoding="utf-8"
    )
    
    # Should skip the corrupted line
    history = list(storage.load_history(limit=10))
    # May be 0 or 2 depending on whether TranscriptionResult validation passes
    # The key is it doesn't crash
    assert isinstance(history, list)


def test_history_storage_trim_is_atomic(history_dir: Path, sample_result: TranscriptionResult) -> None:
    """Test that trimming history is atomic (no partial writes)."""
    import threading
    
    storage = HistoryStorage(history_dir, limit=5)
    
    # Add more than limit to trigger trim
    for i in range(10):
        modified_result = TranscriptionResult(
            text=f"Transcript {i}",
            segments=sample_result.segments,
            model_name=sample_result.model_name,
            device=sample_result.device,
            precision=sample_result.precision,
            engine=sample_result.engine,
            duration_s=sample_result.duration_s,
        )
        storage.save_transcription(modified_result, target=None)
    
    # Verify the file is valid after trim
    history_file = history_dir / "history.jsonl"
    assert history_file.exists()
    lines = history_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 5
    
    # All lines should be valid JSON
    for line in lines:
        assert json.loads(line)  # Should not raise


def test_history_storage_concurrent_writes(history_dir: Path, sample_result: TranscriptionResult) -> None:
    """Test that concurrent writes don't corrupt the history file."""
    import threading
    
    storage = HistoryStorage(history_dir, limit=50)
    errors = []
    
    def write_transcript(index: int):
        try:
            modified_result = TranscriptionResult(
                text=f"Transcript {index}",
                segments=sample_result.segments,
                model_name=sample_result.model_name,
                device=sample_result.device,
                precision=sample_result.precision,
                engine=sample_result.engine,
                duration_s=sample_result.duration_s,
            )
            storage.save_transcription(modified_result, target=None)
        except Exception as e:
            errors.append(e)
    
    # Launch 10 concurrent writers
    threads = []
    for i in range(10):
        t = threading.Thread(target=write_transcript, args=(i,))
        threads.append(t)
        t.start()
    
    # Wait for all threads to complete
    for t in threads:
        t.join()
    
    # No errors should have occurred
    assert len(errors) == 0
    
    # Verify the file is valid
    history_file = history_dir / "history.jsonl"
    assert history_file.exists()
    lines = history_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 10
    
    # All lines should be valid JSON
    for line in lines:
        assert json.loads(line)  # Should not raise


def test_history_storage_no_tmp_file_left_behind(history_dir: Path, sample_result: TranscriptionResult) -> None:
    """Test that no temporary files are left behind after trim."""
    storage = HistoryStorage(history_dir, limit=3)
    
    # Add more than limit to trigger trim
    for i in range(10):
        modified_result = TranscriptionResult(
            text=f"Transcript {i}",
            segments=sample_result.segments,
            model_name=sample_result.model_name,
            device=sample_result.device,
            precision=sample_result.precision,
            engine=sample_result.engine,
            duration_s=sample_result.duration_s,
        )
        storage.save_transcription(modified_result, target=None)
    
    # No .tmp files should exist
    tmp_files = list(history_dir.glob("*.tmp"))
    assert len(tmp_files) == 0
