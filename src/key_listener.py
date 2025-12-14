"""
Keyboard and Mouse Input Handling Module
=========================================

This module provides a pluggable input handling system that abstracts away the
differences between Linux input backends (evdev for Wayland, pynput for X11).

Design Patterns Used
--------------------
1. **Strategy Pattern**: Multiple input backends (evdev, pynput) implement the
   same interface, allowing runtime selection based on environment.

2. **Protocol (Structural Subtyping)**: Using Python's `Protocol` instead of
   ABC enables duck typing - any class with the right methods works, no
   inheritance required. This is more Pythonic than Java-style interfaces.

3. **Observer Pattern**: Callbacks are registered for activation/deactivation
   events, decoupling input detection from business logic.

4. **Dataclass with Slots**: `KeyChord` uses `@dataclass(slots=True)` for
   memory efficiency and auto-generated `__init__`, `__repr__`, etc.

Why Two Backends?
-----------------
- **evdev**: Direct Linux kernel interface. Works on Wayland and X11, but
  requires the user to be in the `input` group. Most reliable option.

- **pynput**: Uses X11 APIs. Easy to set up but doesn't work on Wayland
  (the display server blocks cross-application input monitoring).

Python 3.12+ Features Demonstrated
----------------------------------
- `@runtime_checkable Protocol`: Enables isinstance() checks on duck-typed protocols
- `@dataclass(slots=True)`: Memory-efficient dataclasses with faster attribute access
- `match/case` statements: Clean event type handling and pattern matching
- Modern type hints: `set[KeyCode | frozenset[KeyCode]]` union in generics

Architecture
------------
    ┌─────────────────┐
    │   KeyListener   │  ← Manages backends, tracks key chords
    └────────┬────────┘
             │ uses
    ┌────────┴────────┐
    │  InputBackend   │  ← Protocol (interface)
    │    (Protocol)   │
    └────────┬────────┘
             │ implemented by
    ┌────────┴────────┬──────────────────┐
    │  EvdevBackend   │   PynputBackend  │
    │  (Wayland/X11)  │   (X11 only)     │
    └─────────────────┴──────────────────┘
"""
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol, runtime_checkable

from utils import ConfigManager

logger = logging.getLogger(__name__)


class InputEvent(Enum):
    """
    Enumeration of input event types.

    Using `auto()` automatically assigns incrementing integer values.
    This is preferred over manual numbering because:
    1. Adding new events doesn't require renumbering
    2. The actual values don't matter - we compare enum members, not values
    3. Less error-prone (no duplicate values possible)
    """
    KEY_PRESS = auto()
    KEY_RELEASE = auto()
    MOUSE_PRESS = auto()
    MOUSE_RELEASE = auto()


class KeyCode(Enum):
    """
    Unified key code enumeration across all input backends.

    This abstraction layer maps backend-specific key codes (evdev scancodes,
    pynput Key objects) to a common set of identifiers. This enables:

    1. Backend Independence: KeyChord works with any backend
    2. Configuration Portability: Saved hotkeys work across backends
    3. Testing: Unit tests can use KeyCode directly without mocking backends

    The full list includes modifiers, function keys, letters, numbers,
    special keys, media keys, and mouse buttons for comprehensive coverage.
    """
    # Modifier keys
    CTRL_LEFT = auto()
    CTRL_RIGHT = auto()
    SHIFT_LEFT = auto()
    SHIFT_RIGHT = auto()
    ALT_LEFT = auto()
    ALT_RIGHT = auto()
    META_LEFT = auto()
    META_RIGHT = auto()

    # Function keys
    F1 = auto()
    F2 = auto()
    F3 = auto()
    F4 = auto()
    F5 = auto()
    F6 = auto()
    F7 = auto()
    F8 = auto()
    F9 = auto()
    F10 = auto()
    F11 = auto()
    F12 = auto()
    F13 = auto()
    F14 = auto()
    F15 = auto()
    F16 = auto()
    F17 = auto()
    F18 = auto()
    F19 = auto()
    F20 = auto()
    F21 = auto()
    F22 = auto()
    F23 = auto()
    F24 = auto()

    # Number keys
    ONE = auto()
    TWO = auto()
    THREE = auto()
    FOUR = auto()
    FIVE = auto()
    SIX = auto()
    SEVEN = auto()
    EIGHT = auto()
    NINE = auto()
    ZERO = auto()

    # Letter keys
    A = auto()
    B = auto()
    C = auto()
    D = auto()
    E = auto()
    F = auto()
    G = auto()
    H = auto()
    I = auto()
    J = auto()
    K = auto()
    L = auto()
    M = auto()
    N = auto()
    O = auto()
    P = auto()
    Q = auto()
    R = auto()
    S = auto()
    T = auto()
    U = auto()
    V = auto()
    W = auto()
    X = auto()
    Y = auto()
    Z = auto()

    # Special keys
    SPACE = auto()
    ENTER = auto()
    TAB = auto()
    BACKSPACE = auto()
    ESC = auto()
    INSERT = auto()
    DELETE = auto()
    HOME = auto()
    END = auto()
    PAGE_UP = auto()
    PAGE_DOWN = auto()
    CAPS_LOCK = auto()
    NUM_LOCK = auto()
    SCROLL_LOCK = auto()
    PAUSE = auto()
    PRINT_SCREEN = auto()

    # Arrow keys
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()

    # Numpad keys
    NUMPAD_0 = auto()
    NUMPAD_1 = auto()
    NUMPAD_2 = auto()
    NUMPAD_3 = auto()
    NUMPAD_4 = auto()
    NUMPAD_5 = auto()
    NUMPAD_6 = auto()
    NUMPAD_7 = auto()
    NUMPAD_8 = auto()
    NUMPAD_9 = auto()
    NUMPAD_ADD = auto()
    NUMPAD_SUBTRACT = auto()
    NUMPAD_MULTIPLY = auto()
    NUMPAD_DIVIDE = auto()
    NUMPAD_DECIMAL = auto()
    NUMPAD_ENTER = auto()

    # Additional special characters
    MINUS = auto()
    EQUALS = auto()
    LEFT_BRACKET = auto()
    RIGHT_BRACKET = auto()
    SEMICOLON = auto()
    QUOTE = auto()
    BACKQUOTE = auto()
    BACKSLASH = auto()
    COMMA = auto()
    PERIOD = auto()
    SLASH = auto()

    # Media keys
    MUTE = auto()
    VOLUME_DOWN = auto()
    VOLUME_UP = auto()
    PLAY_PAUSE = auto()
    NEXT_TRACK = auto()
    PREV_TRACK = auto()

    # Additional Media and Special Function Keys
    MEDIA_PLAY = auto()
    MEDIA_PAUSE = auto()
    MEDIA_PLAY_PAUSE = auto()
    MEDIA_STOP = auto()
    MEDIA_PREVIOUS = auto()
    MEDIA_NEXT = auto()
    MEDIA_REWIND = auto()
    MEDIA_FAST_FORWARD = auto()
    AUDIO_MUTE = auto()
    AUDIO_VOLUME_UP = auto()
    AUDIO_VOLUME_DOWN = auto()
    MEDIA_SELECT = auto()
    WWW = auto()
    MAIL = auto()
    CALCULATOR = auto()
    COMPUTER = auto()
    APP_SEARCH = auto()
    APP_HOME = auto()
    APP_BACK = auto()
    APP_FORWARD = auto()
    APP_STOP = auto()
    APP_REFRESH = auto()
    APP_BOOKMARKS = auto()
    BRIGHTNESS_DOWN = auto()
    BRIGHTNESS_UP = auto()
    DISPLAY_SWITCH = auto()
    KEYBOARD_ILLUMINATION_TOGGLE = auto()
    KEYBOARD_ILLUMINATION_DOWN = auto()
    KEYBOARD_ILLUMINATION_UP = auto()
    EJECT = auto()
    SLEEP = auto()
    WAKE = auto()
    EMOJI = auto()
    MENU = auto()
    CLEAR = auto()
    LOCK = auto()

    # Mouse Buttons
    MOUSE_LEFT = auto()
    MOUSE_RIGHT = auto()
    MOUSE_MIDDLE = auto()
    MOUSE_BACK = auto()
    MOUSE_FORWARD = auto()
    MOUSE_SIDE1 = auto()
    MOUSE_SIDE2 = auto()
    MOUSE_SIDE3 = auto()

