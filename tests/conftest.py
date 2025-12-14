"""
Pytest configuration and fixtures for Vociferous tests.
"""
import os
import sys
from contextlib import suppress

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture(scope="session", autouse=True)
def init_config():
    """Initialize ConfigManager once for all tests."""
    from utils import ConfigManager
    ConfigManager.initialize()
    yield ConfigManager


@pytest.fixture
def config_manager(init_config):
    """Provide ConfigManager instance."""
    return init_config


@pytest.fixture
def key_listener():
    """Create and yield a KeyListener, stopping it after test."""
    from key_listener import KeyListener
    kl = KeyListener()
    yield kl
    with suppress(Exception):
        kl.stop()
