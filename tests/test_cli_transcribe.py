"""CLI integration tests for transcribe command with simplified signature."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch
import os

import pytest
from typer.testing import CliRunner

from vociferous.cli.main import app
from vociferous.domain.exceptions import ConfigurationError, DependencyError, EngineError
from vociferous.domain.model import DEFAULT_WHISPER_MODEL


class _FakeConfig:
    model_name = DEFAULT_WHISPER_MODEL
    engine = "whisper_turbo"
    compute_type = "auto"
    device = "auto"
    model_cache_dir = "/tmp/vociferous-model-cache"
    chunk_ms = 960
    params: Dict[str, str] = {
        "enable_batching": "true",
        "batch_size": "16",
        "word_timestamps": "false",
        "vad_filter": "true",
    }
    history_dir = "/tmp/vociferous-history"
    history_limit = 20
    numexpr_max_threads = None
    polish_enabled = False
    polish_model = None
    polish_params: Dict[str, str] = {
        "max_tokens": "128",
        "temperature": "0.2",
        "gpu_layers": "0",
        "context_length": "2048",
    }


def _setup_cli_fixtures(
    monkeypatch: pytest.MonkeyPatch, config: Any | None = None
) -> Dict[str, Any]:
    calls: Dict[str, Any] = {}
    fake_engine = object()

    def fake_build_engine(kind: str, cfg: Any) -> object:
        calls["engine_kind"] = kind
        calls["engine_config"] = cfg
        return fake_engine

    class FakeFileSource:
        def __init__(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - trivial capture
            calls["file_source_args"] = (args, kwargs)

    class FakeSession:
        def __init__(self) -> None:
            calls["session_init"] = True

        def start(
            self,
            source: Any,
            engine_adapter: Any,
            sink: Any,
            options: Any,
            engine_kind: str,
            polisher: Any = None,
        ) -> None:
            calls["start_args"] = (source, engine_adapter, sink, options, engine_kind, polisher)

        def join(self) -> None:
            calls["join_called"] = True

    monkeypatch.setattr("vociferous.cli.main.load_config", lambda: config or _FakeConfig())
    monkeypatch.setattr("vociferous.cli.main.build_engine", fake_build_engine)
    monkeypatch.setattr("vociferous.cli.main.FileSource", FakeFileSource)
    monkeypatch.setattr("vociferous.cli.main.build_polisher", lambda cfg: None)
    monkeypatch.setattr("vociferous.cli.main.TranscriptionSession", FakeSession)

    return calls


def test_cli_transcribe_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Basic transcription uses config defaults."""
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(app, ["transcribe", str(audio), "--polish"])

    assert result.exit_code == 0
    cfg = calls["engine_config"]
    assert cfg.params["enable_batching"] == "true"
    assert cfg.params["batch_size"] == "16"
    assert cfg.params["word_timestamps"] == "false"
    assert cfg.params["vad_filter"] == "true"
    assert cfg.params["clean_disfluencies"] == "true"
    assert calls["engine_kind"] == "whisper_turbo"


@pytest.mark.parametrize(
    ("args", "expected_engine"),
    [
        (["--engine", "voxtral_local"], "voxtral_local"),
        (["-e", "voxtral_local"], "voxtral_local"),
    ],
)
def test_cli_transcribe_engine_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str], expected_engine: str
) -> None:
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(app, ["transcribe", str(audio), *args])

    assert result.exit_code == 0
    assert calls["engine_kind"] == expected_engine


@pytest.mark.parametrize(
    ("args", "language"),
    [
        (["--language", "en"], "en"),
        (["--language", "es"], "es"),
        (["--language", "fr"], "fr"),
        (["--language", "de"], "de"),
        (["--language", "it"], "it"),
        (["--language", "ja"], "ja"),
        (["--language", "zh"], "zh"),
        (["--language", "auto"], "auto"),
        (["-l", "es"], "es"),
    ],
)
def test_cli_transcribe_languages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str], language: str
) -> None:
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(app, ["transcribe", str(audio), *args])

    assert result.exit_code == 0
    options = calls["start_args"][3]
    assert options.language == language


@pytest.mark.parametrize(
    ("args", "preset", "model_hint", "beam_size"),
    [
        (["--preset", "fast"], "fast", "turbo", 1),
        (["--preset", "high_accuracy"], "high_accuracy", "large", 2),
        (["-p", "high_accuracy"], "high_accuracy", "large", 2),
    ],
)
def test_cli_transcribe_presets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    args: list[str],
    preset: str,
    model_hint: str,
    beam_size: int,
) -> None:
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    result = CliRunner().invoke(app, ["transcribe", str(audio), *args])

    assert result.exit_code == 0
    cfg = calls["engine_config"]
    assert cfg.params["preset"] == preset
    assert model_hint in cfg.model_name.lower()
    options = calls["start_args"][3]
    assert options.preset == preset
    assert options.beam_size == beam_size


@pytest.mark.parametrize("output_flag", ["-o", "--output"])
def test_cli_transcribe_output_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output_flag: str
) -> None:
    _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")
    output_file = tmp_path / "out.txt"

    result = CliRunner().invoke(
        app,
        ["transcribe", str(audio), output_flag, str(output_file)],
    )

    assert result.exit_code == 0