@runtime_checkable
class InputBackend(Protocol):
    """
    Protocol defining the interface for input backends.

    In Python, a Protocol is a way to define an interface using structural
    subtyping (duck typing) rather than nominal subtyping (inheritance).

    Key Concepts:
    -------------
    - **Protocol vs ABC**: Unlike Abstract Base Classes, you don't need to
      inherit from Protocol. Any class with matching methods is compatible.

    - **@runtime_checkable**: This decorator enables `isinstance()` checks:
      `isinstance(my_backend, InputBackend)` returns True if the object
      has all required methods, even without explicit inheritance.

    - **Ellipsis (...)**: In Protocol methods, `...` indicates the method
      signature without implementation. It's NOT the same as `pass` - it
      signals "this is a protocol stub".

    Why Protocol over ABC here?
    ---------------------------
    The backends (EvdevBackend, PynputBackend) have different internal
    implementations and state. Protocol lets them be completely independent
    classes while still being type-safe. This is particularly useful when
    testing - you can create a mock backend without inheriting anything.

    Example:
        >>> class MockBackend:
        ...     @classmethod
        ...     def is_available(cls): return True
        ...     def start(self): pass
        ...     def stop(self): pass
        ...     def on_input_event(self, event): pass
        >>> isinstance(MockBackend(), InputBackend)  # True!
    """

    @classmethod
    def is_available(cls) -> bool:
        """
        Check if this input backend is available on the current system.

        Returns:
            bool: True if the backend is available, False otherwise.
        """
        ...

    def start(self) -> None:
        """
        Start the input backend.

        Initialize resources and begin listening for input events.
        """
        ...

    def stop(self) -> None:
        """
        Stop the input backend.

        Clean up resources and stop listening for input events.
        """
        ...

    def on_input_event(self, event: tuple[KeyCode, InputEvent]) -> None:
        """
        Handle an input event.

        Called when an input event is detected.

        Args:
            event: Tuple of (KeyCode, InputEvent) for the key and event type.
        """
        ...

@dataclass(slots=True)
class KeyChord:
    """
    Represents a hotkey combination (e.g., Ctrl+Shift+Space).

    This class tracks which keys are currently pressed and determines when
    the entire chord is active (all required keys held simultaneously).

    Dataclass Features Used:
    ------------------------
    - **slots=True**: Creates `__slots__` instead of `__dict__` for attributes.
      This saves ~50 bytes per instance and speeds up attribute access.
      Perfect for objects created frequently (every key event creates one).

    - **field(default_factory=set)**: For mutable defaults (lists, sets, dicts),
      you MUST use `field(default_factory=...)`. Using `pressed_keys: set = set()`
      would share one set across ALL instances (a classic Python gotcha).

    Type Hint Explanation:
    ----------------------
    `keys: set[KeyCode | frozenset[KeyCode]]`

    This allows two types of elements in the keys set:
    1. `KeyCode` - A specific key (e.g., `KeyCode.SPACE`)
    2. `frozenset[KeyCode]` - Any key from a group (e.g., either Ctrl key)

    Why frozenset? Because `{KeyCode.CTRL_LEFT, KeyCode.CTRL_RIGHT}` represents
    "either control key", and we need it hashable (sets require hashable items).

    Attributes:
        keys: The keys/key-groups required for this chord
        pressed_keys: Currently held keys (updated on each event)
    """
    keys: set[KeyCode | frozenset[KeyCode]]
    pressed_keys: set[KeyCode] = field(default_factory=set)

    def update(self, key: KeyCode, event_type: InputEvent) -> bool:
        """Update the state of pressed keys and check if the chord is active."""
        match event_type:
            case InputEvent.KEY_PRESS:
                self.pressed_keys.add(key)
            case InputEvent.KEY_RELEASE:
                self.pressed_keys.discard(key)
        return self.is_active()

    def is_active(self) -> bool:
        """Check if all keys in the chord are currently pressed."""
        return all(
            any(k in self.pressed_keys for k in key) if isinstance(key, frozenset)
            else key in self.pressed_keys
            for key in self.keys
        )

