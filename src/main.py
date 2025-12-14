"""
Vociferous - Simple Speech-to-Text Dictation Application.

This is the main orchestration module that ties together all components:
key listening, audio recording, transcription, and text injection.

Application Architecture:
-------------------------
```
┌─────────────────────────────────────────────────────────────────┐
│                      VociferousApp (QObject)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    callback    ┌─────────────────────┐        │
│  │ KeyListener  │ ──────────────▶│ on_activation()     │        │
│  │ (evdev/      │                │ on_deactivation()   │        │
│  │  pynput)     │                └──────────┬──────────┘        │
│  └──────────────┘                           │                   │
│                                             ▼                   │
│                              ┌──────────────────────────┐       │
│                              │ ResultThread (QThread)   │       │
│                              │ • Record audio           │       │
│                              │ • Run transcription      │       │
│                              └──────────┬───────────────┘       │
│                                         │                       │
│                    Qt Signals           │                       │
│         ┌───────────────────────────────┼───────────────┐       │
│         │                               │               │       │
│         ▼                               ▼               ▼       │
│  ┌──────────────┐              ┌──────────────┐ ┌──────────────┐│
│  │ MainWindow   │              │InputSimulator│ │  Tray Icon   ││
│  │(UI + history)│              │(text inject) │ │  (status)    ││
│  └──────────────┘              └──────────────┘ └──────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

PyQt5 Concepts Demonstrated:
----------------------------

**1. QApplication and Event Loop**
The app runs an event loop (`app.exec_()`) that processes UI events,
timers, and signal/slot invocations. Everything is event-driven.

**2. Signal/Slot Pattern**
Qt's implementation of the Observer pattern. Signals are emitted by
objects, slots are methods that receive them. Key benefits:
- Type-safe (argument types are checked)
- Thread-safe (cross-thread signals are queued automatically)
- Loose coupling (emitter doesn't know about receivers)

Example from this module:
```python
self.result_thread.resultSignal.connect(self.on_transcription_complete)
#                  ↑ signal                    ↑ slot
```

**3. QThread for Background Work**
ResultThread runs audio recording and transcription off the main thread.
This keeps the UI responsive. Signals safely cross the thread boundary.

**4. System Tray Integration**
QSystemTrayIcon provides the tray icon and right-click menu. Combined
with `setQuitOnLastWindowClosed(False)`, the app runs headlessly.

**5. Resource Management**
`deleteLater()` schedules object deletion on the event loop, preventing
crashes from deleting objects that still have pending signals.

Thread Connection Management:
-----------------------------
This module tracks signal connections in `_thread_connections` list.
This allows proper cleanup when threads finish or the app exits:

```python
for signal, slot in self._thread_connections:
    signal.connect(slot)  # Connect
    # ... later ...
    signal.disconnect(slot)  # Clean disconnect
```

Without explicit disconnection, you can get:
- Memory leaks (slots keep objects alive)
- Crashes (signals delivered to deleted objects)
- Unexpected behavior (old handlers still firing)

Recording Modes:
----------------
- `press_to_toggle`: Press once to start, press again to stop
- `hold_to_record`: Hold key to record, release to stop

The mode affects which callback (on_activation vs on_deactivation)
triggers the stop_recording action.

Python 3.12+ Features:
----------------------
- Match/case for status text selection
- `list[tuple]` generic type hints without imports
"""
import logging
import subprocess
import sys
from contextlib import suppress

from PyQt5.QtCore import QObject
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QApplication, QMenu, QStyle, QSystemTrayIcon

from history_manager import HistoryManager
from key_listener import KeyListener
from result_thread import ResultThread
from transcription import create_local_model
from ui.main_window import MainWindow
from ui.settings_dialog import SettingsDialog
from utils import ConfigManager

# Optional clipboard support
try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

logger = logging.getLogger(__name__)


