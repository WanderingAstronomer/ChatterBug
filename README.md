# Vociferous

Vociferous is a modern **Python 3.12+** speech‑to‑text dictation application for Linux built on **OpenAI Whisper** via **faster‑whisper (CTranslate2)**.

It is designed for fast, local dictation with a clipboard‑first workflow and minimal friction.

---

## Main Window

The application is split into **two static interaction panes**:

- **Left pane**: Transcription history
- **Right pane**: Current transcription

There is **no dedicated Start/Stop button** in the current version. Recording is controlled entirely via a hotkey. This will be added in a future update, along with additional UI refinements. A roadmap will be published soon outlining planned features and improvements!

[![Vociferous Main Window](docs/images/main_window.png)](docs/images/main_window.png)

---

## Features

- Fast transcription using faster‑whisper (CTranslate2 backend)
- **GPU acceleration (NVIDIA CUDA)** with **CPU‑only fallback supported**
- PyQt5 GUI (**planned upgrade to PyQt6**)
- Hotkey‑based, press‑to‑toggle recording
- Voice Activity Detection (VAD)
- Clipboard‑first workflow (no input injection)
- Persistent transcription history (JSONL)
- Editable history entries
- Export history to TXT / CSV / Markdown
- Dark‑themed Linux‑native UI with system tray integration
- Live‑reloadable settings (no restart required)

---

## Installation

### Quick Install (Recommended)

```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

### Manual Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### System Dependencies

**Wayland**

```bash
sudo apt install wl-clipboard
sudo usermod -a -G input $USER
```

(Log out and back in after group change)

**X11**

```bash
sudo apt install python3-xlib
```

---

## Dependencies Overview

- `faster-whisper`
- `ctranslate2`
- `PyQt5` *(PyQt6 planned)*
- `sounddevice`
- `webrtcvad`
- `pynput` / `evdev`
- `PyYAML`

See `requirements.txt` for full details.

---

## Running

### GPU (Recommended)

```bash
chmod +x vociferous.sh
./vociferous.sh
```

### CPU

```bash
python scripts/run.py
```

CPU transcription is supported but significantly slower. NVIDIA GPUs are recommended for practical real‑time use.

---

## Usage Workflow

1. Press the activation hotkey (default: **Alt**)
2. Speak
3. Press the hotkey again or allow VAD to stop recording
4. Transcription is copied to the clipboard

### Notes

- Only **press‑to‑toggle hotkey mode** is supported
- Default Alt binding currently registers **both Alt keys**
- Status text displays **Recording** or **Transcribing** only
- No visual dot indicators are used
- A **trailing space is always appended** to transcriptions (non‑configurable)

---

## Clipboard Behavior

Vociferous **always outputs to the clipboard**.

- Email composition: paste into client
- Document writing: paste into editor
- Terminal usage: paste manually (Ctrl+Shift+V)

Vociferous **does not inject input** and does not simulate typing.

---

## Configuration

Defined in `src/config_schema.yaml`.

Key options include:

- `model_options.device`: `auto`, `cuda`, `cpu`
- `model_options.compute_type`: `float16`, `float32`, `int8`
- `model_options.language`
- `recording_options.activation_key`

All settings apply immediately.

---

## History

Stored at:

```
~/.config/vociferous/history.jsonl
```

Supports:

- Editing
- Deletion with persistence
- Auto‑reload
- Export (TXT / CSV / Markdown)

---

## Performance Characteristics

- GPU VRAM usage is consistent with model size and verified
- CPU fallback is supported but slower
- Background resource usage aligns with expectations for Whisper inference

---

## Known Issues / Planned Updates (v1.1.1)

- Alt key binding temporarily blocks normal Alt usage
- Start/Stop UI button planned
- PyQt6 migration planned
- Status text may be expanded in future versions

---

## Further Reading

Additional documentation and technical deep dives are available in the `docs/` directory.

---

**Version:** 1.1.1 (documentation patch)