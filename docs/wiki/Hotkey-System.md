# Hotkey System

The hotkey system uses pluggable backends to detect key combinations across display servers.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       KeyListener                            │
│  - Manages backends                                          │
│  - Parses key combinations                                   │
│  - Tracks KeyChord state                                     │
│  - Triggers callbacks on activation/deactivation             │
└─────────────────────────────────────────────────────────────┘
                              │
                    uses (Protocol pattern)
                              │
              ┌───────────────┴───────────────┐
              │                               │
      ┌───────▼───────┐              ┌────────▼────────┐
      │  EvdevBackend │              │  PynputBackend  │
      │  (Wayland)    │              │  (X11)          │
      └───────────────┘              └─────────────────┘
```

## Backends

### EvdevBackend (Wayland)

Reads directly from Linux input devices (`/dev/input/event*`):

```python
import evdev

devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

for device in devices:
    for event in device.read():
        if event.type == evdev.ecodes.EV_KEY:
            # Handle key event
```

**Requirements:**
- User must be in `input` group
- Works on both Wayland and X11
- No window focus required (global hotkeys)

### PynputBackend (X11)

Uses pynput library for cross-platform input monitoring:

```python
from pynput import keyboard

listener = keyboard.Listener(
    on_press=handle_press,
    on_release=handle_release
)
listener.start()
```

**Requirements:**
- X11 display server (or XWayland)
- python3-xlib on some systems

## Key Chord Detection

A `KeyChord` tracks which keys must be pressed together:

```python
# Single key
chord = KeyChord({KeyCode.BACKQUOTE})

# Modifier + key
chord = KeyChord({KeyCode.CTRL_LEFT, KeyCode.SPACE})

# Any modifier variant (left or right)
ctrl_group = frozenset({KeyCode.CTRL_LEFT, KeyCode.CTRL_RIGHT})
chord = KeyChord({ctrl_group, KeyCode.SPACE})
```

The chord is "active" when all required keys are pressed:

```python
chord.update(KeyCode.CTRL_LEFT, InputEvent.KEY_PRESS)  # partial
chord.update(KeyCode.SPACE, InputEvent.KEY_PRESS)      # active!
chord.update(KeyCode.SPACE, InputEvent.KEY_RELEASE)    # inactive
```

## Configuration

```yaml
recording_options:
  activation_key: alt_right    # Single key
  # Or: ctrl+space             # Modifier + key
  input_backend: auto          # auto, evdev, or pynput
```

## Hotkey String Format

Keys are specified in lowercase, joined by `+`:

| Example | Keys |
|---------|------|
| `alt_right` | Right Alt only |
| `ctrl+space` | Ctrl (either) + Space |
| `ctrl+shift+a` | Ctrl + Shift + A |
| `f13` | F13 key |

Modifiers (`ctrl`, `shift`, `alt`, `meta`) match either left or right variants.

## Capture Mode

For hotkey rebinding, the KeyListener supports capture mode:

```python
def on_capture(key: KeyCode, event: InputEvent):
    if event == InputEvent.KEY_PRESS:
        print(f"User pressed: {key}")

key_listener.enable_capture_mode(on_capture)
# ... wait for user input ...
key_listener.disable_capture_mode()
```

In capture mode, normal hotkey detection is bypassed.

## Supported Keys

See [Keycodes Reference](Keycodes-Reference) for the complete list of supported keys.

## Troubleshooting

### evdev: Permission denied
```bash
sudo usermod -a -G input $USER
# Log out and back in
```

### pynput: Cannot open display
```bash
sudo apt install python3-xlib
export DISPLAY=:0
```

### Hotkey conflicts
Some desktop environments capture certain keys globally. Try:
- Less common keys (F13-F24, Pause, Scroll Lock)
- Keys without modifiers
- Disabling conflicting DE shortcuts

## Known Issues

The default `alt` hotkey currently captures **both** Alt keys in practice, which may temporarily reduce normal Alt-key usability while the listener is active. This is expected in the current version and planned to be improved.
