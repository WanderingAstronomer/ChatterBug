"""Widget for capturing and displaying global hotkeys."""
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from key_listener import InputEvent, KeyCode, KeyListener
from ui.keycode_mapping import (
    keycodes_to_strings,
    normalize_hotkey_string,
)


class HotkeyWidget(QWidget):
    """Capture and edit the activation hotkey."""

    hotkeyChanged = pyqtSignal(str)

    def __init__(
        self, key_listener: KeyListener, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.key_listener = key_listener
        self.pressed_keys: set[KeyCode] = set()

        self.display = QLineEdit(self)
        self.display.setReadOnly(True)
        self.display.setPlaceholderText("Press Change to set hotkey")
        self.display.setToolTip("Current activation hotkey")

        self.change_button = QPushButton("Change...", self)
        self.change_button.setToolTip("Click to capture a new hotkey")
        self.change_button.clicked.connect(self._start_capture)

        self.validation_label = QLabel(self)
        self.validation_label.setStyleSheet("color: red;")
        self.validation_label.setVisible(False)

        row = QHBoxLayout()
        row.addWidget(self.display)
        row.addWidget(self.change_button)

        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self.validation_label)
        self.setLayout(layout)

    def set_hotkey(self, hotkey: str) -> None:
        display, _ = keycodes_to_strings(self._parse_hotkey_string(hotkey))
        self.display.setText(display)
        self.validation_label.setVisible(False)

    def _start_capture(self) -> None:
        self.pressed_keys.clear()
        self.display.setText("Press keys...")
        self.change_button.setEnabled(False)
        self.validation_label.setVisible(False)
        self.key_listener.enable_capture_mode(self._on_capture_event)

    def _on_capture_event(self, key: KeyCode, event_type: InputEvent) -> None:
        if event_type == InputEvent.KEY_PRESS:
            self.pressed_keys.add(key)
            display, _ = keycodes_to_strings(self.pressed_keys)
            self.display.setText(display)
        elif event_type == InputEvent.KEY_RELEASE and self.pressed_keys:
            self._finalize_capture()

    def _finalize_capture(self) -> None:
        self.key_listener.disable_capture_mode()
        self.change_button.setEnabled(True)

        if not self.pressed_keys:
            self.display.setText("")
            return

        display, config = keycodes_to_strings(self.pressed_keys)
        normalized = normalize_hotkey_string(config)

        valid, error = self._validate_hotkey(normalized)
        if not valid:
            self.display.setStyleSheet("QLineEdit { border: 1px solid red; }")
            self.validation_label.setText(error)
            self.validation_label.setVisible(True)
            return

        self.display.setStyleSheet("")
        self.validation_label.setVisible(False)
        self.display.setText(display)
        self.hotkeyChanged.emit(normalized)

    def _validate_hotkey(self, hotkey: str) -> tuple[bool, str]:
        """Validate the hotkey - allow single keys, reject only dangerous combos."""
        parts = [p for p in hotkey.split('+') if p]
        if not parts:
            return False, "No keys captured"
        # Block dangerous system shortcuts
        dangerous = {"alt+f4", "ctrl+alt+delete", "ctrl+c", "ctrl+v", "ctrl+z"}
        if hotkey.lower() in dangerous:
            return False, "Reserved system shortcut"
        return True, ""

    def _parse_hotkey_string(self, hotkey: str) -> set[KeyCode]:
        """Best-effort parse of a config hotkey string into KeyCodes for display."""
        lookup: dict[str, KeyCode] = {code.name.lower(): code for code in KeyCode}
        result: set[KeyCode] = set()
        for part in hotkey.lower().split('+'):
            part = part.strip()
            match part:
                case "ctrl":
                    result.add(KeyCode.CTRL_LEFT)
                case "shift":
                    result.add(KeyCode.SHIFT_LEFT)
                case "alt":
                    result.add(KeyCode.ALT_LEFT)
                case "meta":
                    result.add(KeyCode.META_LEFT)
                case _:
                    code = lookup.get(part)
                    if code:
                        result.add(code)
        return result

    def get_hotkey(self) -> str:
        """Return the currently displayed hotkey string (config-normalized)."""
        keys = self.pressed_keys or self._parse_hotkey_string(
            self.display.text().replace(' + ', '+')
        )
        _, config = keycodes_to_strings(keys)
        return normalize_hotkey_string(config)

    def cleanup(self) -> None:
        """Clean up capture mode if still active."""
        self.key_listener.disable_capture_mode()
        self.change_button.setEnabled(True)
