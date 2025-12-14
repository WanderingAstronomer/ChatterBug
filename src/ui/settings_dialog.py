"""Settings dialog built from the configuration schema."""
from typing import Any

from PyQt5.QtCore import QRegularExpression
from PyQt5.QtGui import QRegularExpressionValidator
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from key_listener import KeyListener
from ui.hotkey_widget import HotkeyWidget
from utils import ConfigManager


class SettingsDialog(QDialog):
    """Modal settings dialog with schema-driven forms."""

    # Sections to skip entirely (internal state)
    HIDDEN_SECTIONS: set[str] = {'_internal', 'ui_state'}

    def __init__(
        self, key_listener: KeyListener, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.key_listener = key_listener
        self.schema = ConfigManager.get_schema()
        self.widgets: dict[tuple[str, str], QWidget] = {}

        self.tab_widget = QTabWidget(self)
        self._build_tabs()
        self._build_buttons()

        layout = QVBoxLayout(self)
        layout.addWidget(self.tab_widget)
        layout.addWidget(self.button_box)
        self.setLayout(layout)
        self.setMinimumSize(550, 350)
        self.resize(700, 500)

    def _build_tabs(self) -> None:
        for section, section_schema in self.schema.items():
            # Skip entirely hidden sections
            if section in self.HIDDEN_SECTIONS:
                continue

            tab = QWidget(self)
            form = QFormLayout(tab)
            has_visible = False

            for key, spec in section_schema.items():
                # Skip internal options
                if spec.get('_internal', False):
                    continue

                widget = self._create_widget(section, key, spec)
                self.widgets[(section, key)] = widget

                label = QLabel(self._format_label(key), tab)
                if desc := spec.get('description'):
                    label.setToolTip(desc)
                form.addRow(label, widget)
                has_visible = True

            # Only add tab if it has visible options
            if has_visible:
                tab.setLayout(form)
                self.tab_widget.addTab(tab, self._format_label(section))

    def _build_buttons(self) -> None:
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply,
            self,
        )
        self.button_box.accepted.connect(self._apply_and_accept)
        self.button_box.rejected.connect(self._on_reject)
        self.button_box.button(QDialogButtonBox.Apply).clicked.connect(self._apply_only)

    def _on_reject(self) -> None:
        """Handle cancel button with cleanup."""
        self._cleanup_widgets()
        self.reject()

    def _create_widget(self, section: str, key: str, spec: dict[str, Any]) -> QWidget:
        value = ConfigManager.get_config_value(section, key)
        value_type = spec.get('type')
        options = spec.get('options')

        tooltip = spec.get('description', '')

        if section == 'recording_options' and key == 'activation_key':
            widget = HotkeyWidget(self.key_listener, self)
            widget.set_hotkey(str(value))
            widget.setToolTip(tooltip)
            return widget

        if value_type == 'bool':
            cb = QCheckBox(self)
            cb.setChecked(bool(value))
            cb.setToolTip(tooltip)
            return cb

        if value_type == 'int':
            spin = QSpinBox(self)
            spin.setRange(0, 100_000)
            spin.setValue(int(value) if value is not None else 0)
            spin.setToolTip(tooltip)
            return spin

        if value_type == 'float':
            dspin = QDoubleSpinBox(self)
            dspin.setDecimals(4)
            dspin.setRange(0.0, 10.0)
            dspin.setSingleStep(0.001)
            dspin.setValue(float(value) if value is not None else 0.0)
            dspin.setToolTip(tooltip)
            return dspin

        if value_type == 'str' and options:
            combo = QComboBox(self)
            combo.addItems(options)
            combo.setCurrentText(str(value) if value else options[0])
            combo.setToolTip(tooltip)
            return combo

        if value_type == 'str':
            edit = QLineEdit(str(value) if value else '', self)
            if section == 'model_options' and key == 'language':
                regex = QRegularExpression(r'^[a-zA-Z]{2}$')
                edit.setValidator(QRegularExpressionValidator(regex, edit))
                edit.setPlaceholderText('en')
            edit.setToolTip(tooltip)
            return edit

        # Fallback to line edit
        fallback = QLineEdit(str(value) if value else '', self)
        fallback.setToolTip(tooltip)
        return fallback

    def _format_label(self, text: str) -> str:
        return text.replace('_', ' ').title()

    def _apply_only(self) -> None:
        if self._apply_changes():
            ConfigManager.save_config()

    def _apply_and_accept(self) -> None:
        if self._apply_changes():
            ConfigManager.save_config()
            self._cleanup_widgets()
            self.accept()

    def _cleanup_widgets(self) -> None:
        """Clean up widgets before closing dialog."""
        from ui.hotkey_widget import HotkeyWidget as HKW
        for widget in self.widgets.values():
            if isinstance(widget, HKW):
                widget.cleanup()

    def _apply_changes(self) -> bool:
        """Write widget values back to ConfigManager."""
        for (section, key), widget in self.widgets.items():
            new_value = self._read_widget_value(widget)
            current_value = ConfigManager.get_config_value(section, key)
            # Only update if value changed to prevent unnecessary reloads
            if new_value != current_value:
                ConfigManager.set_config_value(new_value, section, key)
        return True

    def _read_widget_value(self, widget: QWidget) -> Any:
        from ui.hotkey_widget import HotkeyWidget as HKW

        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QSpinBox):
            return int(widget.value())
        if isinstance(widget, QDoubleSpinBox):
            return float(widget.value())
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QLineEdit):
            return widget.text()
        if isinstance(widget, HKW):
            return widget.get_hotkey()
        return None
