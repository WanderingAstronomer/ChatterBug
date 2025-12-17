# Vociferous

A modern Python 3.12+ speech-to-text dictation application for Linux using OpenAI's Whisper via faster-whisper.

## Quick Start

1. **Install**: `./scripts/install.sh`
2. **Run**: `./vociferous.sh` (GPU) or `python scripts/run.py` (CPU)
3. **Record**: Press Alt (default hotkey) to start
4. **Speak**: VAD captures your speech and filters silence
5. **Stop**: Press Alt again to transcribe
6. **Paste**: Text auto-copies to clipboard → Ctrl+V

## Features

- **Fast transcription** with faster-whisper (CTranslate2 backend)
- **GPU acceleration** with CUDA/cuDNN (CPU fallback supported)
- **Custom frameless window** with dark theme, Wayland-native drag support
- **System tray** integration for background operation
- **Voice Activity Detection** filters silence during recording
- **Transcription history** with JSONL storage, day grouping, and export
- **Editable transcriptions** with persistence
- **Live settings** that take effect immediately

## Documentation

[Architecture — Deep-Dive Systems Guide](ARCHITECTURE) - The master document detailing Vociferous's architecture, design patterns, and components. This wiki should be sufficient to understand and contribute to the codebase without looking here. It's pretty much just a legacy doc.

### Getting Started
- [Installation Guide](Installation-Guide) - Complete setup instructions
- [Recording](Recording) - How recording works
- [Troubleshooting](Troubleshooting) - Common issues and solutions

### Architecture
- [Backend Architecture](Backend-Architecture) - Module structure and design patterns
- [Threading Model](Threading-Model) - Qt signals/slots and worker threads
- [Configuration Schema](Configuration-Schema) - YAML-based settings system

### Components
- [Audio Recording](Audio-Recording) - Microphone capture and VAD filtering
- [Hotkey System](Hotkey-System) - evdev/pynput backends and key detection
- [Text Output](Text-Output) - Clipboard workflow
- [History Storage](History-Storage) - JSONL persistence and rotation

### Reference
- [Keycodes Reference](Keycodes-Reference) - Supported keys for hotkey binding
- [Config Options](Config-Options) - All configuration values explained

## Requirements

- **Python**: 3.12+
- **OS**: Linux (Wayland or X11)
- **Audio**: Working microphone
- **GPU** (optional): CUDA-compatible NVIDIA GPU for fast transcription

## Project Structure

```
src/
├── main.py           # Application orchestrator
├── key_listener.py   # Input backend (evdev/pynput)
├── transcription.py  # Whisper model wrapper
├── result_thread.py  # Audio recording thread
├── history_manager.py # JSONL storage
├── input_simulation.py # Text injection
├── utils.py          # ConfigManager singleton
└── ui/               # PyQt5 widgets
    ├── main_window.py
    ├── settings_dialog.py
    └── history_widget.py
```

## License

MIT License - see [LICENSE](../LICENSE)
