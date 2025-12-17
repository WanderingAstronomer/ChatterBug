"""
Text injection module for Vociferous.

Handles copying text to clipboard and simulating Ctrl+V paste.
Supports multiple backends: pynput (X11), dotool/ydotool (Wayland).
"""
import logging
import subprocess
import time
from contextlib import suppress

from pynput.keyboard import Controller as PynputController

from utils import ConfigManager

# Optional clipboard support
try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

logger = logging.getLogger(__name__)


class InputSimulator:
    """Simulates keyboard input to inject transcribed text into applications."""

    def __init__(self) -> None:
        self.input_method: str = ''
        self.dotool_process: subprocess.Popen | None = None
        self.keyboard: PynputController | None = None
        self._configure_from_config()

    def _initialize_dotool(self) -> None:
        """Initialize dotool process for persistent Wayland input."""
        try:
            self.dotool_process = subprocess.Popen(
                "dotool",
                stdin=subprocess.PIPE,
                text=True
            )
        except FileNotFoundError:
            logger.warning('dotool not found, falling back to pynput')
            self.input_method = 'pynput'
            self.keyboard = PynputController()

    def _terminate_dotool(self) -> None:
        """Terminate dotool subprocess safely with proper cleanup to avoid zombies."""
        if self.dotool_process is None:
            return

        proc = self.dotool_process
        self.dotool_process = None  # Clear reference immediately

        with suppress(ProcessLookupError, OSError):
            # Close stdin first to signal EOF
            if proc.stdin:
                with suppress(OSError, BrokenPipeError):
                    proc.stdin.close()

            # Graceful termination with timeout
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()  # Reap to avoid zombie

    def typewrite(self, text: str) -> None:
        """
        Inject text by copying to clipboard and simulating Ctrl+V.

        IMPORTANT: Due to Wayland security restrictions, this may not work
        reliably if focus has shifted away from the target application.
        For best results, keep the target window focused when transcription completes.

        Strategy:
        ---------
        1. Copy text to clipboard
        2. Wait for modifier keys to be fully released
        3. Simulate Ctrl+V keypress to paste

        Args:
            text: The text to inject into the focused application
        """
        if not text:
            return

        # Step 1: Copy to clipboard
        self._copy_to_clipboard(text)

        # Step 2: Wait for modifier keys to be fully released
        # Longer wait (500ms) to ensure Alt key release doesn't inject a character
        time.sleep(0.5)

        # Step 3: Simulate Ctrl+V to paste
        self._simulate_paste()

    def _typewrite_pynput(self, text: str, interval: float) -> None:
        """Type using pynput (X11)."""
        for char in text:
            self.keyboard.press(char)
            self.keyboard.release(char)
            time.sleep(interval)

    def _typewrite_ydotool(self, text: str, interval: float) -> None:
        """Type using ydotool (Wayland)."""
        try:
            subprocess.run([
                "ydotool", "type",
                "--key-delay", str(int(interval * 1000)),
                "--", text
            ], check=True, capture_output=True)
        except FileNotFoundError:
            logger.error('ydotool not found! Install with: sudo pacman -S ydotool')
        except subprocess.CalledProcessError as e:
            logger.warning(f'ydotool error: {e}. Falling back to clipboard.')
            self._copy_to_clipboard(text)

    def _typewrite_dotool(self, text: str, interval: float) -> None:
        """Type using dotool (Wayland, persistent process)."""
        if not self.dotool_process or not self.dotool_process.stdin:
            logger.warning('dotool stdin unavailable, falling back to clipboard')
            self._copy_to_clipboard(text)
            return

        try:
            self.dotool_process.stdin.write(f"typedelay {int(interval * 1000)}\
")
            self.dotool_process.stdin.write(f"type {text}\
")
            self.dotool_process.stdin.flush()
        except Exception as e:
            logger.warning(f'dotool error: {e}. Falling back to clipboard.')
            self._copy_to_clipboard(text)

    def _simulate_paste(self) -> None:
        """Simulate Ctrl+V keystroke to paste clipboard content."""
        match self.input_method:
            case 'pynput':
                if self.keyboard:
                    from pynput.keyboard import Key
                    self.keyboard.press(Key.ctrl)
                    self.keyboard.press('v')
                    time.sleep(0.02)
                    self.keyboard.release('v')
                    self.keyboard.release(Key.ctrl)
            case 'dotool':
                if self.dotool_process and self.dotool_process.stdin:
                    with suppress(Exception):
                        self.dotool_process.stdin.write("key ctrl+v\n")
                        self.dotool_process.stdin.flush()
            case 'ydotool':
                with suppress(subprocess.CalledProcessError):
                    subprocess.run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"], check=True)
            case _:
                logger.warning('Cannot simulate Ctrl+V with current input method')

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard using pyperclip or wl-copy."""
        if not text:
            return

        if HAS_PYPERCLIP:
            with suppress(Exception):
                pyperclip.copy(text)
                return

        try:
            subprocess.run(["wl-copy"], input=text, text=True, check=True)
        except Exception:
            logger.error('Clipboard copy failed. Install wl-clipboard or pyperclip.')

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.input_method == 'dotool':
            self._terminate_dotool()

    def reinitialize(self) -> None:
        """Reload input method configuration and reconfigure backend."""
        self.cleanup()
        self._configure_from_config()

    def _configure_from_config(self) -> None:
        """Auto-detect and configure the best available input method."""
        configured = ConfigManager.get_config_value('output_options', 'input_method')

        # Auto-detect if not explicitly set
        if not configured or configured == 'auto':
            self.input_method = self._auto_detect_input_method()
        else:
            self.input_method = configured

        match self.input_method:
            case 'pynput':
                self.keyboard = PynputController()
            case 'dotool':
                self._initialize_dotool()
            case 'ydotool':
                self.keyboard = None
            case _:
                self.input_method = 'pynput'
                self.keyboard = PynputController()

        logger.debug(f'Input method: {self.input_method}')

    def _auto_detect_input_method(self) -> str:
        """Detect the best input method for the current display server."""
        import os
        import shutil

        # Check if running on Wayland
        wayland_display = os.environ.get('WAYLAND_DISPLAY')
        xdg_session = os.environ.get('XDG_SESSION_TYPE', '').lower()
        is_wayland = wayland_display or xdg_session == 'wayland'

        if is_wayland:
            # Prefer dotool (persistent process) over ydotool
            if shutil.which('dotool'):
                return 'dotool'
            if shutil.which('ydotool'):
                return 'ydotool'
            # Fall back to pynput (works with XWayland apps)
            logger.warning(
                'Wayland detected but no dotool/ydotool. Using pynput.'
            )

        return 'pynput'
