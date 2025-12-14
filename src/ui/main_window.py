"""
Main application window for Vociferous.

This window provides:
- Transcription history sidebar (left panel)
- Current transcription display (right panel)
- Output options checkboxes (bottom)
- Menu bar with File, View, History, Settings, Help

Layout:
-------
┌──────────────────────────────────────────────────────┐
│ File  View  History  Settings  Help                  │
├──────────────────────────────────────────────────────┤
│ ┌──History────────┐ │ ┌──Current Transcription────┐ │
│ │ [15:30] Hello...│ │ │                           │ │
│ │ [15:28] Test... │ │ │  Full transcription text  │ │
│ │ ...             │ │ │                           │ │
│ └─────────────────┘ │ └───────────────────────────┘ │
├──────────────────────────────────────────────────────┤
│ ☐ Copy to clipboard                                  │
│   ☐ Auto-inject    ☐ Auto-submit ⚠️                  │
└──────────────────────────────────────────────────────┘

Responsive Design:
------------------
- Width >= 700px: Side-by-side (horizontal splitter)
- Width < 700px: Stacked (vertical splitter)

Python 3.12+ Features:
----------------------
- Match/case for status handling and keyboard events
- Union type hints with |
"""

from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import (
    QPropertyAnimation,
    QSettings,
    Qt,
    pyqtSignal,
)
from PyQt5.QtGui import QFont, QGuiApplication, QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QFileDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QShortcut,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from history_manager import HistoryEntry, HistoryManager
from ui.history_widget import HistoryWidget


