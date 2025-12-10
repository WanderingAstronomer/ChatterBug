from __future__ import annotations

from pathlib import Path
from vociferous.domain.model import EngineConfig, TranscriptionOptions
from vociferous.engines.canary_qwen import CanaryQwenEngine


def _engine(use_mock: bool = True) -> CanaryQwenEngine:
    config = EngineConfig(
        model_name="nvidia/canary-qwen-2.5b",
        params={"mode": "asr", "use_mock": str(use_mock).lower()},
    )
    return CanaryQwenEngine(config)


def test_canary_qwen_mock_streaming() -> None:
    engine = _engine()
    engine.start(TranscriptionOptions(language="en"))
    engine.push_audio(b"\x00" * 32000, 0)  # ~1s of mono PCM16 at 16 kHz
    engine.flush()
    segments = engine.poll_segments()

    assert len(segments) == 1
    assert "Canary-Qwen" in segments[0].text
    assert segments[0].end_s > 0


def test_canary_qwen_transcribe_file(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio.raw"
    audio_path.write_bytes(b"\x01" * 64000)

    engine = _engine()
    segments = engine.transcribe_file(audio_path, TranscriptionOptions(language="en"))

    assert segments
    assert segments[0].text


def test_canary_qwen_refine_text() -> None:
    engine = _engine()
    refined = engine.refine_text("hello world")

    assert refined[0].isupper()
    assert refined.rstrip().endswith((".", "!", "?"))
