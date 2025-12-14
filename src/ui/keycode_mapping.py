"""
Utilities for translating KeyCode enums to display/config strings and ordering.
"""
from key_listener import KeyCode

MODIFIER_ORDER = {
    'ctrl': 0,
    'shift': 1,
    'alt': 2,
    'meta': 3,
}


def is_modifier(code: KeyCode) -> bool:
    return code in {
        KeyCode.CTRL_LEFT,
        KeyCode.CTRL_RIGHT,
        KeyCode.SHIFT_LEFT,
        KeyCode.SHIFT_RIGHT,
        KeyCode.ALT_LEFT,
        KeyCode.ALT_RIGHT,
        KeyCode.META_LEFT,
        KeyCode.META_RIGHT,
    }


def keycode_to_display_name(code: KeyCode) -> str:
    match code:
        case KeyCode.CTRL_LEFT | KeyCode.CTRL_RIGHT:
            return "Ctrl"
        case KeyCode.SHIFT_LEFT | KeyCode.SHIFT_RIGHT:
            return "Shift"
        case KeyCode.ALT_LEFT | KeyCode.ALT_RIGHT:
            return "Alt"
        case KeyCode.META_LEFT | KeyCode.META_RIGHT:
            return "Meta"
        case _:
            name = code.name.replace('_', ' ')
            return name.title()


def keycode_to_config_name(code: KeyCode) -> str:
    match code:
        case KeyCode.CTRL_LEFT | KeyCode.CTRL_RIGHT:
            return 'ctrl'
        case KeyCode.SHIFT_LEFT | KeyCode.SHIFT_RIGHT:
            return 'shift'
        case KeyCode.ALT_LEFT | KeyCode.ALT_RIGHT:
            return 'alt'
        case KeyCode.META_LEFT | KeyCode.META_RIGHT:
            return 'meta'
        case _:
            return code.name.lower()


def normalize_hotkey_string(hotkey: str) -> str:
    """Normalize hotkey string: modifiers first (Ctrl, Shift, Alt, Meta), then keys."""
    parts = [p.strip().lower() for p in hotkey.split('+') if p.strip()]
    modifiers = [p for p in parts if p in MODIFIER_ORDER]
    main_keys = [p for p in parts if p not in MODIFIER_ORDER]
    modifiers.sort(key=lambda k: MODIFIER_ORDER[k])
    main_keys.sort()
    return '+'.join(modifiers + main_keys)


def keycodes_to_strings(codes: set[KeyCode]) -> tuple[str, str]:
    """Return (display, config) strings from a set of KeyCodes."""
    sorted_codes = sorted(codes, key=lambda x: x.value)
    config_names = [keycode_to_config_name(c) for c in sorted_codes]
    display_names = [keycode_to_display_name(c) for c in sorted_codes]
    config = normalize_hotkey_string('+'.join(config_names))
    display = ' + '.join(display_names)
    return display, config
