"""
Tests for configuration loading and management.
"""


class TestConfigManager:
    """Tests for ConfigManager functionality."""

    def test_config_initialized(self, config_manager):
        """Config should be initialized."""
        assert config_manager._instance is not None
        assert config_manager._instance.config is not None

    def test_get_model_options(self, config_manager):
        """Should retrieve model options."""
        model = config_manager.get_config_value('model_options', 'model')
        assert model is not None
        assert isinstance(model, str)

    def test_get_activation_key(self, config_manager):
        """Should retrieve activation key."""
        key = config_manager.get_config_value('recording_options', 'activation_key')
        assert key is not None
        # Value depends on user config, just verify it's a non-empty string
        assert isinstance(key, str) and len(key) > 0

    def test_get_recording_mode(self, config_manager):
        """Should retrieve recording mode."""
        mode = config_manager.get_config_value('recording_options', 'recording_mode')
        assert mode == 'press_to_toggle'

    def test_get_input_method(self, config_manager):
        """Should retrieve input method."""
        method = config_manager.get_config_value('output_options', 'input_method')
        assert method in ['pynput', 'ydotool', 'dotool', 'auto']

    def test_get_nonexistent_key_returns_none(self, config_manager):
        """Non-existent keys should return None."""
        value = config_manager.get_config_value('nonexistent', 'key')
        assert value is None

    def test_get_config_section(self, config_manager):
        """Should retrieve entire config sections."""
        model_opts = config_manager.get_config_section('model_options')
        assert isinstance(model_opts, dict)
        assert 'model' in model_opts
        assert 'device' in model_opts