class KeyListener:
    """
    Manages input backends and listens for specific key combinations.

    This is the main entry point for hotkey detection. It:
    1. Discovers available backends (evdev, pynput)
    2. Selects the best one based on configuration
    3. Tracks key state to detect chord activation
    4. Dispatches callbacks when hotkeys are pressed/released

    Design Decisions:
    -----------------
    - **Callback-based**: Instead of returning events, we use callbacks.
      This decouples the listener from the rest of the app - the main module
      doesn't need to poll or manage threads.

    - **Backend Auto-selection**: By default, evdev is preferred (works on
      Wayland), but the user can override in config.

    - **Chord Abstraction**: Keys are grouped into "chords" (combinations).
      This supports both single-key hotkeys (`) and combos (Ctrl+Shift+R).

    Thread Safety:
    --------------
    The KeyListener itself doesn't need locks - backend selection happens
    once at startup, and callback lists aren't modified after init.
    The backends handle their own threading (evdev runs a listener thread).

    Attributes:
        backends: List of available InputBackend implementations
        active_backend: The currently selected backend
        key_chord: The hotkey combination being monitored
        callbacks: Dict mapping event names to callback functions
    """

    def __init__(self) -> None:
        """Initialize the KeyListener with backends and activation keys."""
        self.backends: list[InputBackend] = []
        self.active_backend: InputBackend | None = None
        self.key_chord: KeyChord | None = None
        self.callbacks: dict[str, list[Callable[[], None]]] = {
            "on_activate": [],
            "on_deactivate": []
        }
        self.capture_mode: bool = False
        self.capture_callback: Callable[[KeyCode, InputEvent], None] | None = None
        self.load_activation_keys()
        self.initialize_backends()
        self.select_backend_from_config()

    def initialize_backends(self) -> None:
        """Initialize available input backends."""
        backend_classes = [EvdevBackend, PynputBackend]
        self.backends = [cls() for cls in backend_classes if cls.is_available()]

    def select_backend_from_config(self) -> None:
        """Select the active backend based on configuration."""
        preferred_backend = ConfigManager.get_config_value(
            'recording_options', 'input_backend'
        )

        match preferred_backend:
            case 'auto':
                self.select_active_backend()
            case 'evdev':
                self._try_set_backend(EvdevBackend)
            case 'pynput':
                self._try_set_backend(PynputBackend)
            case _:
                logger.warning(
                    f"Unknown backend '{preferred_backend}'. Falling back to auto."
                )
                self.select_active_backend()

    def _try_set_backend(self, backend_class: type) -> None:
        """Try to set a specific backend, fall back to auto if unavailable."""
        try:
            self.set_active_backend(backend_class)
        except ValueError:
            name = backend_class.__name__
            logger.warning(f"Backend '{name}' unavailable. Using auto.")
            self.select_active_backend()

    def select_active_backend(self) -> None:
        """Select the first available backend as active."""
        if not self.backends:
            raise RuntimeError("No supported input backend found")
        self.active_backend = self.backends[0]
        self.active_backend.on_input_event = self.on_input_event

    def set_active_backend(self, backend_class: type) -> None:
        """Set a specific backend as active."""
        new_backend = next(
            (b for b in self.backends if isinstance(b, backend_class)), None
        )
        if new_backend:
            if self.active_backend:
                self.stop()
            self.active_backend = new_backend
            self.active_backend.on_input_event = self.on_input_event
            self.start()
        else:
            raise ValueError(f"Backend {backend_class.__name__} is not available")

    def update_backend(self) -> None:
        """Update the active backend based on current configuration."""
        self.select_backend_from_config()

    def start(self) -> None:
        """Start the active backend."""
        if self.active_backend:
            self.active_backend.start()
        else:
            raise RuntimeError("No active backend selected")

    def stop(self) -> None:
        """Stop the active backend."""
        if self.active_backend:
            self.active_backend.stop()

    def load_activation_keys(self) -> None:
        """Load activation keys from configuration."""
        key_combination = ConfigManager.get_config_value(
            'recording_options', 'activation_key'
        )
        keys = self.parse_key_combination(key_combination)
        self.set_activation_keys(keys)

    def parse_key_combination(
        self, combination_string: str
    ) -> set[KeyCode | frozenset[KeyCode]]:
        """Parse a string representation of key combination into a set of KeyCodes."""
        modifier_map: dict[str, frozenset[KeyCode]] = {
            'CTRL': frozenset({KeyCode.CTRL_LEFT, KeyCode.CTRL_RIGHT}),
            'SHIFT': frozenset({KeyCode.SHIFT_LEFT, KeyCode.SHIFT_RIGHT}),
            'ALT': frozenset({KeyCode.ALT_LEFT, KeyCode.ALT_RIGHT}),
            'META': frozenset({KeyCode.META_LEFT, KeyCode.META_RIGHT}),
        }

        keys: set[KeyCode | frozenset[KeyCode]] = set()
        for key in combination_string.upper().split('+'):
            key = key.strip()
            if key in modifier_map:
                keys.add(modifier_map[key])
            else:
                try:
                    keys.add(KeyCode[key])
                except KeyError:
                    logger.warning(f"Unknown key: {key}")
        return keys

    def set_activation_keys(self, keys: set[KeyCode | frozenset[KeyCode]]) -> None:
        """Set the activation keys for the KeyChord."""
        self.key_chord = KeyChord(keys=keys)

    def on_input_event(self, event: tuple[KeyCode, InputEvent]) -> None:
        """Handle input events and trigger callbacks for key chord changes."""
        if not self.key_chord or not self.active_backend:
            return

        key, event_type = event

        if self.capture_mode and self.capture_callback:
            self.capture_callback(key, event_type)
            return
        was_active = self.key_chord.is_active()
        is_active = self.key_chord.update(key, event_type)

        match (was_active, is_active):
            case (False, True):
                self._trigger_callbacks("on_activate")
            case (True, False):
                self._trigger_callbacks("on_deactivate")

    def enable_capture_mode(
        self, callback: Callable[[KeyCode, InputEvent], None]
    ) -> None:
        """Divert input events to a capture handler (used for hotkey rebinding)."""
        self.capture_mode = True
        self.capture_callback = callback

    def disable_capture_mode(self) -> None:
        """Exit capture mode and resume normal hotkey handling."""
        self.capture_mode = False
        self.capture_callback = None

    def add_callback(self, event: str, callback: Callable[[], None]) -> None:
        """Add a callback function for a specific event."""
        if event in self.callbacks:
            self.callbacks[event].append(callback)

    def _trigger_callbacks(self, event: str) -> None:
        """Trigger all callbacks associated with a specific event."""
        for callback in self.callbacks.get(event, []):
            callback()

    def update_activation_keys(self) -> None:
        """Update activation keys from the current configuration."""
        self.load_activation_keys()

