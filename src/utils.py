"""
Configuration Management Module.

Thread-safe singleton ConfigManager using double-checked locking.
Schema-driven configuration with YAML validation and hot reloading.
"""
import logging
import threading
from contextlib import suppress
from pathlib import Path
from typing import Any

import yaml
from PyQt5.QtCore import QObject, pyqtSignal

_DEFAULT_CONFIG_PATH = Path('src') / 'config.yaml'
_SCHEMA_FILENAME = 'config_schema.yaml'

logger = logging.getLogger(__name__)


class ConfigManager(QObject):
    """Thread-safe singleton configuration manager with PyQt signals."""

    # Class-level attributes shared by all instances (though only one exists)
    # The type hint 'ConfigManager | None' uses Python 3.10+ union syntax
    _instance: 'ConfigManager | None' = None
    _lock = threading.Lock()

    configChanged = pyqtSignal(str, str, object)
    configReloaded = pyqtSignal()

    def __init__(self) -> None:
        """Initialize the ConfigManager instance."""
        super().__init__()
        self.config: dict[str, Any] = {}
        self.schema: dict[str, Any] = {}
        self._print_enabled: bool = True

    @classmethod
    def initialize(cls, schema_path: Path | str | None = None) -> None:
        """Initialize the ConfigManager singleton with double-checked locking."""
        if cls._instance is None:
            with cls._lock:
                # Double-check pattern for thread safety
                if cls._instance is None:
                    instance = cls()
                    instance.schema = instance.load_config_schema(schema_path)
                    instance.config = instance.load_default_config()
                    instance.load_user_config()
                    cls._instance = instance

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        """Get the configuration schema."""
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")
        return cls._instance.schema

    @classmethod
    def instance(cls) -> 'ConfigManager':
        """Return the initialized ConfigManager instance."""
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")
        return cls._instance

    @classmethod
    def get_config_section(cls, *keys: str) -> dict[str, Any]:
        """Navigate through nested config dictionaries to get a section."""
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")

        section: Any = cls._instance.config
        for key in keys:
            match section:
                case dict() if key in section:
                    section = section[key]
                case _:
                    return {}
        return section

    @classmethod
    def get_config_value(cls, *keys: str) -> Any:
        """Get a specific configuration value using nested keys."""
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")

        value: Any = cls._instance.config
        for key in keys:
            match value:
                case dict() if key in value:
                    value = value[key]
                case _:
                    return None
        return value

    @classmethod
    def set_config_value(cls, value: Any, *keys: str) -> None:
        """Set a nested configuration value, creating intermediate dicts as needed."""
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")
        if not keys:
            raise ValueError("At least one key required")

        with cls._lock:
            config = cls._instance.config
            for key in keys[:-1]:
                match config.get(key):
                    case dict() as nested:
                        config = nested
                    case _:
                        config[key] = {}
                        config = config[key]
            config[keys[-1]] = value

        # Emit after releasing the lock to avoid deadlocks
        if keys:
            section = keys[0]
            leaf_key = keys[-1]
            cls._instance.configChanged.emit(section, leaf_key, value)

    @staticmethod
    def load_config_schema(schema_path: Path | str | None = None) -> dict[str, Any]:
        """Load the configuration schema from a YAML file."""
        if schema_path is None:
            schema_path = Path(__file__).parent / _SCHEMA_FILENAME
        else:
            schema_path = Path(schema_path)

        return yaml.safe_load(schema_path.read_text())

    def load_default_config(self) -> dict[str, Any]:
        """Extract default values from the schema using recursive pattern matching."""
        def extract_value(item: Any) -> Any:
            match item:
                case {'value': val}:
                    return val
                case dict():
                    return {k: extract_value(v) for k, v in item.items()}
                case _:
                    return item

        return {
            category: extract_value(settings)
            for category, settings in self.schema.items()
        }

    def load_user_config(self, config_path: Path | str | None = None) -> None:
        """Load and merge user configuration with defaults (deep merge)."""
        path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH

        def deep_update(source: dict, overrides: dict) -> None:
            for key, value in overrides.items():
                match (source.get(key), value):
                    case (dict() as existing, dict()):
                        deep_update(existing, value)
                    case _:
                        source[key] = value

        if path.is_file():
            with suppress(yaml.YAMLError):
                user_config = yaml.safe_load(path.read_text())
                if user_config:
                    deep_update(self.config, user_config)

    @classmethod
    def save_config(cls, config_path: Path | str | None = None) -> None:
        """Save the current configuration to a YAML file."""
        path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")
        path.write_text(yaml.dump(cls._instance.config, default_flow_style=False))

    @classmethod
    def reload_config(cls) -> None:
        """Reload the configuration from the file."""
        if cls._instance is None:
            raise RuntimeError("ConfigManager not initialized")
        cls._instance.config = cls._instance.load_default_config()
        cls._instance.load_user_config()
        cls._instance.configReloaded.emit()

    @classmethod
    def config_file_exists(cls) -> bool:
        """Check if a valid config file exists."""
        return _DEFAULT_CONFIG_PATH.is_file()

    @classmethod
    def console_print(cls, message: str) -> None:
        """Log a message if console output is enabled."""
        if not cls._instance:
            return
        print_enabled = cls._instance.config.get('output_options', {}).get(
            'print_to_terminal', True
        )
        if print_enabled:
            logger.info(message)
