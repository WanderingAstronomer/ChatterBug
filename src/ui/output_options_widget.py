"""
Cascading output options widget for transcription output control.

Provides hierarchical checkbox interface: Copy → Auto-inject → Auto-submit.
Child options are disabled when parent is unchecked.
"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QWidget,
)

from utils import ConfigManager


class OutputOptionsWidget(QWidget):
    """
    Cascading checkbox hierarchy for output options.

    Hierarchy: Copy → Auto-inject → Auto-submit.
    """

    optionsChanged = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("outputOptionsBar")

        # Create checkboxes
        self.copy_clipboard = QCheckBox("Copy to clipboard")
        self.copy_clipboard.setToolTip(
            "Copy transcription to clipboard. Use Ctrl+V to paste manually."
        )
        
        self.auto_inject = QCheckBox("Auto-inject text into active window")
        self.auto_inject.setToolTip(
            "Experimental: Automatically paste text. May not work reliably on Wayland. "
            "For best results, use 'Copy to clipboard' and paste manually with Ctrl+V."
        )
        
        self.auto_submit = QCheckBox("Auto-submit with Enter key")

        # Warning label for auto-submit (inline, compact)
        self.submit_warning = QLabel("⚠️")
        self.submit_warning.setToolTip(
            "Warning: Enter will be pressed after every transcription"
        )
        self.submit_warning.setStyleSheet("color: #ffa500; font-size: 12pt;")
        self.submit_warning.setVisible(False)

        # Load initial states from config
        self._load_from_config()

        # Setup cascade dependencies
        self._setup_cascade()

        # Build layout with indentation
        self._build_layout()

        # Set accessible names
        self._setup_accessibility()

    def _load_from_config(self) -> None:
        """Load checkbox states from configuration."""
        copy_val = ConfigManager.get_config_value(
            'output_options', 'auto_copy_clipboard'
        )
        self.copy_clipboard.setChecked(bool(copy_val))

        inject_val = ConfigManager.get_config_value(
            'output_options', 'auto_inject_text'
        )
        self.auto_inject.setChecked(bool(inject_val))

        submit_val = ConfigManager.get_config_value(
            'output_options', 'auto_submit_return'
        )
        self.auto_submit.setChecked(bool(submit_val))

    def _setup_cascade(self) -> None:
        """Connect checkbox state changes to enable/disable dependents."""
        # Level 1: clipboard controls inject
        self.copy_clipboard.stateChanged.connect(self._on_clipboard_changed)

        # Level 2: inject controls submit
        self.auto_inject.stateChanged.connect(self._on_inject_changed)

        # Auto-submit confirmation
        self.auto_submit.stateChanged.connect(self._on_submit_changed)

        # Initialize enabled states
        self._on_clipboard_changed(self.copy_clipboard.checkState())
        self._on_inject_changed(self.auto_inject.checkState())

        # Emit signal for external listeners
        self.copy_clipboard.stateChanged.connect(lambda: self.optionsChanged.emit())
        self.auto_inject.stateChanged.connect(lambda: self.optionsChanged.emit())
        self.auto_submit.stateChanged.connect(lambda: self.optionsChanged.emit())

    def _build_layout(self) -> None:
        """Build compact single-row layout."""
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(20)

        # All checkboxes in a single row
        layout.addWidget(self.copy_clipboard)
        layout.addWidget(self.auto_inject)
        layout.addWidget(self.auto_submit)
        layout.addWidget(self.submit_warning)
        layout.addStretch()

        self.setLayout(layout)

    def _setup_accessibility(self) -> None:
        """Set accessible names and descriptions for screen readers."""
        self.copy_clipboard.setAccessibleName("Copy to Clipboard")
        self.copy_clipboard.setAccessibleDescription(
            "Automatically copy each transcription to the system clipboard"
        )

        self.auto_inject.setAccessibleName("Auto-inject Text")
        self.auto_inject.setAccessibleDescription(
            "Automatically type transcription into the active window. "
            "Requires Copy to Clipboard to be enabled."
        )

        self.auto_submit.setAccessibleName("Auto-submit with Enter")
        self.auto_submit.setAccessibleDescription(
            "Automatically press Enter after typing transcription. "
            "Use with caution as this will send messages and submit forms."
        )

    def _on_clipboard_changed(self, state: int) -> None:
        """Enable/disable inject checkbox based on clipboard state."""
        is_checked = state == Qt.Checked
        self.auto_inject.setEnabled(is_checked)

        if not is_checked:
            # Uncheck children when parent is unchecked
            self.auto_inject.setChecked(False)

    def _on_inject_changed(self, state: int) -> None:
        """Enable/disable submit checkbox based on inject state."""
        is_checked = state == Qt.Checked
        is_parent_checked = self.copy_clipboard.isChecked()

        # Only enable if both parent and this are checked
        self.auto_submit.setEnabled(is_checked and is_parent_checked)

        if not is_checked:
            self.auto_submit.setChecked(False)

    def _on_submit_changed(self, state: int) -> None:
        """Handle auto-submit checkbox change with confirmation."""
        is_checked = state == Qt.Checked

        # Update warning visibility
        self.submit_warning.setVisible(is_checked)

        if is_checked:
            # Check if user has been warned before
            warned_before = ConfigManager.get_config_value(
                '_internal', 'auto_submit_warned'
            ) or False

            if not warned_before:
                reply = QMessageBox.warning(
                    self,
                    "Enable Auto-Submit?",
                    "This will automatically press Enter after each transcription.\n\n"
                    "⚠️ Use with caution:\n"
                    "• Chat messages will be sent immediately\n"
                    "• Forms will be submitted\n"
                    "• Terminal commands will execute\n\n"
                    "Are you sure you want to enable this?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )

                if reply == QMessageBox.No:
                    # User declined, uncheck the box
                    self.auto_submit.setChecked(False)
                    return

                # Remember that user was warned
                ConfigManager.set_config_value(True, '_internal', 'auto_submit_warned')

    def get_options(self) -> dict[str, bool]:
        """Get current checkbox states as dict."""
        return {
            'auto_copy_clipboard': self.copy_clipboard.isChecked(),
            'auto_inject_text': self.auto_inject.isChecked(),
            'auto_submit_return': self.auto_submit.isChecked(),
        }

    def save_to_config(self) -> None:
        """Save current options to configuration."""
        options = self.get_options()
        for key, value in options.items():
            ConfigManager.set_config_value(value, 'output_options', key)
