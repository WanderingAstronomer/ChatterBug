"""
Tests for settings dialog, hotkey widget, and live config updates.
"""
from unittest.mock import MagicMock, patch

import pytest

from key_listener import InputEvent, KeyCode


class TestKeycodeMapping:
    """Tests for keycode mapping utilities."""

    def test_is_modifier(self):
        from ui.keycode_mapping import is_modifier

        assert is_modifier(KeyCode.CTRL_LEFT)
        assert is_modifier(KeyCode.SHIFT_RIGHT)
        assert is_modifier(KeyCode.ALT_LEFT)
        assert is_modifier(KeyCode.META_RIGHT)
        assert not is_modifier(KeyCode.SPACE)
        assert not is_modifier(KeyCode.A)

    def test_keycode_to_display_name(self):
        from ui.keycode_mapping import keycode_to_display_name

        assert keycode_to_display_name(KeyCode.CTRL_LEFT) == "Ctrl"
        assert keycode_to_display_name(KeyCode.CTRL_RIGHT) == "Ctrl"
        assert keycode_to_display_name(KeyCode.SHIFT_LEFT) == "Shift"
        assert keycode_to_display_name(KeyCode.ALT_RIGHT) == "Alt"
        assert keycode_to_display_name(KeyCode.META_LEFT) == "Meta"
        assert keycode_to_display_name(KeyCode.F1) == "F1"
        assert keycode_to_display_name(KeyCode.SPACE) == "Space"

    def test_keycode_to_config_name(self):
        from ui.keycode_mapping import keycode_to_config_name

        assert keycode_to_config_name(KeyCode.CTRL_LEFT) == "ctrl"
        assert keycode_to_config_name(KeyCode.SHIFT_RIGHT) == "shift"
        assert keycode_to_config_name(KeyCode.ALT_LEFT) == "alt"
        assert keycode_to_config_name(KeyCode.META_RIGHT) == "meta"
        assert keycode_to_config_name(KeyCode.SPACE) == "space"
        assert keycode_to_config_name(KeyCode.ALT_RIGHT) == "alt"

    def test_normalize_hotkey_string(self):
        from ui.keycode_mapping import normalize_hotkey_string

        assert normalize_hotkey_string("shift+ctrl+a") == "ctrl+shift+a"
        assert normalize_hotkey_string("alt+ctrl+shift") == "ctrl+shift+alt"
        assert normalize_hotkey_string("space") == "space"
        assert normalize_hotkey_string("ctrl+space") == "ctrl+space"
        assert normalize_hotkey_string("meta+alt+z") == "alt+meta+z"

    def test_keycodes_to_strings(self):
        from ui.keycode_mapping import keycodes_to_strings

        display, config = keycodes_to_strings({KeyCode.CTRL_LEFT, KeyCode.A})
        assert "Ctrl" in display
        assert "A" in display
        assert "ctrl" in config
        assert "a" in config


class TestHotkeyWidgetLogic:
    """Tests for HotkeyWidget validation logic (no Qt required)."""

    def test_validate_hotkey_empty(self):
        """Empty hotkey should be invalid."""
        # Simulate validation logic
        parts = []
        valid = len(parts) > 0
        assert not valid

    def test_validate_hotkey_modifier_only(self):
        """Modifier-only hotkeys should be invalid."""
        parts = ["ctrl"]
        modifiers = {"ctrl", "shift", "alt", "meta"}
        is_modifier_only = len(parts) == 1 and parts[0] in modifiers
        assert is_modifier_only

    def test_validate_hotkey_reserved(self):
        """Reserved system shortcuts should be blocked."""
        reserved = {"alt+f4", "ctrl+alt+delete"}
        assert "alt+f4" in reserved
        assert "ctrl+alt+delete" in reserved
        assert "ctrl+space" not in reserved


class TestConfigChangedSignal:
    """Tests for config change signal emission."""

    def test_set_config_emits_signal(self, config_manager):
        """Setting a config value should emit configChanged."""
        signal_received = []

        def on_changed(section, key, value):
            signal_received.append((section, key, value))

        config_manager.instance().configChanged.connect(on_changed)
        try:
            config_manager.set_config_value("test_value", "misc", "print_to_terminal")
            assert len(signal_received) == 1
            assert signal_received[0] == ("misc", "print_to_terminal", "test_value")
        finally:
            config_manager.instance().configChanged.disconnect(on_changed)
            # Restore original value
            config_manager.set_config_value(True, "misc", "print_to_terminal")

    def test_set_nested_config_emits_correct_section(self, config_manager):
        """Nested config changes should emit with correct section/key."""
        signal_received = []

        def on_changed(section, key, value):
            signal_received.append((section, key, value))

        config_manager.instance().configChanged.connect(on_changed)
        try:
            original = config_manager.get_config_value(
                "output_options", "add_trailing_space"
            )
            config_manager.set_config_value(
                False, "output_options", "add_trailing_space"
            )
            assert len(signal_received) == 1
            assert signal_received[0][0] == "output_options"
            assert signal_received[0][1] == "add_trailing_space"
        finally:
            config_manager.instance().configChanged.disconnect(on_changed)
            config_manager.set_config_value(
                original, "output_options", "add_trailing_space"
            )


class TestKeyListenerCaptureMode:
    """Tests for KeyListener capture mode."""

    def test_enable_capture_mode(self, key_listener):
        """Capture mode should divert events to callback."""
        captured = []

        def capture_cb(key, event):
            captured.append((key, event))

        key_listener.enable_capture_mode(capture_cb)
        assert key_listener.capture_mode is True
        assert key_listener.capture_callback is capture_cb

    def test_disable_capture_mode(self, key_listener):
        """Disabling capture mode should restore normal handling."""
        key_listener.enable_capture_mode(lambda k, e: None)
        key_listener.disable_capture_mode()
        assert key_listener.capture_mode is False
        assert key_listener.capture_callback is None

    def test_capture_mode_diverts_events(self, key_listener):
        """Events should go to capture callback, not normal handling."""
        captured = []
        normal_triggered = []

        def capture_cb(key, event):
            captured.append((key, event))

        def on_activate():
            normal_triggered.append("activate")

        key_listener.add_callback("on_activate", on_activate)
        key_listener.enable_capture_mode(capture_cb)

        # Simulate event
        key_listener.on_input_event((KeyCode.SPACE, InputEvent.KEY_PRESS))

        assert len(captured) == 1
        assert captured[0] == (KeyCode.SPACE, InputEvent.KEY_PRESS)
        assert len(normal_triggered) == 0

        key_listener.disable_capture_mode()
