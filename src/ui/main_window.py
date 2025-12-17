"""
Main application window for Vociferous.

Provides transcription history sidebar, current transcription display,
and output options. Responsive layout adapts to window size.
"""

from pathlib import Path

from PyQt5.QtCore import (
    QPoint,
    QPropertyAnimation,
    QSettings,
    QSize,
    Qt,
    QEvent,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt5.QtGui import QDesktopServices, QFont, QGuiApplication, QKeySequence
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
    QSizePolicy,
    QShortcut,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from history_manager import HistoryEntry, HistoryManager
from ui.history_widget import HistoryWidget


class TitleBar(QWidget):
    """Custom title bar with menu, drag, and window controls in one row."""

    def __init__(self, window: QMainWindow, menu_bar: QMenuBar) -> None:
        super().__init__(window)
        self._window = window
        self._drag_pos: QPoint | None = None
        self._menu_bar = menu_bar

        self.setObjectName("titleBar")
        self.setFixedHeight(44)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self._menu_bar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        self.title_label = QLabel("Vociferous", self)
        self.title_label.setObjectName("titleBarLabel")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setMinimumWidth(0)

        btn_size = QSize(36, 28)

        def make_btn(text: str, obj: str) -> QToolButton:
            button = QToolButton(self)
            button.setText(text)
            button.setObjectName(obj)
            button.setFixedSize(btn_size)
            button.setToolButtonStyle(Qt.ToolButtonTextOnly)
            button.setFocusPolicy(Qt.NoFocus)
            return button

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(6)

        self.min_btn = make_btn("—", "titleBarControl")
        self.min_btn.clicked.connect(self._window.showMinimized)
        button_layout.addWidget(self.min_btn)

        self.max_btn = make_btn("▢", "titleBarControl")
        self.max_btn.clicked.connect(self._toggle_maximize)
        button_layout.addWidget(self.max_btn)

        self.close_btn = make_btn("✕", "titleBarClose")
        self.close_btn.clicked.connect(self._window.close)
        button_layout.addWidget(self.close_btn)

        self._controls = QWidget()
        self._controls.setLayout(button_layout)
        self._controls.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self._left_slot = QWidget(self)
        left_l = QHBoxLayout(self._left_slot)
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(0)
        left_l.addWidget(self._menu_bar)
        left_l.addStretch(1)

        self._right_slot = QWidget(self)
        right_l = QHBoxLayout(self._right_slot)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(0)
        right_l.addStretch(1)
        right_l.addWidget(self._controls)

        layout.addWidget(self._left_slot)
        layout.addWidget(self.title_label, 1)
        layout.addWidget(self._right_slot)

        # Allow dragging from title text
        self.title_label.installEventFilter(self)

        QTimer.singleShot(0, self._sync_side_slots)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._sync_side_slots()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            if QGuiApplication.platformName() == "wayland":
                if self._try_wayland_system_move():
                    event.accept()
                    self._drag_pos = None
                    return
            self._drag_pos = event.globalPos() - self._window.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if (
            QGuiApplication.platformName() != "wayland"
            and event.buttons() & Qt.LeftButton
            and self._drag_pos
            and not self._window.isMaximized()
        ):
            self._window.move(event.globalPos() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self._toggle_maximize()
        super().mouseDoubleClickEvent(event)

    def _toggle_maximize(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
            self.max_btn.setText("▢")
        else:
            self._window.showMaximized()
            self.max_btn.setText("❐")

    def sync_state(self) -> None:
        """Sync maximize icon with window state."""
        self.max_btn.setText("❐" if self._window.isMaximized() else "▢")

    def _try_wayland_system_move(self) -> bool:
        """Request compositor-driven move on Wayland."""
        if self._window.isMaximized():
            return False
        self._window.winId()  # Force native handle creation
        window_handle = self._window.windowHandle()
        if not window_handle:
            return False
        if hasattr(window_handle, "startSystemMove"):
            return bool(window_handle.startSystemMove())
        return False

    def eventFilter(self, source, event):  # type: ignore[override]
        if source is self.title_label:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                if QGuiApplication.platformName() == "wayland" and self._try_wayland_system_move():
                    self._drag_pos = None
                    event.accept()
                    return True
                self._drag_pos = event.globalPos() - self._window.frameGeometry().topLeft()
            elif event.type() == QEvent.MouseMove and event.buttons() & Qt.LeftButton:
                if (
                    QGuiApplication.platformName() != "wayland"
                    and self._drag_pos
                    and not self._window.isMaximized()
                ):
                    self._window.move(event.globalPos() - self._drag_pos)
                    return True
            elif event.type() == QEvent.MouseButtonRelease:
                self._drag_pos = None
        return super().eventFilter(source, event)

    def _sync_side_slots(self) -> None:
        """Match left/right slot widths so the title stays truly centered."""
        menu_w = self._menu_bar.sizeHint().width()
        ctrl_w = self._controls.sizeHint().width()
        width = max(menu_w, ctrl_w)
        self._left_slot.setFixedWidth(width)
        self._right_slot.setFixedWidth(width)


class MainWindow(QMainWindow):
    """Primary application window with history and transcription display."""

    windowCloseRequested = pyqtSignal()
    cancelRecordingRequested = pyqtSignal()

    def __init__(self, history_manager: HistoryManager | None = None) -> None:
        super().__init__()
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.CustomizeWindowHint)
        self.settings = QSettings("Vociferous", "MainWindow")
        self._tray_icon = None
        self._hide_notification_shown = False

        # History manager (create default if not provided)
        self.history_manager = history_manager or HistoryManager()
        
        # Track currently loaded entry for editing
        self._current_entry_timestamp: str | None = None

        # Menu bar (constructed before title bar so it can be embedded)
        self._menu_bar = QMenuBar(self)

        # Custom title bar with menu + controls in one row
        self.title_bar = TitleBar(self, self._menu_bar)

        self._init_ui()
        self._create_menu_bar()
        self._create_shortcuts()
        self._restore_geometry()

    def _init_ui(self) -> None:
        """Initialize the main UI layout."""
        self.setWindowTitle("Vociferous")
        self.setMinimumSize(600, 400)

        # Unified header: place the composed title bar (menu + title + controls) as menu widget
        self.setMenuWidget(self.title_bar)

        central = QWidget(self)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Recording status indicator with pulse animation
        self._setup_recording_indicator()

        # Fixed panels without resize handle: use horizontal layout
        panels_layout = QHBoxLayout()
        panels_layout.setContentsMargins(0, 0, 0, 0)
        panels_layout.setSpacing(8)

        # Left: History panel with header
        history_panel = self._create_history_panel()
        # Right: Current transcription display
        current_panel = self._create_current_panel()

        panels_layout.addWidget(history_panel, 1)
        panels_layout.addWidget(current_panel, 1)

        main_layout.addLayout(panels_layout)

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
        header = QLabel("Trasncription History")
        header.setObjectName("historyHeader")
        header.setAlignment(Qt.AlignCenter)
        header.setFixedHeight(66)
        layout.addWidget(header)

        # Content layout with padding
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(8, 0, 8, 8)

        # History widget (create but don't load yet - buttons must exist first)
        self.history_widget = HistoryWidget(self.history_manager)
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

        # Now connect and load history (buttons exist, so _update_history_actions is safe)
        self.history_widget.historyCountChanged.connect(self._update_history_actions)
        self.history_widget.load_history()
        self._update_history_actions(self.history_widget.entry_count())

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

        # Large text display - now editable
        self.transcription_display = QTextEdit()
        self.transcription_display.setReadOnly(False)
        self.transcription_display.setPlaceholderText(
            "Your transcription will appear here..."
        )
        self.transcription_display.setFont(QFont("Monospace", 11))
        self.transcription_display.setAccessibleName("Current Transcription")
        self.transcription_display.setAccessibleDescription(
            "Display of the most recent transcription result. Editable with Save button."
        )
        self.transcription_display.textChanged.connect(self._on_text_edited)
        content_layout.addWidget(self.transcription_display)

        # Button row with recording indicator in center
        button_layout = QHBoxLayout()

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setObjectName("transcriptionButton")
        self.copy_btn.setToolTip("Copy current transcription to clipboard (Ctrl+C)")
        self.copy_btn.clicked.connect(self._copy_current)
        self.copy_btn.setAccessibleName("Copy Current Transcription")
        button_layout.addWidget(self.copy_btn)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("transcriptionButton")
        self.save_btn.setToolTip("Save edited transcription (Ctrl+S)")
        self.save_btn.clicked.connect(self._save_current)
        self.save_btn.setAccessibleName("Save Edited Transcription")
        self.save_btn.setEnabled(False)  # Disabled until editing
        button_layout.addWidget(self.save_btn)

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

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("transcriptionButton")
        self.cancel_btn.setToolTip("Cancel recording without transcribing")
        self.cancel_btn.clicked.connect(self.cancelRecordingRequested.emit)
        self.cancel_btn.setAccessibleName("Cancel Recording")
        button_layout.addWidget(self.cancel_btn)

        content_layout.addLayout(button_layout)
        content_widget.setLayout(content_layout)
        layout.addWidget(content_widget)

        panel.setLayout(layout)
        return panel

    def _create_menu_bar(self) -> None:
        """Create menu bar with all menus."""
        menu_bar: QMenuBar = self._menu_bar

        # File menu
        file_menu = menu_bar.addMenu("&File")
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu

        # History menu
        history_menu = menu_bar.addMenu("&History")
        self.export_action = QAction("Export...", self)
        self.export_action.triggered.connect(self._export_history)
        history_menu.addAction(self.export_action)

        open_history_action = QAction("Open History File", self)
        open_history_action.triggered.connect(self._open_history_file)
        history_menu.addAction(open_history_action)

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
        self.export_shortcut = QShortcut(QKeySequence("Ctrl+E"), self)
        self.export_shortcut.activated.connect(self._export_history)

        # Ctrl+H: Focus history
        focus_history_shortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        focus_history_shortcut.activated.connect(lambda: self.history_widget.setFocus())

        # Ctrl+L: Clear display
        clear_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        clear_shortcut.activated.connect(self._clear_current)
        
        # Ctrl+S: Save current
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self._save_current)

        # Sync enabled state with history availability
        self._update_history_actions()

    def _update_history_actions(self, count: int | None = None) -> None:
        """Enable or disable export controls based on history count."""
        entries = count if count is not None else self.history_widget.entry_count()
        enabled = entries > 0

        if self.history_export_btn:
            self.history_export_btn.setEnabled(enabled)

        if hasattr(self, "export_action"):
            self.export_action.setEnabled(enabled)

        if hasattr(self, "export_shortcut"):
            self.export_shortcut.setEnabled(enabled)

    def _setup_recording_indicator(self) -> None:
        """Create compact pulsing recording indicator label."""
        self.recording_indicator = QLabel("Recording")
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
                border: 1px solid #3c3c3c;
                border-radius: 6px;
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

            /* Title bar */
            QWidget#titleBar {
                background-color: #1e1e1e;
                border: none;
            }

            QLabel#titleBarLabel {
                color: #d4d4d4;
                font-weight: bold;
                font-size: 18px;
                qproperty-alignment: AlignCenter;
            }

            QToolButton#titleBarControl, QToolButton#titleBarClose {
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                padding: 0px;
                margin: 0px;
                font-size: 14px;
            }

            QToolButton#titleBarControl:hover {
                background-color: #2d3d4d;
                border-color: #5a9fd4;
            }

            QToolButton#titleBarClose {
                color: #ff6b6b;
            }

            QToolButton#titleBarClose:hover {
                background-color: #5a2d2d;
                border-color: #ff6b6b;
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
            }

            /* Hide horizontal scrollbar in history */
            QListWidget QScrollBar:horizontal {
                height: 0px;
            }
            
            QListWidget::item {
                padding: 12px;
                margin: 4px;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                background-color: #2a2a2a;
                outline: none;
            }
            
            QListWidget::item:selected {
                background-color: #2d5a7b;
                border: 1px solid #5a9fd4;
            }
            
            QListWidget::item:hover {
                background-color: #2d3d4d;
                border: 1px solid #5a9fd4;
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
                background-color: #1e1e1e;
                color: #d4d4d4;
                border-bottom: 1px solid #3c3c3c;
                font-size: 14px;
                padding: 0px;
                margin: 0px;
                border: none;
            }
            
            QMenuBar::item {
                padding: 0px 8px;
                margin: 0px;
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
            
            /* Splitter handle tweaks are done via a custom handle class. */
            
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
            
            /* Tooltips - match button appearance */
            QToolTip {
                background-color: #252526;
                color: #5a9fd4;
                border: 1px solid #5a9fd4;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
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
                self.recording_indicator.setText("Recording")
                self.recording_indicator.setStyleSheet("color: #ff6b6b; font-size: 16px;")
                self._start_recording_pulse()
            case "transcribing":
                self._stop_recording_pulse()
                self.recording_indicator.setText("Transcribing")
                self.recording_indicator.setStyleSheet("color: #ffa500; font-size: 16px;")
                self.indicator_opacity.setOpacity(1.0)
                self.recording_indicator.setVisible(True)
            case "error" | _:
                self._stop_recording_pulse()

    def display_transcription(self, entry: HistoryEntry) -> None:
        """Display a transcription and mark it as the current editable entry."""
        self.transcription_display.setPlainText(entry.text)

        # Add to history widget using the persisted entry (keeps timestamps aligned)
        self.history_widget.add_entry(entry)

        # Track new entry as current (for potential edits)
        self._current_entry_timestamp = entry.timestamp
        self.save_btn.setEnabled(False)  # Reset save button state

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
        self._current_entry_timestamp = None
        self.save_btn.setEnabled(False)
    
    def _on_text_edited(self) -> None:
        """Enable save button when text is edited."""
        if self._current_entry_timestamp:
            self.save_btn.setEnabled(True)
    
    def _save_current(self) -> None:
        """Save the edited transcription back to history."""
        if not self._current_entry_timestamp:
            return
        
        new_text = self.transcription_display.toPlainText()
        if not new_text:
            return
        
        # Update in history manager
        success = self.history_manager.update_entry(
            self._current_entry_timestamp,
            new_text
        )
        
        if success:
            # Reload history to show updated entry
            self.history_widget.load_history()
            self.save_btn.setEnabled(False)
            self.statusBar().showMessage("Saved changes", 2000)
        else:
            QMessageBox.warning(
                self,
                "Save Failed",
                "Could not save changes. Entry may have been deleted."
            )
    
    def load_entry_for_edit(self, text: str, timestamp: str) -> None:
        """Load a history entry into the transcription display for editing."""
        if not text or not timestamp:
            self.transcription_display.clear()
            self._current_entry_timestamp = None
            self.save_btn.setEnabled(False)
            return

        self.transcription_display.setPlainText(text)
        self._current_entry_timestamp = timestamp
        self.save_btn.setEnabled(False)  # Not edited yet

    def _export_history(self) -> None:
        """Show file dialog and export history."""
        if self.history_widget.entry_count() == 0:
            self.statusBar().showMessage("No history to export", 2000)
            return

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export History",
            str(Path.home() / "vociferous_history.txt"),
            "Text Files (*.txt);;CSV Files (*.csv);;Markdown Files (*.md)",
            options=QFileDialog.DontUseNativeDialog,
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
            self._update_history_actions(0)

    def _open_history_file(self) -> None:
        """Open the history JSONL file in the default system handler."""
        path = getattr(self.history_manager, "history_file", None)
        if not path:
            QMessageBox.warning(self, "History File", "History file path is unavailable.")
            return

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(self, "History File", f"Could not prepare history file:\n{exc}")
            return

        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        if not opened:
            QMessageBox.warning(
                self,
                "History File",
                f"Could not open history file at:\n{path}",
            )

    def _restore_geometry(self) -> None:
        """Restore window geometry from settings."""
        geometry = self.settings.value("geometry")

        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(1000, 700)
            self._center_on_screen()

            # No splitter state to restore with fixed panels

    def _center_on_screen(self) -> None:
        """Center window on screen."""
        screen = self.screen().availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(screen.center())
        self.move(frame.topLeft())

    def resizeEvent(self, event) -> None:
        """Handle window resize with responsive layout."""
        super().resizeEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Hide to tray and emit a one-time notification before exiting."""
        self.settings.setValue("geometry", self.saveGeometry())

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

    def changeEvent(self, event) -> None:  # type: ignore[override]
        """Sync title bar button state on window state changes."""
        if event.type() == QEvent.WindowStateChange and hasattr(self, "title_bar"):
            self.title_bar.sync_state()
        super().changeEvent(event)
