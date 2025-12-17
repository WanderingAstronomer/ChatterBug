# Configuration Schema

Vociferous uses a YAML-based configuration system with schema validation.

## Files

- **Schema**: `src/config_schema.yaml` - Defines structure, types, defaults, and metadata
- **User Config**: `src/config.yaml` - User overrides (merged with defaults)

## Schema Structure

Each setting follows this pattern:

```yaml
section_name:
  setting_name:
    value: default_value
    type: str|int|bool
    description: "Human-readable description"
    options:              # Optional: valid values for dropdowns
      - option1
      - option2
    _internal: true       # Optional: hide from Settings dialog
```

## Configuration Sections

### model_options

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `model` | str | `distil-large-v3` | Whisper model name |
| `device` | str | `auto` | Inference device: auto, cuda, cpu |
| `compute_type` | str | `float16` | Precision: float16, float32, int8 |
| `language` | str | `en` | ISO-639-1 language code |

### recording_options

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `activation_key` | str | `alt_right` | Key to trigger recording |
| `input_backend` | str | `auto` | Input backend: auto, evdev, pynput |
| `recording_mode` | str | `press_to_toggle` | Mode: press_to_toggle, hold_to_record |
| `sample_rate` | int | `16000` | Audio sample rate (Hz) |
| `silence_duration` | int | `900` | VAD silence threshold (ms) |
| `min_duration` | int | `100` | Minimum recording length (ms) |

### output_options

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `max_history_entries` | int | `1000` | Maximum history entries to keep |
| `print_to_terminal` | bool | `true` | Print status to terminal |
| `add_trailing_space` | bool | `true` | Add space after transcription |

## Accessing Configuration

```python
from utils import ConfigManager

# Initialize once at startup
ConfigManager.initialize()

# Get a value
device = ConfigManager.get_config_value('model_options', 'device')

# Get entire section
model_opts = ConfigManager.get_config_section('model_options')

# Set a value (triggers configChanged signal)
ConfigManager.set_config_value('cuda', 'model_options', 'device')

# Save to file
ConfigManager.save_config()
```

## Live Updates

ConfigManager emits signals when values change:

```python
ConfigManager.instance().configChanged.connect(self.on_config_changed)

def on_config_changed(self, section: str, key: str, value):
    if section == 'model_options' and key == 'device':
        self.reload_model()
```

## Internal Settings

Settings with `_internal: true` are not shown in the Settings dialog:
- `input_backend` - auto-detected based on display server
- `sample_rate` - fixed at 16kHz for Whisper
- `min_duration` - rarely needs adjustment

These can still be edited in `config.yaml` directly.
