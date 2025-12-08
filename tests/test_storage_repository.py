"""Tests for FileSystemStorage delegating to HistoryStorage."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vociferous.app.sinks.sinks import HistorySink
from vociferous.domain.model import TranscriptSegment, TranscriptionResult
from vociferous.storage.repository import FileSystemStorage


@pytest.fixture
def sample_result() -> TranscriptionResult:
    return TranscriptionResult(
        text="Hello history",
        segments=(
            TranscriptSegment(text="Hello", start_s=0.0, end_s=0.5, language="en", confidence=0.9),
            TranscriptSegment(text="history", start_s=0.5, end_s=1.0, language="en", confidence=0.9),
        ),
        model_name="openai/whisper-large-v3-turbo",
        device="cpu",
        precision="int8",
        engine="whisper_turbo",
        duration_s=1.0,
        warnings=(),
    )


def test_filesystem_storage_persists_history(tmp_path: Path, sample_result: TranscriptionResult) -> None:
    storage = FileSystemStorage(tmp_path)

    storage.save_transcription(sample_result, target=None)
    history = list(storage.load_history(limit=5))

    assert len(history) == 1
    assert history[0].text == "Hello history"


def test_filesystem_storage_respects_target(tmp_path: Path, sample_result: TranscriptionResult) -> None:
    storage = FileSystemStorage(tmp_path)
    target = tmp_path / "out.txt"

    saved_path = storage.save_transcription(sample_result, target=target)

    assert saved_path == target
    assert target.read_text(encoding="utf-8") == "Hello history"


def test_history_sink_passes_target_to_storage(sample_result: TranscriptionResult, tmp_path: Path) -> None:
    storage = MagicMock(spec=FileSystemStorage)
    target = tmp_path / "note.txt"
    sink = HistorySink(storage, target=target)

    for segment in sample_result.segments:
        sink.handle_segment(segment)

    sink.complete(sample_result)

    storage.save_transcription.assert_called_once_with(sample_result, target=target)
    assert len(sink._segments) == len(sample_result.segments)
