# Vociferous - AI Agent Instructions

## Project Overview
Vociferous is a modern Python 3.12+ speech-to-text dictation application for Linux using OpenAI's Whisper via faster-whisper. It's a headless PyQt5 app with system tray integration that records audio on hotkey press and injects transcribed text into any application.

## Architecture & Key Patterns

### Component Boundaries
- **[src/main.py](../src/main.py)**: Central orchestrator - coordinates KeyListener → ResultThread → InputSimulator via PyQt5 signals
- **[src/key_listener.py](../src/key_listener.py)**: Pluggable input backends (evdev for Wayland, pynput for X11) using Protocol pattern
- **[src/transcription.py](../src/transcription.py)**: Whisper model wrapper with VAD filtering
- **[src/input_simulation.py](../src/input_simulation.py)**: Text injection with multiple backends (pynput/ydotool/dotool/clipboard)
- **[src/result_thread.py](../src/result_thread.py)**: QThread handling audio recording + transcription off UI thread
- **[src/utils.py](../src/utils.py)**: Thread-safe singleton ConfigManager using double-checked locking

### Critical Threading Model
- **Signal/Slot**: All cross-thread communication uses PyQt5 signals (thread-safe by design)
- **Connection tracking**: Track signal connections in `_thread_connections` list for proper cleanup to prevent memory leaks and crashes
- **QThread pattern**: Audio/transcription runs in ResultThread, emits signals back to main thread for UI/input simulation

### Configuration System
- **Schema-driven**: [src/config_schema.yaml](../src/config_schema.yaml) defines structure, types, defaults, and documentation
- **Hot reloading**: ConfigManager supports runtime config updates
- **Access pattern**: `ConfigManager.get_config_value('section', 'key')` - always initialize first with `ConfigManager.initialize()`

## Python 3.12+ Features Used
- `match/case` statements for event handling and pattern matching
- Union type hints: `Path | str | None` instead of `Optional`
- `@dataclass(slots=True)` for memory-efficient data classes
- `@runtime_checkable Protocol` for structural subtyping
- Modern generic type hints: `list[tuple]`, `dict[str, Any]` without `__future__` imports

## Platform Compatibility

### Wayland vs X11
- **Input monitoring**: evdev (Wayland + X11, requires `input` group) OR pynput (X11 only)
- **Text injection**: ydotool/dotool (Wayland, needs uinput access) OR pynput (X11) OR clipboard fallback

### GPU Path Management
- **Critical**: LD_LIBRARY_PATH must be set BEFORE CUDA imports - see [run.py](../scripts/run.py) re-exec pattern
- Use `./vociferous.sh` wrapper for GPU, or set `LD_LIBRARY_PATH` to venv's nvidia libs manually
- Config: `model_options.device: cuda` + `compute_type: float16` for GPU, `cpu` + `float32` for CPU

## Development Workflows

### Running & Testing
```bash
# Development run (auto-detects GPU)
python run.py

# GPU-optimized run (sets LD_LIBRARY_PATH)
./vociferous.sh

# Run tests
pytest                          # All tests
pytest tests/test_config.py    # Specific module
pytest -v                      # Verbose
```

### Dependency Management
```bash
# Check for missing dependencies
python check_deps.py

# Install all dependencies
pip install -r requirements.txt

# Format & lint
ruff check .
ruff format .
```

### Testing Patterns
- **Fixtures**: Use `config_manager` and `key_listener` fixtures from [tests/conftest.py](../tests/conftest.py)
- **Import testing**: Allowed F401 (unused import) in test files for import-availability checks
- **Cleanup**: Stop listeners/threads in teardown to prevent pytest hangs

## Code Conventions

### Import Organization
- Standard library → third-party → local modules
- Use `TYPE_CHECKING` for heavy imports (defer to runtime): `if TYPE_CHECKING: from faster_whisper import WhisperModel`

### Error Handling
- Use `contextlib.suppress()` for expected exceptions instead of try/except/pass
- Process cleanup: terminate() → wait(timeout) → kill() → wait() to prevent zombies

### Logging
- Each module gets logger: `logger = logging.getLogger(__name__)`
- Log levels: DEBUG for verbose info, INFO for user-visible events, WARNING for recoverable issues

### Resource Management
- Use `deleteLater()` for Qt objects (schedules deletion on event loop)
- Close subprocess stdin before termination for graceful shutdown
- Disconnect signals explicitly to prevent memory leaks

## Common Tasks

### Adding New Hotkey Backend
1. Implement `InputBackend` Protocol in [src/key_listener.py](../src/key_listener.py)
2. Add to `_create_backend()` selection logic
3. Update `config_schema.yaml` `input_backend.options`

### Adding New Text Injection Method
1. Extend `input_method` match/case in [src/input_simulation.py](../src/input_simulation.py)
2. Implement backend-specific logic (see dotool pattern for subprocess handling)
3. Add to `config_schema.yaml` `output_options.input_method.options`

### Modifying Transcription Pipeline
- VAD filtering happens in [src/transcription.py](../src/transcription.py) `transcribe()` function
- Audio format must be float32 normalized for Whisper (convert from int16 numpy array)
- Post-processing (spacing, capitalization) in `post_process()` function
