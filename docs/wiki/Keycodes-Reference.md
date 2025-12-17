# Keycodes Reference

Supported keycodes for hotkey binding in Vociferous.

## Modifier Keys

These match either left or right variant when used in hotkey strings:

| Config Name | Display Name |
|-------------|--------------|
| `ctrl` | Ctrl |
| `shift` | Shift |
| `alt` | Alt |
| `meta` | Meta/Super |

Specific variants:

| Config Name | Description |
|-------------|-------------|
| `ctrl_left`, `ctrl_right` | Specific Ctrl key |
| `shift_left`, `shift_right` | Specific Shift key |
| `alt_left`, `alt_right` | Specific Alt key |
| `meta_left`, `meta_right` | Specific Meta/Super key |

## Function Keys

| Config Name | Notes |
|-------------|-------|
| `f1` - `f12` | Standard function keys |
| `f13` - `f24` | Extended (some keyboards) |

## Letter Keys

`a` through `z` (lowercase in config)

## Number Keys

`0` through `9`

## Special Keys

| Config Name | Description |
|-------------|-------------|
| `space` | Spacebar |
| `enter` | Enter/Return |
| `tab` | Tab |
| `backspace` | Backspace |
| `esc` | Escape |
| `insert` | Insert |
| `delete` | Delete |
| `home` | Home |
| `end` | End |
| `page_up` | Page Up |
| `page_down` | Page Down |
| `caps_lock` | Caps Lock |
| `num_lock` | Num Lock |
| `scroll_lock` | Scroll Lock (good hotkey choice) |
| `pause` | Pause/Break (good hotkey choice) |
| `print_screen` | Print Screen |

## Arrow Keys

`up`, `down`, `left`, `right`

## Numpad Keys

| Config Name | Description |
|-------------|-------------|
| `numpad_0` - `numpad_9` | Numpad digits |
| `numpad_add` | Numpad + |
| `numpad_subtract` | Numpad - |
| `numpad_multiply` | Numpad * |
| `numpad_divide` | Numpad / |
| `numpad_decimal` | Numpad . |
| `numpad_enter` | Numpad Enter |

## Symbol Keys

| Config Name | Character |
|-------------|-----------|
| `minus` | `-` |
| `equals` | `=` |
| `left_bracket` | `[` |
| `right_bracket` | `]` |
| `semicolon` | `;` |
| `quote` | `'` |
| `backquote` | `` ` `` |
| `backslash` | `\` |
| `comma` | `,` |
| `period` | `.` |
| `slash` | `/` |

## Media Keys

| Config Name | Description |
|-------------|-------------|
| `mute` | Mute |
| `volume_down` | Volume Down |
| `volume_up` | Volume Up |
| `play_pause` | Play/Pause |
| `next_track` | Next Track |
| `prev_track` | Previous Track |

## Mouse Buttons

| Config Name | Description |
|-------------|-------------|
| `mouse_left` | Left mouse button |
| `mouse_right` | Right mouse button |
| `mouse_middle` | Middle mouse button |
| `mouse_back` | Back button (side) |
| `mouse_forward` | Forward button (side) |

## Hotkey String Format

Keys are specified in lowercase, joined by `+`:

```yaml
activation_key: alt           # Either Alt key
activation_key: alt_right     # Specific Right Alt
activation_key: ctrl+space    # Ctrl + Space
activation_key: f13           # F13 key
```

## Recommended Hotkeys

Choose keys that:
- Won't conflict with other applications
- Are easy to reach
- Won't trigger accidentally

Good choices:
- `alt` or `alt_right` - Default
- `scroll_lock` - Rarely used
- `pause` - Rarely mapped
- `f13` - `f24` - Extended keys (if available)
- `mouse_back` / `mouse_forward` - Side mouse buttons

## Known Issue

The default `alt` binding currently captures **both** Alt keys, which may temporarily affect normal Alt-key usage while recording is active. This is planned to be improved.
