# Vociferous Changelog

---

# v1.1.1 Beta - Documentation Refresh

**Date:** December 2025  
**Status:** Beta

---

## Summary

Documentation-focused update: clarified current behavior (press-to-toggle only), aligned wiki with ARCHITECTURE.md as source of truth, and fixed mermaid diagrams.

## Changes

- **Wiki refresh**: Replaced Recording page to reflect single supported mode (press-to-toggle); updated Text Output, Config Options, Keycodes Reference, Hotkey System, Backend Architecture, Threading Model, and Home navigation links.
- **Architecture link-out**: Added guidance to treat ARCHITECTURE.md as canonical; wiki pages now act as concise summaries.
- **Mermaid fixes**: Corrected High-Level Architecture diagram label (main.py/VociferousApp) and refreshed data-flow/threading diagrams in wiki to render properly.
- **Config clarification**: Documented `recording_mode` as fixed to `press_to_toggle`; noted default Alt hotkey captures both Alt keys (known limitation).

## Notes

- No functional code changes; this release is purely documentation and clarity improvements.

---

# v1.1.0 Beta - Custom Title Bar & History Enhancements

**Date:** December 2025  
**Status:** Beta

---

## Summary

Feature release introducing a custom frameless title bar with unified menu/controls, enhanced history management with file watching and persistent deletion, a Cancel button for aborting recordings, and bundled application icons.

---

## Changes

### Custom Title Bar

- **Added**: Custom frameless `TitleBar` widget with menu bar, centered title, and window controls (minimize, maximize, close) in a single row
- **Added**: Wayland-native drag support via `startSystemMove()` for proper window dragging on Wayland compositors
- **Added**: X11 fallback drag handling for traditional window movement
- **Added**: Double-click title bar to maximize/restore window
- **Added**: Styled window controls with hover effects (blue highlight for min/max, red for close)
- **Added**: Border styling for frameless window (`1px solid #3c3c3c`, `border-radius: 6px`)
- **Added**: `QT_WAYLAND_DISABLE_WINDOWDECORATION=1` environment variable for client-side decorations on Wayland

### History Widget Enhancements

- **Added**: `QFileSystemWatcher` with 200ms debounce to auto-reload history when file changes externally
- **Added**: `delete_entry()` method in HistoryManager for persistent deletion from JSONL file
- **Added**: Delete key shortcut with `Qt.ApplicationShortcut` context for reliable deletion even when focus shifts
- **Added**: `historyCountChanged` signal to track entry count for UI state updates
- **Added**: `entry_count()` helper method for counting non-header entries
- **Added**: Automatic fallback selection after deletion (prefers previous entry, then next)
- **Added**: Automatic day header removal when all entries under a day are deleted
- **Fixed**: History widget now accepts `HistoryManager` in constructor for proper initialization order

### Main Window Improvements

- **Added**: Cancel button in current transcription panel to abort recording without transcribing
- **Added**: `cancelRecordingRequested` signal connected to `_cancel_recording()` in main app
- **Added**: History menu "Open History File" action to open JSONL file in system default handler
- **Added**: `_update_history_actions()` method to enable/disable Export controls based on history count
- **Fixed**: Export button, menu action, and Ctrl+E shortcut now disabled when history is empty
- **Fixed**: Guard added to `_export_history()` to show status message when nothing to export
- **Changed**: `display_transcription()` now accepts `HistoryEntry` for consistent timestamps
- **Changed**: `load_entry_for_edit()` no longer steals focus (cursor position preserved)
- **Changed**: Placeholder text updated to "Your transcription will appear here..."

### Application Icons

- **Added**: Bundled icon assets in `icons/` directory:
  - `512x512.png` - High-resolution application icon
  - `192x192.png` - Medium-resolution icon
  - `favicon.ico` - Windows/multi-resolution icon
- **Changed**: Tray icon now loads from bundled assets with fallback to theme icon

### Launcher Script

- **Added**: `RUST_LOG=error` environment variable to suppress verbose wgpu/Vulkan warnings

### Bug Fixes

- **Fixed**: Unused `datetime` import removed from main_window.py (ruff compliance)
- **Fixed**: Result thread now properly sets `self.result_thread = None` on completion to prevent stale references
- **Fixed**: History widget initialization order ensures buttons exist before loading history (prevents AttributeError)

---

# v1.0.1 Beta - UI Polish & Editing Support

**Date:** December 2025  
**Status:** Beta

---

## Summary

