"""CLI tests for non-transcribe commands and helper builders.

Transcribe-specific CLI coverage lives in tests/test_cli_transcribe.py to avoid duplication.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
from typer.testing import CliRunner
from unittest.mock import Mock

from vociferous.cli.main import app
from vociferous.cli.helpers import (
    build_transcribe_configs_from_cli,
    build_engine_config,
    build_polisher_config,
    resolve_preset,
    build_sink,
)
from vociferous.domain.model import DEFAULT_WHISPER_MODEL


class _FakeAppConfig:
    """Minimal fake AppConfig matching schema."""
    model_name: str = DEFAULT_WHISPER_MODEL
    engine: str = "whisper_turbo"
    compute_type: str = "auto"
    device: str = "auto"
    model_cache_dir: str = "/tmp/vociferous-model-cache"
    vllm_endpoint: str = "http://localhost:8000"
    chunk_ms: int = 960
    params: Dict[str, str] = {
        "enable_batching": "true",
        "batch_size": "16",
        "word_timestamps": "false",
        "vad_filter": "true",
    }
    history_dir: str = "/tmp/vociferous-history"
    history_limit: int = 20
    numexpr_max_threads: int | None = None
    polish_enabled: bool = False
    polish_model: str | None = None
    polish_params: Dict[str, str] = {
        "max_tokens": "128",
        "temperature": "0.2",
        "gpu_layers": "0",
        "context_length": "2048",
    }


# ============================================================================
# CHECK Command Tests
# ============================================================================


class TestCheckCommand:
    """Tests for the check command."""

    def test_check_success_all_deps_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/ffmpeg" if x == "ffmpeg" else None)

        import importlib.util

        def mock_find_spec(name: str) -> Any:
            if name == "sounddevice":
                return Mock()
            return None

        monkeypatch.setattr("importlib.util.find_spec", mock_find_spec)
        monkeypatch.setattr("vociferous.cli.main.load_config", lambda: _FakeAppConfig())

        result = CliRunner().invoke(app, ["check"])

        assert result.exit_code == 0
        assert "✅" in result.stdout or "All checks passed" in result.stdout

    def test_check_fails_missing_ffmpeg(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("shutil.which", lambda x: None)

        import importlib.util

        def mock_find_spec(name: str) -> Any:
            if name == "sounddevice":
                return Mock()
            return None

        monkeypatch.setattr("importlib.util.find_spec", mock_find_spec)
        monkeypatch.setattr("vociferous.cli.main.load_config", lambda: _FakeAppConfig())

        result = CliRunner().invoke(app, ["check"])

        assert result.exit_code == 1
        assert "ffmpeg" in result.stdout.lower() or "❌" in result.stdout

    def test_check_warns_missing_sounddevice(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/ffmpeg" if x == "ffmpeg" else None)

        import importlib.util

        def mock_find_spec(name: str) -> Any:
            return None

        monkeypatch.setattr("importlib.util.find_spec", mock_find_spec)
        monkeypatch.setattr("vociferous.cli.main.load_config", lambda: _FakeAppConfig())

        result = CliRunner().invoke(app, ["check"])

        assert result.exit_code == 1
        assert "sounddevice" in result.stdout.lower() or "⚠️" in result.stdout

    def test_check_verifies_model_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/ffmpeg" if x == "ffmpeg" else None)

        import importlib.util

        def mock_find_spec(name: str) -> Any:
            if name == "sounddevice":
                return Mock()
            return None

        monkeypatch.setattr("importlib.util.find_spec", mock_find_spec)

        config = _FakeAppConfig()
        config.model_cache_dir = str(tmp_path / "cache")
        (tmp_path / "cache").mkdir()

        monkeypatch.setattr("vociferous.cli.main.load_config", lambda: config)

        result = CliRunner().invoke(app, ["check"])

        assert result.exit_code == 0


# ============================================================================
# LANGUAGES Command Tests
# ============================================================================


class TestLanguagesCommand:
    """Tests for the languages command."""

    def test_languages_command_success(self) -> None:
        """Test that languages command runs successfully."""
        result = CliRunner().invoke(app, ["languages"])
        
        assert result.exit_code == 0
        assert "Whisper" in result.stdout
        assert "Voxtral" in result.stdout

    def test_languages_displays_whisper_languages(self) -> None:
        """Test that Whisper languages are displayed."""
        result = CliRunner().invoke(app, ["languages"])
        
        assert result.exit_code == 0
        # Check for some common languages
        assert "en" in result.stdout
        assert "English" in result.stdout
        assert "es" in result.stdout
        assert "Spanish" in result.stdout
        assert "fr" in result.stdout
        assert "French" in result.stdout
        assert "zh" in result.stdout
        assert "Chinese" in result.stdout

    def test_languages_displays_voxtral_core(self) -> None:
        """Test that Voxtral core languages are displayed."""
        result = CliRunner().invoke(app, ["languages"])
        
        assert result.exit_code == 0
        # Check for Voxtral core languages
        assert "Voxtral" in result.stdout
        assert "Core Languages" in result.stdout or "core" in result.stdout.lower()
        # At least some of the core languages should be there
        output_lower = result.stdout.lower()
        assert "english" in output_lower
        assert "spanish" in output_lower
        assert "french" in output_lower

    def test_languages_displays_usage_examples(self) -> None:
        """Test that usage examples are displayed."""
        result = CliRunner().invoke(app, ["languages"])
        
        assert result.exit_code == 0
        assert "Usage" in result.stdout or "usage" in result.stdout.lower()
        assert "vociferous transcribe" in result.stdout
        assert "-l" in result.stdout or "--language" in result.stdout
        assert "auto" in result.stdout

    def test_languages_shows_total_count(self) -> None:
        """Test that total language count is displayed."""
        result = CliRunner().invoke(app, ["languages"])
        
        assert result.exit_code == 0
        # Should show total count for Whisper (99 or 100 languages)
        assert "Total" in result.stdout or "total" in result.stdout.lower()


# ============================================================================
# CHECK_VLLM Command Tests
# ============================================================================


class TestCheckVLLMCommand:
    """Tests for the check-vllm command."""

    def test_check_vllm_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("vociferous.cli.main.load_config", lambda: _FakeAppConfig())

        import sys

        mock_models = Mock()
        mock_models.data = [Mock(id="openai/whisper-large-v3-turbo")]
        mock_client = Mock()
        mock_client.models.list.return_value = mock_models

        mock_openai_module = Mock()
        mock_openai_module.OpenAI.return_value = mock_client

        monkeypatch.setitem(sys.modules, "openai", mock_openai_module)

        result = CliRunner().invoke(app, ["check-vllm"])

        assert result.exit_code == 0
        assert "vLLM endpoint" in result.stdout or "Models" in result.stdout

    def test_check_vllm_with_custom_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("vociferous.cli.main.load_config", lambda: _FakeAppConfig())

        import sys

        mock_models = Mock()
        mock_models.data = [Mock(id="openai/whisper-large-v3")]
        mock_client = Mock()
        mock_client.models.list.return_value = mock_models

        mock_openai_module = Mock()
        mock_openai_module.OpenAI.return_value = mock_client

        monkeypatch.setitem(sys.modules, "openai", mock_openai_module)

        result = CliRunner().invoke(app, ["check-vllm", "--endpoint", "http://custom:9000"])

        assert result.exit_code == 0


# ============================================================================
# SERVE_VLLM Command Tests
# ============================================================================


class TestServeVLLMCommand:
    """Tests for the serve-vllm command."""

    def test_serve_vllm_missing_binary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("shutil.which", lambda x: None)

        result = CliRunner().invoke(app, ["serve-vllm"])

        assert result.exit_code == 1
        assert result.stdout or result.stderr

    def test_serve_vllm_success_with_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/vllm" if x == "vllm" else None)

        called_args: list[str] = []

        def mock_run(args: list[str], **kwargs: Any) -> None:
            called_args.extend(args)

        monkeypatch.setattr("subprocess.run", mock_run)

        result = CliRunner().invoke(app, ["serve-vllm"])

        assert result.exit_code == 0
        assert called_args  # ensure subprocess.run was invoked

    def test_serve_vllm_custom_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/vllm" if x == "vllm" else None)

        called_args: list[str] = []

        def mock_run(args: list[str], **kwargs: Any) -> None:
            called_args.extend(args)

        monkeypatch.setattr("subprocess.run", mock_run)

        result = CliRunner().invoke(
            app,
            [
                "serve-vllm",
                "--model",
                "openai/whisper-large-v3",
                "--dtype",
                "float16",
                "--port",
                "9000",
            ],
        )

        assert result.exit_code == 0
        assert any("whisper-large-v3" in arg for arg in called_args)
        assert "9000" in called_args

    def test_serve_vllm_propagates_return_code(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/vllm" if x == "vllm" else None)

        from subprocess import CalledProcessError

        def mock_run_error(args: list[str], **kwargs: Any) -> None:
            raise CalledProcessError(returncode=42, cmd=args)

        monkeypatch.setattr("subprocess.run", mock_run_error)

        result = CliRunner().invoke(app, ["serve-vllm"])

        assert result.exit_code == 42


# ============================================================================
# HELPERS: Preset Resolution
# ============================================================================


class TestPresetResolution:
    """Tests for resolve_preset helper."""

    def test_resolve_preset_fast_whisper_turbo(self) -> None:
        settings = resolve_preset("fast", "whisper_turbo", "auto")

        model_lower = settings.model.lower() if settings.model else ""
        assert "turbo" in model_lower
        assert settings.beam_size == 1
        assert settings.batch_size >= 16
        assert settings.enable_batching is True

    def test_resolve_preset_balanced_whisper_turbo(self) -> None:
        settings = resolve_preset("balanced", "whisper_turbo", "auto")

        model_lower = settings.model.lower() if settings.model else ""
        assert "turbo" in model_lower
        assert settings.beam_size >= 1
        assert settings.batch_size >= 12
        assert settings.enable_batching is True

    def test_resolve_preset_high_accuracy_whisper_turbo(self) -> None:
        settings = resolve_preset("high_accuracy", "whisper_turbo", "auto")

        model_lower = settings.model.lower() if settings.model else ""
        assert "large" in model_lower
        assert settings.beam_size >= 2
        assert settings.batch_size >= 8
        assert settings.enable_batching is True

    def test_resolve_preset_fast_whisper_vllm(self) -> None:
        settings = resolve_preset("fast", "whisper_vllm", "auto")

        model_lower = settings.model.lower() if settings.model else ""
        assert "turbo" in model_lower
        assert settings.beam_size == 1

    def test_resolve_preset_high_accuracy_whisper_vllm(self) -> None:
        settings = resolve_preset("high_accuracy", "whisper_vllm", "auto")

        model_lower = settings.model.lower() if settings.model else ""
        assert "large" in model_lower and "turbo" not in model_lower
        assert settings.beam_size == 2

    def test_resolve_preset_respects_device_cpu(self) -> None:
        settings = resolve_preset("balanced", "whisper_turbo", "cpu")

        assert settings.compute_type is not None

    def test_resolve_preset_respects_device_cuda(self) -> None:
        settings = resolve_preset("balanced", "whisper_turbo", "cuda")

        assert settings.compute_type is not None


# ============================================================================
# HELPERS: Model Registry & Normalization
# ============================================================================


class TestModelNormalization:
    """Tests for build_engine_config helper."""

    def test_build_engine_config_normalizes_model(self) -> None:
        cfg = build_engine_config(
            "whisper_turbo",
            model_name="turbo",
            compute_type="auto",
            device="auto",
            model_cache_dir="/tmp/cache",
            params={},
        )

        model_lower = cfg.model_name.lower() if cfg.model_name else ""
        assert "turbo" in model_lower or "large" in model_lower

    def test_build_engine_config_handles_none_model(self) -> None:
        cfg = build_engine_config(
            "whisper_turbo",
            model_name=None,
            compute_type="auto",
            device="auto",
            model_cache_dir="/tmp/cache",
            params={},
        )

        assert cfg.model_name == DEFAULT_WHISPER_MODEL

    def test_build_engine_config_sanitizes_params(self) -> None:
        cfg = build_engine_config(
            "whisper_turbo",
            model_name="test",
            compute_type="",
            device="auto",
            model_cache_dir="/tmp",
            params={"some_param": ""},
        )

        assert cfg.compute_type == "auto"
        assert "some_param" not in cfg.params


# ============================================================================
# HELPERS: Config Building
# ============================================================================


class TestBuildTranscribeConfigs:
    """Tests for build_transcribe_configs_from_cli helper."""

    def test_build_configs_basic(self) -> None:
        config = _FakeAppConfig()

        bundle = build_transcribe_configs_from_cli(
            app_config=config,  # type: ignore[arg-type]
            engine="whisper_turbo",
            language="en",
            preset=None,
        )

        assert bundle.engine_config.model_name is not None
        assert bundle.options.language == "en"
        assert bundle.options.preset is None

    def test_build_configs_with_preset(self) -> None:
        config = _FakeAppConfig()

        bundle = build_transcribe_configs_from_cli(
            app_config=config,  # type: ignore[arg-type]
            engine="whisper_turbo",
            language="en",
            preset="high_accuracy",
        )

        assert bundle.options.preset == "high_accuracy"
        assert bundle.preset == "high_accuracy"
        model_lower = bundle.engine_config.model_name.lower() if bundle.engine_config.model_name else ""
        assert "large" in model_lower

    def test_build_configs_vllm_defaults_balanced(self) -> None:
        config = _FakeAppConfig()

        bundle = build_transcribe_configs_from_cli(
            app_config=config,  # type: ignore[arg-type]
            engine="whisper_vllm",
            language="en",
            preset=None,
        )

        assert bundle.preset == "balanced"

    def test_build_configs_preserves_config_params(self) -> None:
        config = _FakeAppConfig()
        config.params["custom_param"] = "custom_value"

        bundle = build_transcribe_configs_from_cli(
            app_config=config,  # type: ignore[arg-type]
            engine="whisper_turbo",
            language="en",
            preset=None,
        )

        assert bundle.engine_config.params["custom_param"] == "custom_value"

    def test_build_configs_adds_clean_disfluencies(self) -> None:
        config = _FakeAppConfig()

        bundle = build_transcribe_configs_from_cli(
            app_config=config,  # type: ignore[arg-type]
            engine="whisper_turbo",
            language="en",
            preset=None,
        )

        assert bundle.engine_config.params["clean_disfluencies"] == "true"


# ============================================================================
# HELPERS: Polisher Config
# ============================================================================


class TestBuildPolisherConfig:
    """Tests for build_polisher_config helper."""

    def test_build_polisher_config_disabled(self) -> None:
        cfg = build_polisher_config(enabled=False, model=None, base_params={})

        assert cfg.enabled is False

    def test_build_polisher_config_enabled(self) -> None:
        cfg = build_polisher_config(
            enabled=True,
            model="test-model",
            base_params={},
            max_tokens=256,
        )

        assert cfg.enabled is True
        assert cfg.model == "test-model"
        assert cfg.params["max_tokens"] == "256"

    def test_build_polisher_config_custom_temperature(self) -> None:
        cfg = build_polisher_config(
            enabled=True,
            model="test-model",
            base_params={},
            temperature=0.7,
        )

        temp_val = cfg.params.get("temperature") if cfg.params else None
        assert temp_val is not None and float(temp_val) == 0.7

    def test_build_polisher_config_with_gpu_layers(self) -> None:
        cfg = build_polisher_config(
            enabled=True,
            model="test",
            base_params={},
            gpu_layers=50,
        )

        assert int(cfg.params["gpu_layers"]) == 50


# ============================================================================
# HELPERS: Sink Building
# ============================================================================


class TestBuildSink:
    """Tests for build_sink helper."""

    def test_build_sink_stdout(self) -> None:
        sink = build_sink(output=None)

        from vociferous.app.sinks import StdoutSink

        assert isinstance(sink, StdoutSink)

    def test_build_sink_file(self, tmp_path: Path) -> None:
        output_file = tmp_path / "transcript.txt"
        sink = build_sink(output=output_file)

        from vociferous.app.sinks import FileSink

        assert isinstance(sink, FileSink)
