# Config Options

Complete reference for all configuration options in Vociferous.

## Model Options

Settings for the Whisper transcription model.

### model

**Type:** string  
**Default:** `distil-large-v3`  
**Internal:** Yes (not shown in Settings dialog)

The Whisper model to use for transcription. Options:
- `distil-large-v3` - Faster, slightly less accurate (recommended)
- `large-v3` - Full model, highest accuracy
- `medium` - Balanced speed/accuracy
- `small` - Fast, lower accuracy
- `base` - Fastest, lowest accuracy
- `tiny` - Minimal resources

### device

**Type:** string  
**Default:** `auto`  
**Options:** `auto`, `cuda`, `cpu`

Where to run the model:
- `auto` - Detect GPU, fall back to CPU
- `cuda` - Force GPU (requires NVIDIA + CUDA)
- `cpu` - Force CPU only

### compute_type

**Type:** string  
**Default:** `float16`  
**Options:** `float16`, `float32`, `int8`

Numerical precision:
- `float16` - GPU only, fastest, good accuracy
- `float32` - Any device, slower, full precision
- `int8` - CPU only, quantized, smallest memory

### language

**Type:** string  
**Default:** `en`

ISO-639-1 language code. Common values:
- `en` - English
- `es` - Spanish
- `de` - German
- `fr` - French
- `zh` - Chinese
- `ja` - Japanese

Leave empty for auto-detection (slower).

---

## Recording Options

Settings for audio capture and hotkey behavior.

### activation_key

**Type:** string  
**Default:** `alt_right`

Key combination to trigger recording. See [Keycodes Reference](Keycodes-Reference).

Examples:
- `alt_right` - Right Alt key
- `ctrl+space` - Ctrl + Space
- `f13` - F13 key

### input_backend

**Type:** string  
**Default:** `auto`  
**Options:** `auto`, `evdev`, `pynput`  
**Internal:** Yes

Which input backend to use:
- `auto` - Detect based on display server
- `evdev` - Linux evdev (Wayland, requires input group)
- `pynput` - Cross-platform (X11)

### recording_mode

**Type:** string  
**Default:** `press_to_toggle`  
**Internal:** Yes (not configurable)

Recording mode is fixed at `press_to_toggle`:
- Press activation key to start recording
- Press again to stop and transcribe

Other modes (hold_to_record, voice_activity_detection) are not currently supported.

### sample_rate

**Type:** integer  
**Default:** `16000`  
**Internal:** Yes

Audio sample rate in Hz. 16000 is Whisper's native rate.

### silence_duration

**Type:** integer  
**Default:** `900`  
**Internal:** Yes

Milliseconds of silence before VAD stops recording. Lower = faster cutoff, higher = more patience for pauses.

### min_duration

**Type:** integer  
**Default:** `100`  
**Internal:** Yes

Minimum recording length in milliseconds. Recordings shorter than this are discarded.

---

## Output Options

Settings for text output and history.

### max_history_entries

**Type:** integer  
**Default:** `1000`

Maximum entries to keep in history file. Oldest entries are removed when limit is reached. Set to `0` for unlimited.

### print_to_terminal

**Type:** boolean  
**Default:** `true`  
**Internal:** Yes

Print status messages (Recording..., Transcribing...) to the terminal.

### add_trailing_space

**Type:** boolean  
**Default:** `true`  
**Internal:** Yes

Add a space after each transcription for easier continuation.

---

## Internal State

Hidden settings managed by the application.

### _internal.auto_submit_warned

**Type:** boolean  
**Default:** `false`

Tracks whether user has seen certain warnings. Do not modify.

---

## Configuration File

User settings are stored in `src/config.yaml`:

```yaml
model_options:
  device: cuda
  compute_type: float16
  language: en

recording_options:
  activation_key: alt_right

output_options:
  max_history_entries: 1000
```

Only override the settings you want to change. Missing values use schema defaults.