Refinement release focusing on UI polish and introducing editable transcriptions. History entries can now be edited directly in the main window, and the layout has been simplified to a fixed 50/50 split.

---

## Changes

### History Widget Behavior

- **Single-click** on history entry loads it into editor for modification
- **Double-click** copies entry to clipboard
- **Removed**: Re-inject functionality (replaced by copy/paste workflow)
- **Removed**: Tooltips on history items (cleaner appearance)
- **Fixed**: Timestamp format now consistently shows "10:03 a.m." style

### Main Window Layout

- **Replaced**: QSplitter with fixed 50/50 horizontal layout (no resize handle)
- **Added**: Editable transcription panel with Save button
- **Added**: `update_entry()` in HistoryManager for saving edits

### Settings Dialog

- **Added**: Device setting (auto/cuda/cpu) exposed in UI
- **Added**: Dynamic compute_type filtering based on device selection
- **Fixed**: float16 automatically falls back to float32 on CPU

### Project Structure

- **Moved**: Scripts reorganized into `scripts/` folder
  - `run.py` → `scripts/run.py`
  - `install.sh` → `scripts/install.sh`
  - `check_deps.py` → `scripts/check_deps.py`
- **Updated**: `vociferous.sh` references `scripts/run.py`

### Documentation

- **Updated**: README.md to match current codebase
- **Updated**: ARCHITECTURE.md with accurate module descriptions
- **Fixed**: Install and run paths reference `scripts/` folder

---

# v1.0.0 Beta - Polished UI & History System

**Date:** December 2025  
**Status:** Beta

---

## Summary

Major milestone release introducing a full-featured main window with transcription history, graphical settings dialog, and a simplified clipboard-only workflow. The floating status window has been replaced with an integrated UI that provides history management, export capabilities, and live configuration updates.

---

## Breaking Changes from Alpha

### UI Architecture

- **Removed**: `StatusWindow` and `BaseWindow` classes (floating frameless windows)
- **Removed**: Automatic text injection (unreliable on Wayland)
- **Replaced with**: `MainWindow` with integrated history and transcription panels
- **Replaced with**: Clipboard-only output (always copies, user pastes with Ctrl+V)

### Configuration

- **Removed**: `output_options.input_method` auto-inject options (pynput/ydotool/dotool direct typing)
- **Removed**: `output_options.auto_copy_clipboard`, `auto_inject_text`, `auto_submit_return` cascading options
- **Simplified**: All transcriptions now copy to clipboard automatically

---

## What's New

### Main Window

A full application window replaces the minimal floating status indicator:

```
┌──────────────────────────────────────────────────────┐
│ File  History  Settings  Help                        │
├──────────────────────────────────────────────────────┤
│ ┌──History────────┐ │ ┌──Current Transcription────┐ │
│ │ ▼ December 14th │ │ │                           │ │
│ │   10:03 a.m. ...│ │ │  Transcribed text here    │ │
│ │   9:45 a.m. ... │ │ │                           │ │
│ │ ▼ December 13th │ │ │       ● Recording         │ │
│ │   ...           │ │ │                           │ │
│ └─────────────────┘ │ └───────────────────────────┘ │
│ [Export] [Clear All]│ [Copy]            [Clear]     │
└──────────────────────────────────────────────────────┘
```