class MainWindow(QMainWindow):
    """Primary application window with history and transcription display."""

    windowCloseRequested = pyqtSignal()

    def __init__(self, history_manager: HistoryManager | None = None) -> None:
        super().__init__()
        self.settings = QSettings("Vociferous", "MainWindow")
        self._tray_icon = None
        self._hide_notification_shown = False

        # History manager (create default if not provided)
        self.history_manager = history_manager or HistoryManager()

        self._init_ui()
        self._create_menu_bar()
        self._create_shortcuts()
        self._restore_geometry()

    def _init_ui(self) -> None:
        """Initialize the main UI layout."""
        self.setWindowTitle("Vociferous")
        self.setMinimumSize(600, 400)

        central = QWidget(self)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Recording status indicator with pulse animation
        self._setup_recording_indicator()

        # Splitter for resizable panels
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(1)

        # Left: History panel with header
        history_panel = self._create_history_panel()
        self.splitter.addWidget(history_panel)

        # Right: Current transcription display
        current_panel = self._create_current_panel()
        self.splitter.addWidget(current_panel)

        # Initial splitter ratio (30% history, 70% current)
        self.splitter.setSizes([300, 700])

        main_layout.addWidget(self.splitter)

        central.setLayout(main_layout)
        self.setCentralWidget(central)

        # Apply stylesheet for visual polish
        self._apply_stylesheet()

        # Hide status bar
        self.statusBar().hide()

    def _create_history_panel(self) -> QWidget:
        """Create history panel with header."""
        from PyQt5.QtWidgets import QLabel

        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header - floating pill label
        header = QLabel("History")
        header.setObjectName("historyHeader")
        header.setAlignment(Qt.AlignCenter)
        header.setFixedHeight(66)
        layout.addWidget(header)

        # Content layout with padding
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(8, 0, 8, 8)

        # History widget
        self.history_widget = HistoryWidget()
        self.history_widget.load_history(self.history_manager)
        content_layout.addWidget(self.history_widget)

        # Button row: Export (left) and Clear All (right)
        history_buttons = QHBoxLayout()

        self.history_export_btn = QPushButton("Export")
        self.history_export_btn.setObjectName("transcriptionButton")
        self.history_export_btn.setToolTip("Export history to file (Ctrl+E)")
        self.history_export_btn.clicked.connect(self._export_history)
        self.history_export_btn.setAccessibleName("Export History")
        history_buttons.addWidget(self.history_export_btn)

        history_buttons.addStretch()

        self.history_clear_btn = QPushButton("Clear All")
        self.history_clear_btn.setObjectName("transcriptionButton")
        self.history_clear_btn.setToolTip("Clear all history entries")
        self.history_clear_btn.clicked.connect(self._clear_all_history)
        self.history_clear_btn.setAccessibleName("Clear All History")
        history_buttons.addWidget(self.history_clear_btn)

        content_layout.addLayout(history_buttons)

        content_widget.setLayout(content_layout)
        layout.addWidget(content_widget)

        panel.setLayout(layout)
        return panel

    def _create_current_panel(self) -> QWidget:
        """Create panel for displaying current transcription."""
        from PyQt5.QtWidgets import QLabel

        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header - floating pill label
        header = QLabel("Current Transcription")
        header.setObjectName("currentHeader")
        header.setAlignment(Qt.AlignCenter)
        header.setFixedHeight(66)
        layout.addWidget(header)

        # Content layout with padding
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(8, 0, 8, 8)

        # Large text display
        self.transcription_display = QTextEdit()
        self.transcription_display.setReadOnly(True)
        self.transcription_display.setPlaceholderText(
            "Transcriptions will appear here..."
        )
        self.transcription_display.setFont(QFont("Monospace", 11))
        self.transcription_display.setAccessibleName("Current Transcription")
        self.transcription_display.setAccessibleDescription(
            "Display of the most recent transcription result."
        )
        content_layout.addWidget(self.transcription_display)

        # Button row with recording indicator in center
        button_layout = QHBoxLayout()

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setObjectName("transcriptionButton")
        self.copy_btn.setToolTip("Copy current transcription to clipboard (Ctrl+C)")
        self.copy_btn.clicked.connect(self._copy_current)
        self.copy_btn.setAccessibleName("Copy Current Transcription")
        button_layout.addWidget(self.copy_btn)

        # Recording indicator centered between buttons
        button_layout.addStretch()
        button_layout.addWidget(self.recording_indicator)
        button_layout.addStretch()

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("transcriptionButton")
        self.clear_btn.setToolTip("Clear current display (Ctrl+L)")
        self.clear_btn.clicked.connect(self._clear_current)
        self.clear_btn.setAccessibleName("Clear Current Display")
        button_layout.addWidget(self.clear_btn)

        content_layout.addLayout(button_layout)
        content_widget.setLayout(content_layout)
        layout.addWidget(content_widget)

        panel.setLayout(layout)
        return panel

    def _create_menu_bar(self) -> None:
        """Create menu bar with all menus."""
        menu_bar: QMenuBar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu

        # History menu
        history_menu = menu_bar.addMenu("&History")
        export_action = QAction("Export...", self)
        export_action.triggered.connect(self._export_history)
        history_menu.addAction(export_action)

        clear_history_action = QAction("Clear All...", self)
        clear_history_action.triggered.connect(self._clear_all_history)
        history_menu.addAction(clear_history_action)

        # Settings menu
        settings_menu = menu_bar.addMenu("&Settings")
        self.settings_action = QAction("Preferences...", self)
        self.settings_action.setEnabled(True)
        settings_menu.addAction(self.settings_action)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("About", self)
        about_action.setEnabled(False)
        help_menu.addAction(about_action)

    def _create_shortcuts(self) -> None:
        """Create keyboard shortcuts."""
        # Ctrl+C: Copy current
        copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        copy_shortcut.activated.connect(self._copy_current)

        # Ctrl+E: Export history
        export_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        export_shortcut.activated.connect(self._export_history)

        # Ctrl+H: Focus history
        focus_history_shortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        focus_history_shortcut.activated.connect(lambda: self.history_widget.setFocus())

        # Ctrl+L: Clear display
        clear_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        clear_shortcut.activated.connect(self._clear_current)

    def _setup_recording_indicator(self) -> None:
        """Create compact pulsing recording indicator label."""
        self.recording_indicator = QLabel("● Recording")
        self.recording_indicator.setObjectName("recordingIndicator")
        self.recording_indicator.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.recording_indicator.setVisible(False)
        self.recording_indicator.setFixedHeight(24)
        self.recording_indicator.setContentsMargins(8, 0, 8, 0)

        # Opacity effect for fading
        self.indicator_opacity = QGraphicsOpacityEffect(self.recording_indicator)
        self.recording_indicator.setGraphicsEffect(self.indicator_opacity)
        self.indicator_opacity.setOpacity(1.0)

        # Pulse animation: fade between 0.4 and 1.0 opacity
        self.pulse_animation = QPropertyAnimation(self.indicator_opacity, b"opacity")
        self.pulse_animation.setDuration(600)  # 600ms per pulse
        self.pulse_animation.setStartValue(1.0)
        self.pulse_animation.setEndValue(0.4)
        self.pulse_animation.finished.connect(self._reverse_pulse)
        self._pulse_direction = True  # True = fading out, False = fading in

    def _reverse_pulse(self) -> None:
        """Reverse the pulse animation direction."""
        if not self.recording_indicator.isVisible():
            return
        if self._pulse_direction:
            self.pulse_animation.setStartValue(0.3)
            self.pulse_animation.setEndValue(1.0)
        else:
            self.pulse_animation.setStartValue(1.0)
            self.pulse_animation.setEndValue(0.3)
        self._pulse_direction = not self._pulse_direction
        self.pulse_animation.start()

    def _start_recording_pulse(self) -> None:
        """Show recording indicator and start pulsing."""
        self.recording_indicator.setVisible(True)
        self.indicator_opacity.setOpacity(1.0)
        self._pulse_direction = True
        self.pulse_animation.start()

    def _stop_recording_pulse(self) -> None:
        """Hide recording indicator and stop pulsing."""
        self.pulse_animation.stop()
        self.recording_indicator.setVisible(False)

    def _apply_stylesheet(self) -> None:
        """Apply dark theme with blue accents."""
        self.setStyleSheet("""
            /* Main window - dark background */
            QMainWindow {
                background-color: #1e1e1e;
            }
            
            QWidget {
                background-color: #1e1e1e;
                color: #d4d4d4;
            }
            
            /* Recording indicator - compact inline */
            QLabel#recordingIndicator {
                background-color: transparent;
                color: #ff6b6b;
                font-weight: bold;
                font-size: 11px;
                padding: 2px 8px;
                border: none;
            }
            
            /* Panel headers - floating pill labels */
            QLabel#historyHeader, QLabel#currentHeader {
                background-color: #252526;
                color: #5a9fd4;
                font-weight: bold;
                font-size: 18px;
                padding: 8px 24px;
                margin: 8px;
                border: 1px solid #5a9fd4;
                border-radius: 18px;
                qproperty-alignment: AlignCenter;
            }

            /* Hide separator lines */
            QFrame#separator {
                max-height: 0px;
                border: none;
            }
            
            /* History list */
            QListWidget {
                background-color: #252526;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                outline: none;
                color: #d4d4d4;
                font-size: 11pt;
                padding: 8px 16px 8px 8px;  /* extra right padding for scrollbar */
            }

            /* Hide horizontal scrollbar in history */
            QListWidget QScrollBar:horizontal {
                height: 0px;
            }
            
            QListWidget::item {
                padding: 12px;
                margin: 4px;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                background-color: #2a2a2a;
                outline: none;
            }
            
            /* Alternating row colors */
            QListWidget::item:alternate {
                background-color: #252526;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
            
            QListWidget::item:selected {
                background-color: #2d5a7b;
                color: #5a9fd4;
                border: 1px solid #5a9fd4;
                border-radius: 4px;
            }
            
            QListWidget::item:hover {
                background-color: #2d3d4d;
                border: 1px solid #5a9fd4;
                border-radius: 4px;
            }
            
            /* Current transcription display */
            QTextEdit {
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 12px;
                selection-background-color: #2d5a7b;
                selection-color: #5a9fd4;
            }
            
            QTextEdit:focus {
                border: 1px solid #5a9fd4;
            }
            
            /* Buttons - dark with blue accent on hover */
            QPushButton {
                background-color: #333333;
                color: #d4d4d4;
                border: 1px solid #5a9fd4;
                border-radius: 4px;
                padding: 6px 16px;
                min-width: 70px;
            }
            
            /* Smaller buttons for transcription section */
            QPushButton#transcriptionButton {
                padding: 4px 12px;
                min-width: 56px;
                font-size: 16px;
            }
            
            QPushButton:hover {
                background-color: #2d5a7b;
                color: #5a9fd4;
            }
            
            QPushButton:pressed {
                background-color: #1e4a6b;
            }
            
            /* Output options bar - compact dark panel */
            QWidget#outputOptionsBar {
                background-color: #252526;
                border-top: 1px solid #3c3c3c;
                max-height: 36px;
            }
            
            /* Checkboxes - blue accent */
            QCheckBox {
                spacing: 8px;
                color: #d4d4d4;
                font-size: 14pt;
            }
            
            QCheckBox:disabled {
                color: #606060;
            }
            
            QCheckBox::indicator {
                width: 14px;
                height: 16px;
                border: 1px solid #5a9fd4;
                border-radius: 3px;
                background-color: #252526;
            }
            
            QCheckBox::indicator:checked {
                background-color: #5a9fd4;
            }
            
            QCheckBox::indicator:disabled {
                border-color: #4a4a4a;
                background-color: #333333;
            }
            
            /* Status bar - dark with blue text */
            QStatusBar {
                background-color: #252526;
                color: #5a9fd4;
                border-top: 1px solid #3c3c3c;
            }
            
            /* Menu bar - compact */
            QMenuBar {
                background-color: #252526;
                color: #d4d4d4;
                border-bottom: 1px solid #3c3c3c;
                font-size: 14px;
                padding: 2px;
            }
            
            QMenuBar::item {
                padding: 3px 8px;
            }
            
            QMenuBar::item:selected {
                background-color: #2d5a7b;
                color: #5a9fd4;
            }
            
            QMenu {
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #5a9fd4;
                font-size: 11px;
            }
            
            QMenu::item {
                padding: 4px 20px;
            }
            
            QMenu::item:selected {
                background-color: #2d5a7b;
                color: #5a9fd4;
            }
            
            /* Splitter handle - visible centered grab bar */
            QSplitter::handle {
                background-color: #1e1e1e;
                width: 12px;
            }

            QSplitter::handle:horizontal {
                width: 12px;
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e1e1e,
                    stop:0.3 #1e1e1e,
                    stop:0.35 #5a5a5a,
                    stop:0.4 #5a5a5a,
                    stop:0.45 #1e1e1e,
                    stop:0.5 #1e1e1e,
                    stop:0.55 #5a5a5a,
                    stop:0.6 #5a5a5a,
                    stop:0.65 #1e1e1e,
                    stop:0.7 #1e1e1e,
                    stop:1 #1e1e1e
                );
            }

            QSplitter::handle:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e1e1e,
                    stop:0.3 #1e1e1e,
                    stop:0.35 #5a9fd4,
                    stop:0.4 #5a9fd4,
                    stop:0.45 #1e1e1e,
                    stop:0.5 #1e1e1e,
                    stop:0.55 #5a9fd4,
                    stop:0.6 #5a9fd4,
                    stop:0.65 #1e1e1e,
                    stop:0.7 #1e1e1e,
                    stop:1 #1e1e1e
                );
            }
            
            /* Scrollbars - dark with blue accent */
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 12px;
                border: none;
            }
            
            QScrollBar::handle:vertical {
                background-color: #3c3c3c;
                border-radius: 6px;
                min-height: 30px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #5a9fd4;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar:horizontal {
                background-color: #1e1e1e;
                height: 12px;
                border: none;
            }
            
            QScrollBar::handle:horizontal {
                background-color: #3c3c3c;
                border-radius: 6px;
                min-width: 30px;
            }
            
            QScrollBar::handle:horizontal:hover {
                background-color: #5a9fd4;
            }
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

    def on_settings_requested(self, handler) -> None:
        """Connect a handler for opening settings."""
        if hasattr(self, "settings_action"):
            self.settings_action.triggered.connect(handler)

    def set_tray_icon(self, tray_icon) -> None:
        """Allow the window to notify the user via tray messages."""
        self._tray_icon = tray_icon

    def update_transcription_status(self, status: str) -> None:
        """Update recording indicator based on transcription status."""
        match status:
            case "recording":
                self.recording_indicator.setText("● Recording")
                self.recording_indicator.setStyleSheet("color: #ff6b6b;")
                self._start_recording_pulse()
            case "transcribing":
                self._stop_recording_pulse()
                self.recording_indicator.setText("● Transcribing")
                self.recording_indicator.setStyleSheet("color: #ffa500;")
                self.indicator_opacity.setOpacity(1.0)
                self.recording_indicator.setVisible(True)
            case "error" | _:
                self._stop_recording_pulse()

    def display_transcription(self, text: str) -> None:
        """Display new transcription in current panel and add to history."""
        self.transcription_display.setPlainText(text)

        # Add to history widget
        entry = HistoryEntry(
            timestamp=datetime.now().isoformat(),
            text=text,
            duration_ms=0,  # Duration tracked elsewhere
        )
        self.history_widget.add_entry(entry)

    def show_and_raise(self) -> None:
        """Ensure the window is visible and focused."""
        self.show()
        self.raise_()
        # activateWindow() doesn't work on Wayland and triggers warnings
        platform = QGuiApplication.platformName()
        if platform != "wayland":
            self.activateWindow()

    def _toggle_history(self) -> None:
        """Toggle history panel visibility."""
        history_visible = self.history_widget.isVisible()

        if history_visible:
            self.history_widget.hide()
            self.toggle_history_action.setText("Show History")
        else:
            self.history_widget.show()
            self.toggle_history_action.setText("Hide History")

    def _copy_current(self) -> None:
        """Copy current transcription to clipboard."""
        text = self.transcription_display.toPlainText()
        if text:
            self.history_widget._copy_to_clipboard(text)
            self.statusBar().showMessage("Copied to clipboard", 2000)

    def _clear_current(self) -> None:
        """Clear current transcription display."""
        self.transcription_display.clear()

    def _export_history(self) -> None:
        """Show file dialog and export history."""
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export History",
            str(Path.home() / "vociferous_history.txt"),
            "Text Files (*.txt);;CSV Files (*.csv);;Markdown Files (*.md)",
        )

        if not file_path:
            return  # User cancelled

        # Determine format from filter or extension
        if "CSV" in selected_filter or file_path.endswith(".csv"):
            format = "csv"
        elif "Markdown" in selected_filter or file_path.endswith(".md"):
            format = "md"
        else:
            format = "txt"

        # Export
        success = self.history_manager.export_to_file(Path(file_path), format)

        if success:
            QMessageBox.information(
                self, "Export Successful", f"History exported to:\n{file_path}"
            )
        else:
            QMessageBox.warning(
                self,
                "Export Failed",
                "Could not export history. Check logs for details.",
            )

    def _clear_all_history(self) -> None:
        """Clear all history with confirmation using custom dialog layout."""
        from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout, QHBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle("Clear History")
        dialog.setMinimumWidth(420)

        layout = QVBoxLayout()
        layout.setSpacing(16)

        message = QLabel(
            "Are you sure you want to delete all transcription history?\n\n"
            "This action cannot be undone."
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        buttons = QHBoxLayout()
        yes_btn = QPushButton("Yes")
        yes_btn.setObjectName("transcriptionButton")
        yes_btn.clicked.connect(dialog.accept)
        buttons.addWidget(yes_btn)

        buttons.addStretch()

        no_btn = QPushButton("No")
        no_btn.setObjectName("transcriptionButton")
        no_btn.clicked.connect(dialog.reject)
        no_btn.setDefault(True)
        buttons.addWidget(no_btn)

        layout.addLayout(buttons)
        dialog.setLayout(layout)

        if dialog.exec_() == QDialog.Accepted:
            self.history_manager.clear()
            self.history_widget.clear()
            self.statusBar().showMessage("History cleared", 2000)

    def _restore_geometry(self) -> None:
        """Restore window geometry from settings."""
        geometry = self.settings.value("geometry")
        splitter_state = self.settings.value("splitter_state")

        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(1000, 700)
            self._center_on_screen()

        if splitter_state:
            self.splitter.restoreState(splitter_state)

    def _center_on_screen(self) -> None:
        """Center window on screen."""
        screen = self.screen().availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(screen.center())
        self.move(frame.topLeft())

    def resizeEvent(self, event) -> None:
        """Handle window resize with responsive layout."""
        width = event.size().width()

        if width < 700:
            # Small screen: Stack vertically
            self.splitter.setOrientation(Qt.Vertical)
        else:
            # Normal screen: Side-by-side
            self.splitter.setOrientation(Qt.Horizontal)

        super().resizeEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Hide to tray and emit a one-time notification before exiting."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter_state", self.splitter.saveState())

        event.ignore()
        self.hide()

        if self._tray_icon and not self._hide_notification_shown:
            self._tray_icon.showMessage(
                "Vociferous",
                "Running in the system tray. Right-click the tray icon to exit.",
                msecs=2500,
            )
            self._hide_notification_shown = True

        self.windowCloseRequested.emit()
