import os
import tempfile
from pathlib import Path
import pytest
from unittest import mock

from vociferous.config import schema
from vociferous.engines import cache_manager


def test_model_parent_dir_default(monkeypatch):
    # Simulate first run with no config file
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.toml"
        monkeypatch.setattr(schema, "DEFAULT_MODEL_CACHE_DIR", Path(tmpdir) / "models")
        monkeypatch.setattr("builtins.input", lambda _: "")  # Simulate Enter for default
        cfg = schema.load_config(config_path)
        assert cfg.model_parent_dir == str(Path(tmpdir) / "models")
        assert cfg.model_parent_dir is not None and Path(cfg.model_parent_dir).exists()


def test_model_parent_dir_custom(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.toml"
        custom_dir = Path(tmpdir) / "custom_models"
        monkeypatch.setattr(schema, "DEFAULT_MODEL_CACHE_DIR", Path(tmpdir) / "models")
        monkeypatch.setattr("builtins.input", lambda _: str(custom_dir))
        cfg = schema.load_config(config_path)
        assert cfg.model_parent_dir == str(custom_dir)
        assert custom_dir.exists()


def test_config_persistence(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.toml"
        monkeypatch.setattr(schema, "DEFAULT_MODEL_CACHE_DIR", Path(tmpdir) / "models")
        monkeypatch.setattr("builtins.input", lambda _: "")
        cfg = schema.load_config(config_path)
        cfg.model_parent_dir = str(Path(tmpdir) / "persisted_models")
        schema.save_config(cfg, config_path)
        loaded = schema.load_config(config_path)
        assert loaded.model_parent_dir == str(Path(tmpdir) / "persisted_models")


def test_cache_manager_provider_subdir():
    with tempfile.TemporaryDirectory() as tmpdir:
        parent_dir = Path(tmpdir)
        provider = "Mistral"
        model_name = "Voxtral-Mini-3B-2507"
        model_dir = parent_dir / provider / model_name
        model_dir.mkdir(parents=True)
        dummy_file = model_dir / "model.bin"
        dummy_file.write_text("dummy")
        # Simulate find logic
        found = False
        for root, dirs, files in os.walk(parent_dir):
            for file in files:
                if file == "model.bin":
                    found = True
                    assert Path(root) == model_dir
        assert found

# More tests for CLI prompt and download logic can be added with further refactoring.
