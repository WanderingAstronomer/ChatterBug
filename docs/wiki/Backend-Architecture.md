# Backend Architecture

Vociferous follows a modular architecture with clear separation of concerns.

## Module Overview

```
┌─────────────────────────────────────────────────────────────┐
│                       main.py                               │
│                  (VociferousApp Orchestrator)               │
├──────────┬──────────┬──────────┬──────────┬────────────────┤
│  KeyListener  │  ResultThread  │  TranscriptionModel  │  UI  │
│  (Hotkeys)    │  (Audio+Trans) │  (Whisper)           │      │
└──────────────┴────────────────┴──────────────────────┴──────┘
```

## Core Modules

### main.py - Application Orchestrator

Central coordinator that wires all components together:
- Creates and manages `KeyListener`, `ResultThread`, UI components
- Connects signals between components
- Handles application lifecycle (startup, shutdown, cleanup)
- Manages system tray integration

### key_listener.py - Input Handling

Pluggable input backend system using Protocol pattern:
- `KeyListener`: Main class that manages backends and detects hotkey chords
- `EvdevBackend`: Linux evdev for Wayland (requires `input` group)
- `PynputBackend`: Cross-platform fallback for X11
- `KeyChord`: Tracks modifier + key combinations

### result_thread.py - Recording & Transcription

QThread that runs audio capture and transcription off the UI thread:
- Captures audio via sounddevice
- Applies Voice Activity Detection (WebRTC VAD)
- Sends audio to Whisper model
- Emits signals back to main thread with results

### transcription.py - Whisper Integration

Wrapper around faster-whisper:
- `create_local_model()`: Loads model with fallback (CUDA → CPU)
- `transcribe()`: Converts audio to text with VAD filtering
- `post_process_transcription()`: Applies user preferences (spacing)

### history_manager.py - Persistence

JSONL-based storage for transcription history:
- Append-only writes (thread-safe)
- Automatic rotation when exceeding max entries
- Export to txt, csv, or markdown

### utils.py - Configuration

Thread-safe singleton ConfigManager:
- Schema-driven configuration from YAML
- Hot-reload support
- PyQt signals for live updates

## Design Patterns

### Protocol Pattern (Structural Typing)

```python
@runtime_checkable
class InputBackend(Protocol):
    @classmethod
    def is_available(cls) -> bool: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
```

Backends implement this interface without inheritance, enabling duck typing with type safety.

### Singleton with Double-Checked Locking

```python
@classmethod
def initialize(cls) -> None:
    if cls._instance is None:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
```

Thread-safe lazy initialization for ConfigManager.

### Signal/Slot (Observer Pattern)

All cross-thread communication uses PyQt signals:
```python
self.result_thread.resultSignal.connect(self.on_transcription_complete)
```

This ensures thread-safe updates without explicit locking.

## Data Flow

```mermaid
flowchart LR
    KB[Keyboard] --> KL[KeyListener]
    KL -->|toggle| RT[ResultThread]
    MIC[Microphone] --> RT
    RT --> WH[faster-whisper]
    WH --> OUT[Text Result]
    OUT --> CLIP[Clipboard]
    OUT --> HIST[History]
    OUT --> UI[UI display]
```

### Step by Step

1. **Keyboard** → KeyListener detects activation key
2. **KeyListener** → Triggers recording start/stop in VociferousApp
3. **Microphone** → Audio captured by ResultThread
4. **ResultThread** → Sends audio to faster-whisper
5. **faster-whisper** → Returns transcribed text
6. **Text Result** → Copied to clipboard, added to history, displayed in UI

