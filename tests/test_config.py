from vociferous.config.schema import AppConfig


def test_app_config_defaults_params() -> None:
    cfg = AppConfig()
    assert cfg.params["enable_batching"] == "false"
    assert cfg.params["batch_size"] == "1"
    assert cfg.params["word_timestamps"] == "false"


def test_app_config_polish_defaults() -> None:
    cfg = AppConfig()
    assert cfg.polish_enabled is False
    assert cfg.polish_model == "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    assert cfg.polish_params["repo_id"] == "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
    assert cfg.polish_params["max_tokens"] == "128"


def test_app_config_numexpr_default() -> None:
    cfg = AppConfig()
    assert cfg.numexpr_max_threads is None


def test_app_config_validates_model_parent_dir() -> None:
    """Test model_parent_dir validation and expansion."""
    # Should expand user path
    cfg = AppConfig(model_parent_dir="~/models")
    assert cfg.model_parent_dir is not None
    assert str(cfg.model_parent_dir).startswith("/")  # Absolute path
    assert "models" in str(cfg.model_parent_dir)

    # Should reject empty string
    import pytest
    with pytest.raises(ValueError, match="model_parent_dir must be set"):
        AppConfig(model_parent_dir="")