class EvdevBackend:
    """
    Input backend using the Linux evdev subsystem for raw device access.

    This is the PRIMARY backend for Wayland environments. It reads directly
    from /dev/input/* device files, bypassing the display server entirely.

    Why evdev?
    ----------
    On Wayland, applications can't snoop on global keyboard input (by design,
    for security). But evdev reads from the Linux kernel's input subsystem,
    which works regardless of display server. The tradeoff: you need
    appropriate permissions (typically `input` group membership).

    How It Works:
    -------------
    1. Enumerate all /dev/input/event* devices
    2. Spawn a daemon thread that select()s on all devices
    3. When any device has data, read events and translate to KeyCode
    4. Call on_input_event callback with (KeyCode, InputEvent) tuple

    Thread Architecture:
    --------------------
    - Main thread: Creates backend, calls start()/stop()
    - Listener thread (daemon): Runs _listen_loop(), handles I/O
    - stop_event: threading.Event for graceful shutdown

    The daemon=True flag means the thread dies automatically when the main
    program exits, preventing orphaned background processes.

    Pattern Matching in Error Handling:
    ------------------------------------
    The _handle_device_error method uses match/case to categorize errors:

    ```python
    match error:
        case BlockingIOError() if error.errno == errno.EAGAIN:
            return True  # Expected, device is fine
        case OSError() if error.errno in (errno.EBADF, errno.ENODEV):
            return False  # Device disconnected
    ```

    This is cleaner than chained isinstance() + getattr() checks.

    Security Note:
    --------------
    Reading /dev/input requires the `input` group. This is a privileged
    operation - the user could read any keyboard input, including passwords.
    This is why X11's global keyboard hooks are considered insecure by
    comparison to Wayland's stricter security model.
    """

    @classmethod
    def is_available(cls) -> bool:
        """Check if the evdev library is available."""
        try:
            import evdev
            return True
        except ImportError:
            return False

    def __init__(self) -> None:
        """Initialize the EvdevBackend."""
        self.devices: list = []  # List of evdev.InputDevice
        self.key_map: dict[int, KeyCode] | None = None
        self.evdev = None
        self.thread: threading.Thread | None = None
        self.stop_event: threading.Event | None = None
        self.on_input_event: Callable[[tuple[KeyCode, InputEvent]], None] | None = None

    def start(self) -> None:
        """Start the evdev backend."""
        import evdev
        self.evdev = evdev
        self.key_map = self._create_key_map()

        # Initialize input devices
        self.devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        self.stop_event = threading.Event()
        self._setup_signal_handler()
        self._start_listening()

    def _setup_signal_handler(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        import signal

        def signal_handler(signum, frame):
            logger.info("Received termination signal. Stopping evdev backend...")
            self.stop()

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    def stop(self) -> None:
        """Stop the evdev backend and clean up resources."""
        from contextlib import suppress

        if self.stop_event:
            self.stop_event.set()

        if self.thread:
            self.thread.join(timeout=1)
            if self.thread.is_alive():
                logger.warning("Thread did not terminate in time. Forcing exit.")

        # Close all devices with suppress for cleaner code
        for device in self.devices:
            with suppress(Exception):
                device.close()
        self.devices = []

    def _start_listening(self) -> None:
        """Start the listening thread."""
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def _listen_loop(self) -> None:
        """Main loop for listening to input events."""
        import select
        import time

        while not self.stop_event.is_set():
            try:
                devices_snapshot = list(self.devices)
                if not devices_snapshot:
                    time.sleep(0.1)
                    continue

                r, _, _ = select.select(devices_snapshot, [], [], 0.1)

                devices_to_remove = [
                    device for device in r
                    if not self._read_device_events(device)
                ]

                for device in devices_to_remove:
                    self._remove_device(device)

            except Exception as e:
                if self.stop_event.is_set():
                    break
                logger.error(f"Unexpected error in _listen_loop: {e}")

    def _remove_device(self, device) -> None:
        """Safely remove a device from the list."""
        from contextlib import suppress

        with suppress(ValueError):
            if device in self.devices:
                self.devices.remove(device)
                with suppress(Exception):
                    device.close()

    def _read_device_events(self, device) -> bool:
        """Read events from device. Returns False if device should be removed."""
        try:
            for event in device.read():
                if event.type == self.evdev.ecodes.EV_KEY:
                    self._handle_input_event(event)
            return True
        except Exception as e:
            return self._handle_device_error(device, e)

    def _handle_device_error(self, device, error: Exception) -> bool:
        """Handle device read errors. Returns False if device should be removed."""
        import errno

        match error:
            case BlockingIOError() if error.errno == errno.EAGAIN:
                return True  # Non-blocking IO expected, device OK
            case OSError() if error.errno in (errno.EBADF, errno.ENODEV):
                logger.debug(f"Device {device.path} no longer available. Removing.")
                return False
            case _:
                logger.debug(f"Error reading device: {error}")
                return True  # Keep device, might be transient

    def _handle_input_event(self, event) -> None:
        """Process a single input event."""
        key_code, event_type = self._translate_key_event(event)
        if key_code is not None and event_type is not None:
            self.on_input_event((key_code, event_type))

    def _translate_key_event(self, event) -> tuple[KeyCode | None, InputEvent | None]:
        """Translate an evdev event to our internal representation."""
        key_event = self.evdev.categorize(event)
        if not isinstance(key_event, self.evdev.events.KeyEvent):
            return None, None

        key_code = self.key_map.get(key_event.scancode)
        if key_code is None:
            return None, None

        match key_event.keystate:
            case state if state in (key_event.key_down, key_event.key_hold):
                return key_code, InputEvent.KEY_PRESS
            case state if state == key_event.key_up:
                return key_code, InputEvent.KEY_RELEASE
            case _:
                return None, None

    def _create_key_map(self) -> dict[int, KeyCode]:
        """Create a mapping from evdev key codes to our internal KeyCode enum."""
        return {
            # Modifier keys
            self.evdev.ecodes.KEY_LEFTCTRL: KeyCode.CTRL_LEFT,
            self.evdev.ecodes.KEY_RIGHTCTRL: KeyCode.CTRL_RIGHT,
            self.evdev.ecodes.KEY_LEFTSHIFT: KeyCode.SHIFT_LEFT,
            self.evdev.ecodes.KEY_RIGHTSHIFT: KeyCode.SHIFT_RIGHT,
            self.evdev.ecodes.KEY_LEFTALT: KeyCode.ALT_LEFT,
            self.evdev.ecodes.KEY_RIGHTALT: KeyCode.ALT_RIGHT,
            self.evdev.ecodes.KEY_LEFTMETA: KeyCode.META_LEFT,
            self.evdev.ecodes.KEY_RIGHTMETA: KeyCode.META_RIGHT,

            # Function keys
            self.evdev.ecodes.KEY_F1: KeyCode.F1,
            self.evdev.ecodes.KEY_F2: KeyCode.F2,
            self.evdev.ecodes.KEY_F3: KeyCode.F3,
            self.evdev.ecodes.KEY_F4: KeyCode.F4,
            self.evdev.ecodes.KEY_F5: KeyCode.F5,
            self.evdev.ecodes.KEY_F6: KeyCode.F6,
            self.evdev.ecodes.KEY_F7: KeyCode.F7,
            self.evdev.ecodes.KEY_F8: KeyCode.F8,
            self.evdev.ecodes.KEY_F9: KeyCode.F9,
            self.evdev.ecodes.KEY_F10: KeyCode.F10,
            self.evdev.ecodes.KEY_F11: KeyCode.F11,
            self.evdev.ecodes.KEY_F12: KeyCode.F12,

            # Number keys
            self.evdev.ecodes.KEY_1: KeyCode.ONE,
            self.evdev.ecodes.KEY_2: KeyCode.TWO,
            self.evdev.ecodes.KEY_3: KeyCode.THREE,
            self.evdev.ecodes.KEY_4: KeyCode.FOUR,
            self.evdev.ecodes.KEY_5: KeyCode.FIVE,
            self.evdev.ecodes.KEY_6: KeyCode.SIX,
            self.evdev.ecodes.KEY_7: KeyCode.SEVEN,
            self.evdev.ecodes.KEY_8: KeyCode.EIGHT,
            self.evdev.ecodes.KEY_9: KeyCode.NINE,
            self.evdev.ecodes.KEY_0: KeyCode.ZERO,

            # Letter keys
            self.evdev.ecodes.KEY_A: KeyCode.A,
            self.evdev.ecodes.KEY_B: KeyCode.B,
            self.evdev.ecodes.KEY_C: KeyCode.C,
            self.evdev.ecodes.KEY_D: KeyCode.D,
            self.evdev.ecodes.KEY_E: KeyCode.E,
            self.evdev.ecodes.KEY_F: KeyCode.F,
            self.evdev.ecodes.KEY_G: KeyCode.G,
            self.evdev.ecodes.KEY_H: KeyCode.H,
            self.evdev.ecodes.KEY_I: KeyCode.I,
            self.evdev.ecodes.KEY_J: KeyCode.J,
            self.evdev.ecodes.KEY_K: KeyCode.K,
            self.evdev.ecodes.KEY_L: KeyCode.L,
            self.evdev.ecodes.KEY_M: KeyCode.M,
            self.evdev.ecodes.KEY_N: KeyCode.N,
            self.evdev.ecodes.KEY_O: KeyCode.O,
            self.evdev.ecodes.KEY_P: KeyCode.P,
            self.evdev.ecodes.KEY_Q: KeyCode.Q,
            self.evdev.ecodes.KEY_R: KeyCode.R,
            self.evdev.ecodes.KEY_S: KeyCode.S,
            self.evdev.ecodes.KEY_T: KeyCode.T,
            self.evdev.ecodes.KEY_U: KeyCode.U,
            self.evdev.ecodes.KEY_V: KeyCode.V,
            self.evdev.ecodes.KEY_W: KeyCode.W,
            self.evdev.ecodes.KEY_X: KeyCode.X,
            self.evdev.ecodes.KEY_Y: KeyCode.Y,
            self.evdev.ecodes.KEY_Z: KeyCode.Z,

            # Special keys
            self.evdev.ecodes.KEY_SPACE: KeyCode.SPACE,
            self.evdev.ecodes.KEY_ENTER: KeyCode.ENTER,
            self.evdev.ecodes.KEY_TAB: KeyCode.TAB,
            self.evdev.ecodes.KEY_BACKSPACE: KeyCode.BACKSPACE,
            self.evdev.ecodes.KEY_ESC: KeyCode.ESC,
            self.evdev.ecodes.KEY_INSERT: KeyCode.INSERT,
            self.evdev.ecodes.KEY_DELETE: KeyCode.DELETE,
            self.evdev.ecodes.KEY_HOME: KeyCode.HOME,
            self.evdev.ecodes.KEY_END: KeyCode.END,
            self.evdev.ecodes.KEY_PAGEUP: KeyCode.PAGE_UP,
            self.evdev.ecodes.KEY_PAGEDOWN: KeyCode.PAGE_DOWN,
            self.evdev.ecodes.KEY_CAPSLOCK: KeyCode.CAPS_LOCK,
            self.evdev.ecodes.KEY_NUMLOCK: KeyCode.NUM_LOCK,
            self.evdev.ecodes.KEY_SCROLLLOCK: KeyCode.SCROLL_LOCK,
            self.evdev.ecodes.KEY_PAUSE: KeyCode.PAUSE,
            self.evdev.ecodes.KEY_SYSRQ: KeyCode.PRINT_SCREEN,

            # Arrow keys
            self.evdev.ecodes.KEY_UP: KeyCode.UP,
            self.evdev.ecodes.KEY_DOWN: KeyCode.DOWN,
            self.evdev.ecodes.KEY_LEFT: KeyCode.LEFT,
            self.evdev.ecodes.KEY_RIGHT: KeyCode.RIGHT,

            # Numpad keys
            self.evdev.ecodes.KEY_KP0: KeyCode.NUMPAD_0,
            self.evdev.ecodes.KEY_KP1: KeyCode.NUMPAD_1,
            self.evdev.ecodes.KEY_KP2: KeyCode.NUMPAD_2,
            self.evdev.ecodes.KEY_KP3: KeyCode.NUMPAD_3,
            self.evdev.ecodes.KEY_KP4: KeyCode.NUMPAD_4,
            self.evdev.ecodes.KEY_KP5: KeyCode.NUMPAD_5,
            self.evdev.ecodes.KEY_KP6: KeyCode.NUMPAD_6,
            self.evdev.ecodes.KEY_KP7: KeyCode.NUMPAD_7,
            self.evdev.ecodes.KEY_KP8: KeyCode.NUMPAD_8,
            self.evdev.ecodes.KEY_KP9: KeyCode.NUMPAD_9,
            self.evdev.ecodes.KEY_KPPLUS: KeyCode.NUMPAD_ADD,
            self.evdev.ecodes.KEY_KPMINUS: KeyCode.NUMPAD_SUBTRACT,
            self.evdev.ecodes.KEY_KPASTERISK: KeyCode.NUMPAD_MULTIPLY,
            self.evdev.ecodes.KEY_KPSLASH: KeyCode.NUMPAD_DIVIDE,
            self.evdev.ecodes.KEY_KPDOT: KeyCode.NUMPAD_DECIMAL,
            self.evdev.ecodes.KEY_KPENTER: KeyCode.NUMPAD_ENTER,

            # Additional special characters
            self.evdev.ecodes.KEY_MINUS: KeyCode.MINUS,
            self.evdev.ecodes.KEY_EQUAL: KeyCode.EQUALS,
            self.evdev.ecodes.KEY_LEFTBRACE: KeyCode.LEFT_BRACKET,
            self.evdev.ecodes.KEY_RIGHTBRACE: KeyCode.RIGHT_BRACKET,
            self.evdev.ecodes.KEY_SEMICOLON: KeyCode.SEMICOLON,
            self.evdev.ecodes.KEY_APOSTROPHE: KeyCode.QUOTE,
            self.evdev.ecodes.KEY_GRAVE: KeyCode.BACKQUOTE,
            self.evdev.ecodes.KEY_BACKSLASH: KeyCode.BACKSLASH,
            self.evdev.ecodes.KEY_COMMA: KeyCode.COMMA,
            self.evdev.ecodes.KEY_DOT: KeyCode.PERIOD,
            self.evdev.ecodes.KEY_SLASH: KeyCode.SLASH,

            # Media keys
            self.evdev.ecodes.KEY_MUTE: KeyCode.MUTE,
            self.evdev.ecodes.KEY_VOLUMEDOWN: KeyCode.VOLUME_DOWN,
            self.evdev.ecodes.KEY_VOLUMEUP: KeyCode.VOLUME_UP,
            self.evdev.ecodes.KEY_PLAYPAUSE: KeyCode.PLAY_PAUSE,
            self.evdev.ecodes.KEY_NEXTSONG: KeyCode.NEXT_TRACK,
            self.evdev.ecodes.KEY_PREVIOUSSONG: KeyCode.PREV_TRACK,

            # Additional function keys (if needed)
            self.evdev.ecodes.KEY_F13: KeyCode.F13,
            self.evdev.ecodes.KEY_F14: KeyCode.F14,
            self.evdev.ecodes.KEY_F15: KeyCode.F15,
            self.evdev.ecodes.KEY_F16: KeyCode.F16,
            self.evdev.ecodes.KEY_F17: KeyCode.F17,
            self.evdev.ecodes.KEY_F18: KeyCode.F18,
            self.evdev.ecodes.KEY_F19: KeyCode.F19,
            self.evdev.ecodes.KEY_F20: KeyCode.F20,
            self.evdev.ecodes.KEY_F21: KeyCode.F21,
            self.evdev.ecodes.KEY_F22: KeyCode.F22,
            self.evdev.ecodes.KEY_F23: KeyCode.F23,
            self.evdev.ecodes.KEY_F24: KeyCode.F24,

            # Additional Media and Special Function Keys
            self.evdev.ecodes.KEY_PLAYPAUSE: KeyCode.MEDIA_PLAY_PAUSE,
            self.evdev.ecodes.KEY_STOP: KeyCode.MEDIA_STOP,
            self.evdev.ecodes.KEY_PREVIOUSSONG: KeyCode.MEDIA_PREVIOUS,
            self.evdev.ecodes.KEY_NEXTSONG: KeyCode.MEDIA_NEXT,
            self.evdev.ecodes.KEY_REWIND: KeyCode.MEDIA_REWIND,
            self.evdev.ecodes.KEY_FASTFORWARD: KeyCode.MEDIA_FAST_FORWARD,
            self.evdev.ecodes.KEY_MUTE: KeyCode.AUDIO_MUTE,
            self.evdev.ecodes.KEY_VOLUMEUP: KeyCode.AUDIO_VOLUME_UP,
            self.evdev.ecodes.KEY_VOLUMEDOWN: KeyCode.AUDIO_VOLUME_DOWN,
            self.evdev.ecodes.KEY_MEDIA: KeyCode.MEDIA_SELECT,
            self.evdev.ecodes.KEY_WWW: KeyCode.WWW,
            self.evdev.ecodes.KEY_MAIL: KeyCode.MAIL,
            self.evdev.ecodes.KEY_CALC: KeyCode.CALCULATOR,
            self.evdev.ecodes.KEY_COMPUTER: KeyCode.COMPUTER,
            self.evdev.ecodes.KEY_SEARCH: KeyCode.APP_SEARCH,
            self.evdev.ecodes.KEY_HOMEPAGE: KeyCode.APP_HOME,
            self.evdev.ecodes.KEY_BACK: KeyCode.APP_BACK,
            self.evdev.ecodes.KEY_FORWARD: KeyCode.APP_FORWARD,
            self.evdev.ecodes.KEY_STOP: KeyCode.APP_STOP,
            self.evdev.ecodes.KEY_REFRESH: KeyCode.APP_REFRESH,
            self.evdev.ecodes.KEY_BOOKMARKS: KeyCode.APP_BOOKMARKS,
            self.evdev.ecodes.KEY_BRIGHTNESSDOWN: KeyCode.BRIGHTNESS_DOWN,
            self.evdev.ecodes.KEY_BRIGHTNESSUP: KeyCode.BRIGHTNESS_UP,
            self.evdev.ecodes.KEY_DISPLAYTOGGLE: KeyCode.DISPLAY_SWITCH,
            self.evdev.ecodes.KEY_KBDILLUMTOGGLE: KeyCode.KEYBOARD_ILLUMINATION_TOGGLE,
            self.evdev.ecodes.KEY_KBDILLUMDOWN: KeyCode.KEYBOARD_ILLUMINATION_DOWN,
            self.evdev.ecodes.KEY_KBDILLUMUP: KeyCode.KEYBOARD_ILLUMINATION_UP,
            self.evdev.ecodes.KEY_EJECTCD: KeyCode.EJECT,
            self.evdev.ecodes.KEY_SLEEP: KeyCode.SLEEP,
            self.evdev.ecodes.KEY_WAKEUP: KeyCode.WAKE,
            self.evdev.ecodes.KEY_COMPOSE: KeyCode.EMOJI,
            self.evdev.ecodes.KEY_MENU: KeyCode.MENU,
            self.evdev.ecodes.KEY_CLEAR: KeyCode.CLEAR,
            self.evdev.ecodes.KEY_SCREENLOCK: KeyCode.LOCK,

            # Mouse Buttons
            self.evdev.ecodes.BTN_LEFT: KeyCode.MOUSE_LEFT,
            self.evdev.ecodes.BTN_RIGHT: KeyCode.MOUSE_RIGHT,
            self.evdev.ecodes.BTN_MIDDLE: KeyCode.MOUSE_MIDDLE,
            self.evdev.ecodes.BTN_SIDE: KeyCode.MOUSE_BACK,
            self.evdev.ecodes.BTN_EXTRA: KeyCode.MOUSE_FORWARD,
            self.evdev.ecodes.BTN_FORWARD: KeyCode.MOUSE_SIDE1,
            self.evdev.ecodes.BTN_BACK: KeyCode.MOUSE_SIDE2,
            self.evdev.ecodes.BTN_TASK: KeyCode.MOUSE_SIDE3,
        }

    def on_input_event(self, event):
        """
        Callback method to be overridden by the KeyListener.
        This method is called for each processed input event.
        """
        pass

class PynputBackend:
    """
    Input backend using pynput for X11-style keyboard/mouse monitoring.

    This is the FALLBACK backend, primarily for X11 environments. On Wayland,
    pynput often fails or only works with XWayland applications.

    How pynput Works:
    -----------------
    Under the hood, pynput uses:
    - X11: XRecord extension (hooks into X server event stream)
    - Wayland: Falls back to uinput or fails entirely
    - macOS: Quartz event taps
    - Windows: Low-level keyboard/mouse hooks

    Why Keep Both Backends?
    -----------------------
    1. **Fallback**: If evdev isn't available (no permissions, not Linux)
    2. **Simplicity**: pynput doesn't require input group membership
    3. **Compatibility**: Some users run X11 where pynput works fine

    Listener Pattern:
    -----------------
    pynput uses callbacks rather than polling:

    ```python
    self.keyboard_listener = keyboard.Listener(
        on_press=self._on_keyboard_press,
        on_release=self._on_keyboard_release
    )
    self.keyboard_listener.start()  # Spawns internal thread
    ```

    This is the Observer pattern - we register callbacks, and pynput's
    internal thread calls them when events occur.

    Key Translation:
    ----------------
    pynput's Key enum is different from our KeyCode enum. The _create_key_map
    method builds a translation dict. This abstraction means the rest of
    the app doesn't care which backend is active - both emit the same
    (KeyCode, InputEvent) tuples.

    Limitation:
    -----------
    On Wayland without XWayland, pynput may not receive any events or may
    throw an exception at startup. That's why is_available() checks for
    the import, but actual functionality depends on the display server.
    """

    @classmethod
    def is_available(cls) -> bool:
        """Check if pynput library is available."""
        try:
            import pynput
            return True
        except ImportError:
            return False

    def __init__(self) -> None:
        """Initialize PynputBackend."""
        self.keyboard_listener = None
        self.mouse_listener = None
        self.keyboard = None
        self.mouse = None
        self.key_map: dict | None = None
        self.on_input_event: Callable[[tuple[KeyCode, InputEvent]], None] | None = None

    def start(self) -> None:
        """Start listening for keyboard and mouse events."""
        if self.keyboard is None or self.mouse is None:
            from pynput import keyboard, mouse
            self.keyboard = keyboard
            self.mouse = mouse
            self.key_map = self._create_key_map()

        self.keyboard_listener = self.keyboard.Listener(
            on_press=self._on_keyboard_press,
            on_release=self._on_keyboard_release
        )
        self.mouse_listener = self.mouse.Listener(
            on_click=self._on_mouse_click
        )
        self.keyboard_listener.start()
        self.mouse_listener.start()

    def stop(self) -> None:
        """Stop listening for keyboard and mouse events."""
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None

    def _translate_key_event(self, native_event: tuple) -> tuple[KeyCode, InputEvent]:
        """Translate a pynput event to our internal event representation."""
        pynput_key, is_press = native_event
        key_code = self.key_map.get(pynput_key, KeyCode.SPACE)
        event_type = InputEvent.KEY_PRESS if is_press else InputEvent.KEY_RELEASE
        return key_code, event_type

    def _on_keyboard_press(self, key) -> None:
        """Handle keyboard press events."""
        translated_event = self._translate_key_event((key, True))
        self.on_input_event(translated_event)

    def _on_keyboard_release(self, key) -> None:
        """Handle keyboard release events."""
        translated_event = self._translate_key_event((key, False))
        self.on_input_event(translated_event)

    def _on_mouse_click(self, x, y, button, pressed) -> None:
        """Handle mouse click events."""
        translated_event = self._translate_key_event((button, pressed))
        self.on_input_event(translated_event)

    def _create_key_map(self) -> dict:
        """Create a mapping from pynput keys to our internal KeyCode enum."""
        return {
            # Modifier keys
            self.keyboard.Key.ctrl_l: KeyCode.CTRL_LEFT,
            self.keyboard.Key.ctrl_r: KeyCode.CTRL_RIGHT,
            self.keyboard.Key.shift_l: KeyCode.SHIFT_LEFT,
            self.keyboard.Key.shift_r: KeyCode.SHIFT_RIGHT,
            self.keyboard.Key.alt_l: KeyCode.ALT_LEFT,
            self.keyboard.Key.alt_r: KeyCode.ALT_RIGHT,
            self.keyboard.Key.cmd_l: KeyCode.META_LEFT,
            self.keyboard.Key.cmd_r: KeyCode.META_RIGHT,

            # Function keys
            self.keyboard.Key.f1: KeyCode.F1,
            self.keyboard.Key.f2: KeyCode.F2,
            self.keyboard.Key.f3: KeyCode.F3,
            self.keyboard.Key.f4: KeyCode.F4,
            self.keyboard.Key.f5: KeyCode.F5,
            self.keyboard.Key.f6: KeyCode.F6,
            self.keyboard.Key.f7: KeyCode.F7,
            self.keyboard.Key.f8: KeyCode.F8,
            self.keyboard.Key.f9: KeyCode.F9,
            self.keyboard.Key.f10: KeyCode.F10,
            self.keyboard.Key.f11: KeyCode.F11,
            self.keyboard.Key.f12: KeyCode.F12,
            self.keyboard.Key.f13: KeyCode.F13,
            self.keyboard.Key.f14: KeyCode.F14,
            self.keyboard.Key.f15: KeyCode.F15,
            self.keyboard.Key.f16: KeyCode.F16,
            self.keyboard.Key.f17: KeyCode.F17,
            self.keyboard.Key.f18: KeyCode.F18,
            self.keyboard.Key.f19: KeyCode.F19,
            self.keyboard.Key.f20: KeyCode.F20,

            # Number keys
            self.keyboard.KeyCode.from_char('1'): KeyCode.ONE,
            self.keyboard.KeyCode.from_char('2'): KeyCode.TWO,
            self.keyboard.KeyCode.from_char('3'): KeyCode.THREE,
            self.keyboard.KeyCode.from_char('4'): KeyCode.FOUR,
            self.keyboard.KeyCode.from_char('5'): KeyCode.FIVE,
            self.keyboard.KeyCode.from_char('6'): KeyCode.SIX,
            self.keyboard.KeyCode.from_char('7'): KeyCode.SEVEN,
            self.keyboard.KeyCode.from_char('8'): KeyCode.EIGHT,
            self.keyboard.KeyCode.from_char('9'): KeyCode.NINE,
            self.keyboard.KeyCode.from_char('0'): KeyCode.ZERO,

            # Letter keys
            self.keyboard.KeyCode.from_char('a'): KeyCode.A,
            self.keyboard.KeyCode.from_char('b'): KeyCode.B,
            self.keyboard.KeyCode.from_char('c'): KeyCode.C,
            self.keyboard.KeyCode.from_char('d'): KeyCode.D,
            self.keyboard.KeyCode.from_char('e'): KeyCode.E,
            self.keyboard.KeyCode.from_char('f'): KeyCode.F,
            self.keyboard.KeyCode.from_char('g'): KeyCode.G,
            self.keyboard.KeyCode.from_char('h'): KeyCode.H,
            self.keyboard.KeyCode.from_char('i'): KeyCode.I,
            self.keyboard.KeyCode.from_char('j'): KeyCode.J,
            self.keyboard.KeyCode.from_char('k'): KeyCode.K,
            self.keyboard.KeyCode.from_char('l'): KeyCode.L,
            self.keyboard.KeyCode.from_char('m'): KeyCode.M,
            self.keyboard.KeyCode.from_char('n'): KeyCode.N,
            self.keyboard.KeyCode.from_char('o'): KeyCode.O,
            self.keyboard.KeyCode.from_char('p'): KeyCode.P,
            self.keyboard.KeyCode.from_char('q'): KeyCode.Q,
            self.keyboard.KeyCode.from_char('r'): KeyCode.R,
            self.keyboard.KeyCode.from_char('s'): KeyCode.S,
            self.keyboard.KeyCode.from_char('t'): KeyCode.T,
            self.keyboard.KeyCode.from_char('u'): KeyCode.U,
            self.keyboard.KeyCode.from_char('v'): KeyCode.V,
            self.keyboard.KeyCode.from_char('w'): KeyCode.W,
            self.keyboard.KeyCode.from_char('x'): KeyCode.X,
            self.keyboard.KeyCode.from_char('y'): KeyCode.Y,
            self.keyboard.KeyCode.from_char('z'): KeyCode.Z,

            # Special keys
            self.keyboard.Key.space: KeyCode.SPACE,
            self.keyboard.Key.enter: KeyCode.ENTER,
            self.keyboard.Key.tab: KeyCode.TAB,
            self.keyboard.Key.backspace: KeyCode.BACKSPACE,
            self.keyboard.Key.esc: KeyCode.ESC,
            self.keyboard.Key.insert: KeyCode.INSERT,
            self.keyboard.Key.delete: KeyCode.DELETE,
            self.keyboard.Key.home: KeyCode.HOME,
            self.keyboard.Key.end: KeyCode.END,
            self.keyboard.Key.page_up: KeyCode.PAGE_UP,
            self.keyboard.Key.page_down: KeyCode.PAGE_DOWN,
            self.keyboard.Key.caps_lock: KeyCode.CAPS_LOCK,
            self.keyboard.Key.num_lock: KeyCode.NUM_LOCK,
            self.keyboard.Key.scroll_lock: KeyCode.SCROLL_LOCK,
            self.keyboard.Key.pause: KeyCode.PAUSE,
            self.keyboard.Key.print_screen: KeyCode.PRINT_SCREEN,

            # Arrow keys
            self.keyboard.Key.up: KeyCode.UP,
            self.keyboard.Key.down: KeyCode.DOWN,
            self.keyboard.Key.left: KeyCode.LEFT,
            self.keyboard.Key.right: KeyCode.RIGHT,

            # Numpad keys
            self.keyboard.Key.num_lock: KeyCode.NUM_LOCK,
            self.keyboard.KeyCode.from_vk(96): KeyCode.NUMPAD_0,
            self.keyboard.KeyCode.from_vk(97): KeyCode.NUMPAD_1,
            self.keyboard.KeyCode.from_vk(98): KeyCode.NUMPAD_2,
            self.keyboard.KeyCode.from_vk(99): KeyCode.NUMPAD_3,
            self.keyboard.KeyCode.from_vk(100): KeyCode.NUMPAD_4,
            self.keyboard.KeyCode.from_vk(101): KeyCode.NUMPAD_5,
            self.keyboard.KeyCode.from_vk(102): KeyCode.NUMPAD_6,
            self.keyboard.KeyCode.from_vk(103): KeyCode.NUMPAD_7,
            self.keyboard.KeyCode.from_vk(104): KeyCode.NUMPAD_8,
            self.keyboard.KeyCode.from_vk(105): KeyCode.NUMPAD_9,
            self.keyboard.KeyCode.from_vk(107): KeyCode.NUMPAD_ADD,
            self.keyboard.KeyCode.from_vk(109): KeyCode.NUMPAD_SUBTRACT,
            self.keyboard.KeyCode.from_vk(106): KeyCode.NUMPAD_MULTIPLY,
            self.keyboard.KeyCode.from_vk(111): KeyCode.NUMPAD_DIVIDE,
            self.keyboard.KeyCode.from_vk(110): KeyCode.NUMPAD_DECIMAL,

            # Additional special characters
            self.keyboard.KeyCode.from_char('-'): KeyCode.MINUS,
            self.keyboard.KeyCode.from_char('='): KeyCode.EQUALS,
            self.keyboard.KeyCode.from_char('['): KeyCode.LEFT_BRACKET,
            self.keyboard.KeyCode.from_char(']'): KeyCode.RIGHT_BRACKET,
            self.keyboard.KeyCode.from_char(';'): KeyCode.SEMICOLON,
            self.keyboard.KeyCode.from_char("'"): KeyCode.QUOTE,
            self.keyboard.KeyCode.from_char('`'): KeyCode.BACKQUOTE,
            self.keyboard.KeyCode.from_char('\\'): KeyCode.BACKSLASH,
            self.keyboard.KeyCode.from_char(','): KeyCode.COMMA,
            self.keyboard.KeyCode.from_char('.'): KeyCode.PERIOD,
            self.keyboard.KeyCode.from_char('/'): KeyCode.SLASH,

            # Media keys
            self.keyboard.Key.media_volume_mute: KeyCode.AUDIO_MUTE,
            self.keyboard.Key.media_volume_down: KeyCode.AUDIO_VOLUME_DOWN,
            self.keyboard.Key.media_volume_up: KeyCode.AUDIO_VOLUME_UP,
            self.keyboard.Key.media_play_pause: KeyCode.MEDIA_PLAY_PAUSE,
            self.keyboard.Key.media_next: KeyCode.MEDIA_NEXT,
            self.keyboard.Key.media_previous: KeyCode.MEDIA_PREVIOUS,

            # Mouse buttons
            self.mouse.Button.left: KeyCode.MOUSE_LEFT,
            self.mouse.Button.right: KeyCode.MOUSE_RIGHT,
            self.mouse.Button.middle: KeyCode.MOUSE_MIDDLE,
        }

    def on_input_event(self, event):
        """
        Callback method to be set by the KeyListener.
        This method is called for each processed input event.
        """
        pass
