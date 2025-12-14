"""
Tests for key listener and hotkey detection.
"""
import pytest

from key_listener import EvdevBackend, InputEvent, KeyChord, KeyCode, PynputBackend


class TestKeyCode:
    """Tests for KeyCode enum."""

    def test_backquote_exists(self):
        """BACKQUOTE key should exist."""
        assert hasattr(KeyCode, 'BACKQUOTE')
        assert KeyCode.BACKQUOTE is not None

    def test_modifier_keys_exist(self):
        """Common modifier keys should exist."""
        assert hasattr(KeyCode, 'CTRL_LEFT')
        assert hasattr(KeyCode, 'CTRL_RIGHT')
        assert hasattr(KeyCode, 'SHIFT_LEFT')
        assert hasattr(KeyCode, 'ALT_LEFT')
        assert hasattr(KeyCode, 'ALT_RIGHT')

    def test_special_keys_exist(self):
        """Special keys should exist."""
        assert hasattr(KeyCode, 'SPACE')
        assert hasattr(KeyCode, 'ENTER')
        assert hasattr(KeyCode, 'TAB')


class TestKeyChord:
    """Tests for KeyChord functionality."""

    def test_single_key_chord(self):
        """Single key chord should activate on press."""
        chord = KeyChord({KeyCode.BACKQUOTE})

        assert not chord.is_active()

        # Press the key
        result = chord.update(KeyCode.BACKQUOTE, InputEvent.KEY_PRESS)
        assert result is True
        assert chord.is_active()

        # Release the key
        result = chord.update(KeyCode.BACKQUOTE, InputEvent.KEY_RELEASE)
        assert result is False
        assert not chord.is_active()

    def test_multi_key_chord(self):
        """Multi-key chord should only activate when all pressed."""
        chord = KeyChord({KeyCode.CTRL_LEFT, KeyCode.SPACE})

        # Press just CTRL
        chord.update(KeyCode.CTRL_LEFT, InputEvent.KEY_PRESS)
        assert not chord.is_active()

        # Press SPACE while holding CTRL
        chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        assert chord.is_active()

        # Release one key
        chord.update(KeyCode.CTRL_LEFT, InputEvent.KEY_RELEASE)
        assert not chord.is_active()

    def test_modifier_group_chord(self):
        """Modifier groups (e.g., any CTRL) should work."""
        # frozenset means "any of these"
        ctrl_group = frozenset({KeyCode.CTRL_LEFT, KeyCode.CTRL_RIGHT})
        chord = KeyChord({ctrl_group, KeyCode.SPACE})

        # Press left CTRL + SPACE
        chord.update(KeyCode.CTRL_LEFT, InputEvent.KEY_PRESS)
        chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        assert chord.is_active()

        chord.update(KeyCode.CTRL_LEFT, InputEvent.KEY_RELEASE)
        chord.update(KeyCode.SPACE, InputEvent.KEY_RELEASE)

        # Press right CTRL + SPACE
        chord.update(KeyCode.CTRL_RIGHT, InputEvent.KEY_PRESS)
        chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)
        assert chord.is_active()


class TestKeyListener:
    """Tests for KeyListener functionality."""

    def test_parse_single_key(self, key_listener):
        """Should parse single key names."""
        keys = key_listener.parse_key_combination("backquote")
        assert KeyCode.BACKQUOTE in keys

    def test_parse_key_combo(self, key_listener):
        """Should parse key combinations with +."""
        keys = key_listener.parse_key_combination("ctrl+shift+space")

        # CTRL and SHIFT are frozensets (any left/right)
        has_ctrl = any(
            isinstance(k, frozenset) and KeyCode.CTRL_LEFT in k
            for k in keys
        )
        has_shift = any(
            isinstance(k, frozenset) and KeyCode.SHIFT_LEFT in k
            for k in keys
        )
        has_space = KeyCode.SPACE in keys

        assert has_ctrl, "CTRL not found"
        assert has_shift, "SHIFT not found"
        assert has_space, "SPACE not found"

    def test_parse_alt_right(self, key_listener):
        """Should parse ALT_RIGHT specifically."""
        keys = key_listener.parse_key_combination("alt_right")
        assert KeyCode.ALT_RIGHT in keys

    def test_parse_unknown_key_handled(self, key_listener, capsys):
        """Unknown keys should be handled gracefully."""
        keys = key_listener.parse_key_combination("unknownkey123")
        # Should print warning but not crash
        captured = capsys.readouterr()
        assert "Unknown key" in captured.out or len(keys) == 0


class TestBackendAvailability:
    """Tests for input backend detection."""

    def test_pynput_available(self):
        """pynput backend should be available."""
        assert PynputBackend.is_available() is True

    def test_evdev_importable(self):
        """evdev should be importable on Linux."""
        # This may fail on non-Linux, which is fine
        try:
            import evdev
            assert EvdevBackend.is_available() is True
        except ImportError:
            pytest.skip("evdev not installed")

    def test_key_listener_selects_backend(self, key_listener):
        """KeyListener should select an available backend."""
        assert key_listener.active_backend is not None
        backend_name = type(key_listener.active_backend).__name__
        assert backend_name in ['PynputBackend', 'EvdevBackend']
