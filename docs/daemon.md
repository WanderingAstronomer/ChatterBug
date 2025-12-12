# Warm Model Daemon

## Overview

The Vociferous daemon keeps the Canary-Qwen model loaded in GPU memory, eliminating the 16-second model loading overhead for subsequent transcriptions.

## When to Use

**Use the daemon when:**
- ✅ Using the GUI (daemon starts automatically)
- ✅ Transcribing multiple files in a session
- ✅ Iterating rapidly (record → transcribe → repeat)

**Don't use the daemon when:**
- ❌ Transcribing a single file (cold start is fine)
- ❌ Running on a low-memory system (daemon uses ~8GB GPU RAM)

## Quick Start

```bash
# Start daemon (loads model, stays in GPU memory)
vociferous daemon start

# Now transcriptions are instant (~2-5s instead of ~29s)
vociferous transcribe audio1.wav --use-daemon
vociferous transcribe audio2.wav --use-daemon

# Stop daemon when done
vociferous daemon stop
```

## Architecture

```
┌──────────────┐                    ┌──────────────────┐
│ CLI / GUI    │──HTTP requests──→  │ Daemon Server    │
│              │←──responses────────│ (FastAPI)        │
└──────────────┘                    │                  │
                                    │ Canary-Qwen      │
                                    │ (warm in GPU)    │
                                    └──────────────────┘
```

The daemon:
1. Loads Canary-Qwen model at startup (~16s)
2. Listens on `http://127.0.0.1:8765` (local only)
3. Processes transcription/refinement requests
4. Keeps model warm until stopped

## Usage

### Starting the Daemon

```bash
vociferous daemon start
```

This will:
- Load the model (~16 seconds)
- Start HTTP server on port 8765
- Run in background
- Create PID file at `~/.cache/vociferous/daemon.pid`
- Log to `~/.cache/vociferous/daemon.log`

For debugging, run in foreground:

```bash
vociferous daemon start --foreground
```

### Checking Status

```bash
vociferous daemon status
```

Output:
```
✓ Daemon is running
  PID: 12345
  Model: nvidia/canary-qwen-2.5b
  Uptime: 5.2 minutes
  Requests handled: 12
```

### Using the Daemon

**From CLI:**
```bash
vociferous transcribe audio.wav --use-daemon
```

**From GUI:**
Daemon usage is automatic when the GUI is open.

**Programmatically:**
```python
from vociferous.server.client import transcribe_via_daemon

segments = transcribe_via_daemon(audio_path)
if segments is None:
    # Daemon not available, use direct engine
    pass
```

### Stopping the Daemon

```bash
vociferous daemon stop
```

### Viewing Logs

```bash
# Show last 50 lines
vociferous daemon logs

# Show last 100 lines
vociferous daemon logs --lines 100

# Follow logs in real-time
vociferous daemon logs --follow
```

### Restarting

```bash
vociferous daemon restart
```

## API Reference

The daemon exposes an HTTP API (for internal use):

### `GET /health`

Check daemon health.

**Response:**
```json
{
  "status": "ready",
  "model_loaded": true,
  "model_name": "nvidia/canary-qwen-2.5b",
  "uptime_seconds": 123.4,
  "requests_handled": 42
}
```

### `POST /transcribe`

Transcribe audio file.

**Request:** `multipart/form-data` with `audio` file

**Response:**
```json
{
  "success": true,
  "segments": [
    {
      "start": 0.0,
      "end": 5.3,
      "text": "transcribed text",
      "speaker": null,
      "language": "en"
    }
  ],
  "inference_time_s": 2.1
}
```

### `POST /refine`

Refine transcript text.

**Request:**
```json
{
  "text": "raw transcript",
  "instructions": "optional custom instructions"
}
```

**Response:**
```json
{
  "success": true,
  "refined_text": "Refined transcript.",
  "inference_time_s": 0.8
}
```

### `POST /batch-transcribe`

Transcribe multiple audio files in batch.

**Request:**
```json
{
  "audio_paths": ["/path/to/audio1.wav", "/path/to/audio2.wav"],
  "language": "en"
}
```

**Response:**
```json
{
  "success": true,
  "results": [
    {"segments": [...], "inference_time_s": 2.1},
    {"segments": [...], "inference_time_s": 2.3}
  ]
}
```

## Troubleshooting

### Daemon won't start

**Symptom:** `daemon start` fails or times out

**Possible causes:**
1. Port 8765 already in use
2. Out of GPU memory
3. Model files not downloaded

**Solutions:**
```bash
# Check if port is in use
lsof -i :8765

# Check GPU memory
nvidia-smi

# View startup logs
cat ~/.cache/vociferous/daemon.log
```

### Daemon stops responding

**Symptom:** Requests timeout or fail

**Solution:**
```bash
# Restart daemon
vociferous daemon restart

# Check logs for errors
vociferous daemon logs
```

### PID file out of sync

**Symptom:** `daemon status` shows running but `daemon stop` fails

**Solution:**
```bash
# Manually kill process
pkill -f 'uvicorn.*vociferous.server.api'

# Remove stale PID file
rm ~/.cache/vociferous/daemon.pid

# Start fresh
vociferous daemon start
```

## Security Notes

- Daemon listens on `127.0.0.1` (localhost only, not exposed to network)
- No authentication (assumes trusted local environment)
- Audio files are temporarily stored during transcription
- Logs may contain file paths

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Cold start (first launch) | ~16s |
| Transcription (warm) | ~2-5s |
| Memory usage (GPU) | ~8GB |
| Memory usage (CPU) | ~2GB |
| Concurrent requests | 1 (sequential processing) |

## Why HTTP over Unix Sockets?

The v0.5.0 release migrated from Unix sockets to HTTP for:

- ✅ **Cross-platform compatibility** (Windows, macOS, Linux)
- ✅ **Battle-tested libraries** (FastAPI, uvicorn, requests)
- ✅ **Easy debugging** (curl, browser, Postman)
- ✅ **Extensibility** (add endpoints easily)
- ✅ **Standard error handling** (HTTP status codes)
- ⚠️ Minimal overhead for localhost communication

## Future Enhancements

- [ ] Concurrent request handling
- [ ] Request queue with priorities
- [ ] Automatic idle timeout
- [ ] Metrics endpoint
- [ ] Authentication for network exposure