**Features:**
- **Dark theme** with blue accents (#1e1e1e background, #5a9fd4 highlights)
- **Responsive layout**: Side-by-side at ≥700px, stacked below
- **Resizable splitter** with visual grab handle
- **Window geometry persistence** (remembers size/position)
- **System tray integration** with minimize-to-tray behavior
- **One-time tray notification** when first minimized

### History System

Persistent transcription history with JSONL storage:

- **Storage**: `~/.config/vociferous/history.jsonl` (append-only, thread-safe)
- **Day grouping**: Entries organized under collapsible day headers (▼/▶)
- **Friendly timestamps**: "December 14th" headers, "10:03 a.m." entry times
- **Visual nesting**: Indented entries under day headers with styled headers
- **Auto-rotation**: Configurable max entries (default 1000)

**History Widget:**
- Click day headers to collapse/expand
- Double-click entries to copy
- Right-click context menu: Copy, Re-inject, Delete
- Keyboard navigation (Enter to copy, Delete to remove)

**Export:**
- **Text** (`.txt`): Timestamped entries
- **CSV** (`.csv`): Spreadsheet-compatible with headers
- **Markdown** (`.md`): `## Date` and `### Time` heading hierarchy

### Settings Dialog

Schema-driven graphical preferences dialog:

- Accessible via **Settings → Preferences** or **tray right-click → Settings**
- Dynamically built from `config_schema.yaml`
- Each schema section becomes a tab (Model Options, Recording Options, Output Options)
- Widget types inferred from schema (`bool` → checkbox, `str` with options → dropdown)
- Tooltips display setting descriptions
- Changes apply immediately (Apply or OK)

### Hotkey Rebinding

Live hotkey capture in Settings:

1. Click **Change...** next to Activation Key
2. Press desired key combination
3. Validation blocks reserved shortcuts (Alt+F4, Ctrl+C, etc.)
4. New hotkey active immediately—no restart required

**Implementation:**
- `HotkeyWidget` with capture mode
- `KeyListener.enable_capture_mode()` diverts events to callback
- `keycode_mapping.py` utilities for display/config string conversion

### Live Configuration Updates

Settings changes take effect without restart:

| Setting | Effect |
|---------|--------|
| `activation_key` | KeyListener reloads immediately |
| `input_backend` | Backend switches (evdev ↔ pynput) |
| `compute_type`, `device` | Whisper model reloads |

**Signal architecture:**
- `ConfigManager.configChanged(section, key, value)` signal
- Main app connects handlers for each setting type

### Recording Indicator

Compact pulsing indicator in the current transcription panel:

- **Recording**: Red "● Recording" with opacity pulse animation (0.3 ↔ 1.0)
- **Transcribing**: Orange "● Transcribing" (solid)
- **Idle**: Hidden

### UI Polish

- **Floating pill headers** with rounded borders for panel labels
- **Custom Clear History dialog** with Yes/No button layout (Yes left, No right)
- **Styled scrollbars** matching dark theme
- **Menu bar**: File, History, Settings, Help (View menu removed)
- **Keyboard shortcuts**: Ctrl+C (copy), Ctrl+E (export), Ctrl+H (focus history), Ctrl+L (clear)

---

## Files Added

```
src/
├── history_manager.py      # JSONL storage with rotation and export
└── ui/
    ├── history_widget.py   # Collapsible day-grouped history display
    ├── hotkey_widget.py    # Live hotkey capture widget
    ├── keycode_mapping.py  # KeyCode ↔ string utilities
    ├── main_window.py      # Primary application window (820 lines)
    ├── output_options_widget.py  # (Cascading checkboxes - deprecated)
    └── settings_dialog.py  # Schema-driven preferences dialog

tests/
└── test_settings.py        # Settings, hotkey, and config signal tests
```

## Files Removed

```
src/ui/
├── base_window.py          # Frameless window base class
└── status_window.py        # Floating status indicator

assets/
├── microphone.png          # Recording icon (now using text indicator)
├── pencil.png              # Transcribing icon
└── ww-logo.png             # Application logo (now using system theme icon)
```

## Files Modified

- **main.py**: Replaced StatusWindow with MainWindow, added HistoryManager, removed InputSimulator direct typing, clipboard-only workflow
- **input_simulation.py**: Added `reinitialize()` for live updates, auto-detection of input method
- **key_listener.py**: Added capture mode for hotkey rebinding
- **utils.py**: ConfigManager now extends QObject, emits `configChanged` and `configReloaded` signals
- **config_schema.yaml**: Simplified schema, marked internal options with `_internal: true`
- **run.py**: Suppresses Qt Wayland warnings

---

## Known Issues

- **Button padding**: Minor spacing issue between Export/Clear buttons and history pane bottom edge
- **Recording indicator font**: Slight font size inconsistency on the active recording indicator

---

## Platform Notes

### Wayland

The clipboard-only workflow was adopted because automatic text injection via ydotool/dotool is unreliable when window focus shifts during transcription. Copying to clipboard and letting the user paste with Ctrl+V is more robust.

### Model Caching

Model loading now tries `local_files_only=True` first to avoid unnecessary HTTP requests to HuggingFace, only downloading if not cached.

---

---

# v0.9.0 Alpha - Complete Architectural Rewrite

**Date:** December 2025  
**Status:** Pre-release

---

## Summary

Complete ground-up rewrite of Vociferous. The previous architecture (v0.7-v0.8) featured a daemon-based server, Kivy GUI, CLI with multiple commands, and support for multiple transcription engines. This release replaces it entirely with a minimal, focused design: a single-purpose hotkey-triggered dictation tool.

---

## Breaking Changes

**This version is not compatible with any previous version.** The entire codebase has been replaced.

### Architecture Removed

- **Daemon Server** - FastAPI-based background process with REST API
- **Kivy GUI** - Multi-screen application (home, settings, history)
- **CLI Commands** - `transcribe`, `daemon`, `bench`, `check`, `deps`
- **Multiple Engines** - Canary-Qwen, model registry, hardware detection
- **Configuration Presets** - Complex schema with validation and profiles
- **Progress System** - Rich progress tracking with callbacks

### Architecture Replaced With

- **Direct Execution** - Single `run.py` entry point, no daemon
- **Minimal UI** - PyQt5 status window + system tray icon
- **Hotkey Activation** - Press key to record, press again to transcribe
- **Single Engine** - faster-whisper only (distil-large-v3 default)
- **Simple Config** - YAML schema with sensible defaults

---

## New Design Philosophy

| Aspect | v0.8.x (Previous) | v0.9.0 (Current) |
|--------|-------------------|------------------|
| Source files | 60+ files in `vociferous/` | 8 files in `src/` |
| Test files | 50+ test files, 376 tests | 5 test files |
| UI framework | Kivy (Material Design) | PyQt5 (minimal) |
| Transcription | Daemon with REST API | Direct in-process |
| Engines | Multiple (registry-based) | faster-whisper only |
| Configuration | Pydantic schemas, presets | Simple YAML |
| Input detection | pynput only | evdev (Wayland) + pynput fallback |
| Text injection | pynput only | dotool/ydotool/pynput/clipboard |

---

## Rationale

The v0.7-v0.8 architecture was designed for a full-featured transcription application with batch processing, multiple engines, and GUI-driven workflows. The rewrite focuses on a single use case: **real-time dictation**.

**Why rewrite?**
1. **Simplicity** - Daemon architecture added complexity without benefit for dictation
2. **Wayland support** - Previous pynput-only approach broken on modern Linux
3. **Startup speed** - No daemon means instant activation
4. **Maintainability** - 8 files vs 60+ files

---

## What's New

### Wayland-First Input Handling

- **evdev backend** - Works on Wayland (requires `input` group membership)
- **pynput fallback** - Automatic fallback for X11 users
- **Multi-backend text injection** - dotool, ydotool, pynput, clipboard

### GPU Bootstrap Pattern

- Process re-executes with correct `LD_LIBRARY_PATH` for CUDA libraries
- Sentinel variable prevents infinite re-exec loop
- Works transparently - users just run `python run.py`

### Minimal UI

- Frameless floating status window
- Shows recording/transcribing state
- System tray for background operation
- No configuration dialogs (edit YAML directly)

### Simplified Installation

- `install.sh` creates venv, installs deps, verifies imports
- `check_deps.py` validates all required packages
- Single `requirements.txt` with pinned versions

---

## Files (New Structure)

```
Vociferous/
├── run.py                  # Entry point with GPU bootstrap
├── install.sh              # Installation script
├── check_deps.py           # Dependency validator
├── requirements.txt        # Pinned dependencies
├── src/
│   ├── main.py             # VociferousApp orchestrator
│   ├── utils.py            # ConfigManager singleton
│   ├── key_listener.py     # Hotkey detection (evdev/pynput)
│   ├── result_thread.py    # Audio recording & transcription
│   ├── transcription.py    # faster-whisper integration
│   ├── input_simulation.py # Text injection backends
│   ├── config_schema.yaml  # Configuration schema
│   └── ui/
│       ├── base_window.py  # Frameless window base
│       └── status_window.py # Status indicator
├── tests/                  # Minimal test suite
└── docs/
    └── ARCHITECTURE.md     # Comprehensive architecture guide
```

---

## Files Removed (136 files)

All files from the previous architecture deleted:
- `vociferous/` package (app, audio, cli, config, domain, engines, gui, server, setup)
- `tests/` subdirectories (app, audio, cli, config, domain, engines, gui, integration, refinement, server)
- Documentation (Design.md, daemon.md, Redesign.md, GUI recommendations)

---

## Migration

**There is no migration path.** v0.9.0 is a new application sharing only the name. If you relied on the daemon API, CLI commands, or Kivy GUI, those features no longer exist.

---

## Credits

The v0.1-v0.8 architecture served as exploration of what a full-featured transcription tool could look like. This rewrite takes the lessons learned and applies them to a simpler, more focused tool.

012




sdfasdf
s
df
sdf
f
sd

d
df
dfdfd