class VociferousApp(QObject):
    """
    Main application orchestrator for Vociferous speech-to-text.

    This class follows the Mediator pattern - it coordinates communication
    between components (KeyListener, ResultThread, MainWindow, etc.)
    without them knowing about each other.

    Lifecycle:
    ----------
    1. __init__: Create QApplication, initialize ConfigManager
    2. initialize_components: Load model, create UI, set up listeners
    3. run: Enter Qt event loop (blocking)
    4. cleanup: Stop threads, release resources
    5. exit_app: Quit event loop

    Why inherit from QObject?
    -------------------------
    QObject provides:
    - Signal/slot mechanism (not used here but available)
    - Parent-child ownership (automatic cleanup)
    - deleteLater() for safe deferred deletion
    - Thread affinity (objects belong to threads)

    Even though we don't define signals here, inheriting QObject makes
    this class a proper Qt citizen that can participate in the ecosystem.

    Attributes:
        app: QApplication instance (singleton, one per process)
        key_listener: Hotkey detection (evdev/pynput backend)
        local_model: Loaded Whisper model (kept in memory for fast inference)
        result_thread: Current recording/transcription thread (or None)
        main_window: UI showing recording/transcribing state
        tray_icon: System tray presence
        _thread_connections: Tracked signal connections for cleanup
    """

    def __init__(self) -> None:
        super().__init__()
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Vociferous")
        self.app.setQuitOnLastWindowClosed(False)  # Keep running in tray

        # Set larger base font for 2x UI scale
        font = self.app.font()
        font.setPointSize(18)
        self.app.setFont(font)

        # Initialize config
        ConfigManager.initialize()

        # Track active signal connections for cleanup
        self._thread_connections: list[tuple] = []
        self.settings_dialog: SettingsDialog | None = None

        # Initialize components
        self.initialize_components()

    def initialize_components(self) -> None:
        """
        Initialize all application components in dependency order.

        Initialization order matters:
        1. KeyListener - needs config loaded (done in __init__)
        2. Whisper model - slow, loaded early to avoid first-use delay
        3. MainWindow - needs Qt app running
        4. Tray icon
        5. Start listening - only after everything else is ready

        Why load model eagerly?
        -----------------------
        Model loading takes 2-10 seconds depending on size and device.
        Loading it at startup means the first dictation is instant.
        The tradeoff is slower startup, but better UX during use.
        """
        ConfigManager.console_print("Initializing Vociferous...")

        # Key listener for hotkey detection
        self.key_listener = KeyListener()
        self.key_listener.add_callback("on_activate", self.on_activation)
        self.key_listener.add_callback("on_deactivate", self.on_deactivation)

        # Load whisper model
        ConfigManager.console_print("Loading Whisper model (this may take a moment)...")
        self.local_model = create_local_model()

        # Result thread (for recording/transcription)
        self.result_thread = None

        # History manager for transcription storage
        self.history_manager = HistoryManager()

        # Main window (shows recording/transcribing state)
        self.main_window = MainWindow(self.history_manager)
        self.main_window.setWindowIcon(self._build_tray_icon())
        self.main_window.on_settings_requested(self.show_settings)

        # Connect history widget re-inject signal
        self.main_window.history_widget.reinjectRequested.connect(
            self.on_reinject_requested
        )

        # System tray
        self.create_tray_icon()
        self.main_window.set_tray_icon(self.tray_icon)
        self.main_window.windowCloseRequested.connect(self._on_main_window_hidden)

        # React to configuration changes
        ConfigManager.instance().configChanged.connect(self._on_config_changed)

        # Start listening for hotkey
        self.key_listener.start()

        activation_key = ConfigManager.get_config_value(
            'recording_options', 'activation_key'
        )
        ConfigManager.console_print(f"Ready! Press '{activation_key}' to start.")

    def create_tray_icon(self) -> None:
        """
        Create the system tray icon with context menu.

        System Tray Pattern:
        --------------------
        For "headless" apps that run in background:
        1. setQuitOnLastWindowClosed(False) - don't exit when windows close
        2. Create QSystemTrayIcon with icon
        3. Attach QMenu for right-click actions
        4. show() to make visible

        The tray icon serves as:
        - Visual indicator that the app is running
        - Status display (tooltip updates with state)
        - Exit point (right-click → Exit)
        """
        icon = self._build_tray_icon()
        self.tray_icon = QSystemTrayIcon(icon, self.app)

        tray_menu = QMenu()

        # Status indicator (non-clickable)
        status_action = QAction('Vociferous - Ready', self.app)
        status_action.setEnabled(False)
        tray_menu.addAction(status_action)
        self.status_action = status_action

        tray_menu.addSeparator()

        show_hide_action = QAction('Show/Hide Window', self.app)
        show_hide_action.triggered.connect(self.toggle_main_window)
        tray_menu.addAction(show_hide_action)
        self.show_hide_action = show_hide_action

        settings_action = QAction('Settings...', self.app)
        settings_action.setEnabled(True)
        settings_action.triggered.connect(self.show_settings)
        tray_menu.addAction(settings_action)
        self.settings_action = settings_action

        tray_menu.addSeparator()

        # Exit action
        exit_action = QAction('Exit', self.app)
        exit_action.triggered.connect(self.exit_app)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.setToolTip("Vociferous - Speech to Text")
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

        # Start with window shown on first launch
        self.main_window.show_and_raise()

    def toggle_main_window(self) -> None:
        """Toggle visibility of the main window."""
        if self.main_window.isVisible():
            self.main_window.hide()
        else:
            self.main_window.show_and_raise()

    def on_tray_activated(self, reason):
        """Handle tray icon activation (double-click to toggle window)."""
        if reason == QSystemTrayIcon.DoubleClick:
            self.toggle_main_window()

    def _on_main_window_hidden(self) -> None:
        """Handle window close event (currently no action needed)."""
        pass

    def show_settings(self) -> None:
        """Open the settings dialog and apply changes immediately."""
        # Create fresh dialog each time to avoid state issues
        dialog = SettingsDialog(self.key_listener, self.main_window)
        dialog.exec_()

    def _on_config_changed(self, section: str, key: str, value) -> None:
        """Handle live config updates for hotkey, backend, and model changes."""
        if section == 'recording_options' and key == 'activation_key':
            self.key_listener.update_activation_keys()
            return

        if section == 'recording_options' and key == 'input_backend':
            self.key_listener.update_backend()
            return

        # Reload model when model options change
        if section == 'model_options' and key in {'compute_type', 'device', 'language'}:
            self._reload_model()

    def _reload_model(self) -> None:
        """Reload the Whisper model with updated configuration."""
        ConfigManager.console_print("Reloading Whisper model...")
        self.local_model = create_local_model()
        ConfigManager.console_print("Model reloaded successfully.")

    def _build_tray_icon(self) -> QIcon:
        """Return a non-empty icon for the tray using theme or Qt defaults."""
        icon = QIcon.fromTheme('microphone-sensitivity-high')
        if icon.isNull():
            app_instance = QApplication.instance()
            style = self.app.style() if hasattr(self, 'app') else app_instance.style()
            icon = style.standardIcon(QStyle.SP_MediaPlay) if style else QIcon()
        return icon

    def on_activation(self):
        """Called when activation key is pressed."""
        recording_mode = ConfigManager.get_config_value(
            'recording_options', 'recording_mode'
        )

        if self.result_thread and self.result_thread.isRunning():
            # Already recording - stop it
            if recording_mode == 'press_to_toggle':
                self.result_thread.stop_recording()
            return

        # Start new recording
        self.start_result_thread()

    def on_deactivation(self):
        """Called when activation key is released (for hold_to_record mode)."""
        recording_mode = ConfigManager.get_config_value(
            'recording_options', 'recording_mode'
        )

        if (
            recording_mode == 'hold_to_record'
            and self.result_thread
            and self.result_thread.isRunning()
        ):
            self.result_thread.stop_recording()

    def start_result_thread(self):
        """
        Start a new recording and transcription thread.

        Thread Lifecycle:
        -----------------
        1. Check if thread already running (prevent double-start)
        2. Disconnect previous signals (prevent dangling connections)
        3. Create new ResultThread with loaded model
        4. Connect signals to UI and processing slots
        5. Connect finished signal for auto-cleanup
        6. Start the thread

        Signal Connection Pattern:
        --------------------------
        We store connections in `_thread_connections` list:
        ```python
        self._thread_connections = [
            (signal, slot),
            (signal, slot),
            ...
        ]
        ```

        This pattern allows:
        - Bulk connect/disconnect operations
        - Proper cleanup when thread finishes
        - Prevention of "zombie" connections

        The `finished.connect(self._on_thread_finished)` sets up auto-cleanup:
        when the thread completes, we disconnect all signals and schedule
        the thread object for deletion.
        """
        if self.result_thread and self.result_thread.isRunning():
            return

        # Clean up any previous thread connections
        self._disconnect_thread_signals()

        self.result_thread = ResultThread(self.local_model)

        # Store connections for later cleanup (allows proper disconnection)
        status_slot = self.main_window.update_transcription_status
        self._thread_connections = [
            (self.result_thread.statusSignal, status_slot),
            (self.result_thread.statusSignal, self.update_tray_status),
            (self.result_thread.resultSignal, self.on_transcription_complete),
        ]

        # Connect all signals
        for signal, slot in self._thread_connections:
            signal.connect(slot)

        # Auto-cleanup: when thread finishes, disconnect signals and schedule deletion
        self.result_thread.finished.connect(self._on_thread_finished)
        self.result_thread.start()

    def _disconnect_thread_signals(self) -> None:
        """Safely disconnect all tracked thread signal connections."""
        for signal, slot in self._thread_connections:
            with suppress(TypeError, RuntimeError):
                signal.disconnect(slot)
        self._thread_connections.clear()

    def _on_thread_finished(self) -> None:
        """Handle thread completion: cleanup signals and schedule deletion."""
        self._disconnect_thread_signals()
        if self.result_thread:
            self.result_thread.deleteLater()

    def stop_result_thread(self) -> None:
        """Stop the recording/transcription thread."""
        if self.result_thread and self.result_thread.isRunning():
            self.result_thread.stop()

    def update_tray_status(self, status: str) -> None:
        """
        Update tray icon tooltip based on current status.

        Uses match/case for clean status-to-text mapping:
        ```python
        match status:
            case 'recording':    text = '...Recording...'
            case 'transcribing': text = '...Transcribing...'
            case _:              text = '...Ready'
        ```

        The wildcard `_` case handles any unexpected status values,
        providing a safe default rather than raising an error.

        Args:
            status: Status string ('recording', 'transcribing', 'error', etc.)
        """
        match status:
            case 'recording':
                text = 'Vociferous - Recording...'
            case 'transcribing':
                text = 'Vociferous - Transcribing...'
            case 'error':
                text = 'Vociferous - Error'
            case _:
                text = 'Vociferous - Ready'
        self.status_action.setText(text)
        self.tray_icon.setToolTip(text)

    def on_transcription_complete(self, result: str) -> None:
        """
        Handle completed transcription - always copies to clipboard.

        Output Pipeline:
        1. Add to history and display in window
        2. Copy to clipboard (always enabled)

        User can then manually paste with Ctrl+V where needed.

        Args:
            result: Transcribed text (may be empty string)
        """
        if not result:
            return

        # Add to history and display in window
        self.history_manager.add_entry(result)
        self.main_window.display_transcription(result)

        # Always copy to clipboard for manual paste
        self._copy_to_clipboard(result)

    def on_reinject_requested(self, text: str) -> None:
        """
        Handle re-copy from history.

        Copies text to clipboard for manual paste.
        Does NOT add to history again.
        """
        logger.info(f"Re-copying from history: {text[:50]}...")
        self._copy_to_clipboard(text)

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard using available method."""
        if HAS_PYPERCLIP:
            with suppress(Exception):
                pyperclip.copy(text)
                logger.debug("Copied to clipboard via pyperclip")
                return

        # Fallback to wl-copy (Wayland)
        with suppress(Exception):
            subprocess.run(["wl-copy"], input=text, text=True, check=True)
            logger.debug("Copied to clipboard via wl-copy")

    def cleanup(self) -> None:
        """Clean up resources."""
        # Stop and clean up result thread
        if self.result_thread and self.result_thread.isRunning():
            self.result_thread.stop()
            self.result_thread.wait(2000)  # Wait up to 2 seconds for graceful stop
        self._disconnect_thread_signals()

        if self.key_listener:
            self.key_listener.stop()

    def exit_app(self) -> None:
        """Exit the application."""
        self.cleanup()
        QApplication.quit()

    def run(self) -> int:
        """Run the application."""
        return self.app.exec_()


if __name__ == '__main__':
    app = VociferousApp()
    sys.exit(app.run())