def test_cli_transcribe_file_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing files return exit code 2 with a helpful message."""
    _setup_cli_fixtures(monkeypatch)
    missing = tmp_path / "missing.wav"

    result = CliRunner().invoke(app, ["transcribe", str(missing)])

    assert result.exit_code == 2
    assert "not found" in result.stdout.lower()


def test_cli_transcribe_rejects_directory_as_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_cli_fixtures(monkeypatch)
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    result = CliRunner().invoke(app, ["transcribe", str(audio_dir)])

    assert result.exit_code == 2
    assert "directory" in result.stdout.lower()


def test_cli_transcribe_rejects_output_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    result = CliRunner().invoke(app, ["transcribe", str(audio), "-o", str(output_dir)])

    assert result.exit_code == 2
    assert "directory" in result.stdout.lower()


def test_cli_transcribe_engine_error_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    class FailingSession:
        def __init__(self) -> None:
            pass

        def start(self, *args: Any, **kwargs: Any) -> None:
            return None

        def join(self) -> None:
            raise EngineError("Engine inference failed")

    monkeypatch.setattr("vociferous.cli.main.TranscriptionSession", FailingSession)

    result = CliRunner().invoke(app, ["transcribe", str(audio)])

    assert result.exit_code == 4


def test_cli_transcribe_dependency_error_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    def failing_build_engine(*args: Any, **kwargs: Any) -> None:
        raise DependencyError("Required package not installed")

    monkeypatch.setattr("vociferous.cli.main.build_engine", failing_build_engine)

    result = CliRunner().invoke(app, ["transcribe", str(audio)])

    assert result.exit_code == 3


def test_cli_transcribe_configuration_error_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    def failing_build_polisher(*args: Any, **kwargs: Any) -> None:
        raise ConfigurationError("Bad polisher config")

    monkeypatch.setattr("vociferous.cli.main.build_polisher", failing_build_polisher)

    result = CliRunner().invoke(app, ["transcribe", str(audio), "--polish"])

    assert result.exit_code == 2


def test_cli_transcribe_sets_numexpr_threads_from_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_config = _FakeConfig()
    base_config.numexpr_max_threads = 8
    _setup_cli_fixtures(monkeypatch, config=base_config)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    with patch.dict("os.environ", {}, clear=False):
        result = CliRunner().invoke(app, ["transcribe", str(audio)])
        assert os.environ["NUMEXPR_MAX_THREADS"] == "8"

    assert result.exit_code == 0


def test_cli_transcribe_all_flags_together(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")
    output_file = tmp_path / "out.txt"

    result = CliRunner().invoke(
        app,
        [
            "transcribe",
            str(audio),
            "--engine",
            "voxtral_local",
            "--language",
            "es",
            "--preset",
            "high_accuracy",
            "--output",
            str(output_file),
        ],
    )

    assert result.exit_code == 0
    assert calls["engine_kind"] == "voxtral_local"
    options = calls["start_args"][3]
    assert options.language == "es"
    assert options.preset == "high_accuracy"


def test_cli_transcribe_skips_polisher_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    def failing_polisher(cfg: Any) -> object:
        calls["polisher_called"] = cfg
        raise AssertionError("polisher should not be built when disabled")

    monkeypatch.setattr("vociferous.cli.main.build_polisher", failing_polisher)
    monkeypatch.setattr(
        "vociferous.cli.main.PolishingSink",
        lambda inner, polisher: (_ for _ in ()).throw(AssertionError("polisher sink should not be used")),
    )

    result = CliRunner().invoke(app, ["transcribe", str(audio)])

    assert result.exit_code == 0
    assert "polisher_called" not in calls


def test_cli_transcribe_polish_flag_wraps_sink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _setup_cli_fixtures(monkeypatch)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    def fake_polisher(cfg: Any) -> object:
        calls["polisher_config"] = cfg
        return "POLISHER"

    def fake_polishing_sink(inner: Any, polisher: Any) -> str:
        calls["polishing_sink_args"] = (inner, polisher)
        return "WRAPPED_SINK"

    monkeypatch.setattr("vociferous.cli.main.build_polisher", fake_polisher)
    monkeypatch.setattr("vociferous.cli.main.PolishingSink", fake_polishing_sink)

    result = CliRunner().invoke(app, ["transcribe", str(audio), "--polish"])

    assert result.exit_code == 0
    assert calls["polisher_config"].enabled is True
    assert calls["polishing_sink_args"][1] == "POLISHER"
    assert calls["start_args"][2] == "WRAPPED_SINK"


def test_cli_transcribe_no_polish_overrides_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _FakeConfig()
    config.polish_enabled = True
    calls = _setup_cli_fixtures(monkeypatch, config=config)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"data")

    def failing_polisher(cfg: Any) -> object:
        calls["polisher_called"] = cfg
        raise AssertionError("polisher should be skipped when --no-polish is set")

    monkeypatch.setattr("vociferous.cli.main.build_polisher", failing_polisher)
    monkeypatch.setattr(
        "vociferous.cli.main.PolishingSink",
        lambda inner, polisher: (_ for _ in ()).throw(AssertionError("polisher sink should not be used")),
    )

    result = CliRunner().invoke(app, ["transcribe", str(audio), "--no-polish"])

    assert result.exit_code == 0
    assert "polisher_called" not in calls
