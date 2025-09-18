# ChatterBug

ChatterBug is a Linux-first, Python-based offline speech-to-text utility for single-user desktop use. It prioritizes accuracy, simplicity, and modularity, using Voxtral (primary) and Faster-Whisper (fallback) for ASR, with a minimal Tkinter UI.

## Features
- Minimal Tkinter UI: Start/Stop, transcript area, device dropdown, clipboard auto-copy
- Local-only transcription: No network calls in core flow
- GPU-aware: Uses CUDA if available, falls back to CPU
- Modular architecture: UI, audio, ASR, and storage are separate modules
- XML logging: Each transcript is appended to `~/.chatterbug/transcripts.xml` with metadata
- Config and logs stored in `~/.chatterbug/`

## Architecture
- **UI (`ui.py`)**: Tkinter window, controls, clipboard, device selection, background threads
- **Audio (`audio.py`)**: Records 16 kHz mono PCM from selected device
- **ASR (`asr.py`)**: Voxtral (CUDA if available), fallback to Faster-Whisper
- **Storage (`storage.py`)**: Appends transcripts to XML atomically, crash-safe

## Usage
1. Install dependencies: `pip install -r requirements.txt` (ensure CUDA, portaudio, libsndfile1, build-essential are present)
2. Run the app: `python3 main.py`
3. Use the UI to record, transcribe, and copy transcripts

Notes:
- System packages: on Debian/Ubuntu install `sudo apt install portaudio19-dev libsndfile1`.
- If you plan to use GPU acceleration, ensure appropriate NVIDIA drivers and CUDA toolkits are installed.

Config & data paths:
- Config: `~/.chatterbug/config.json`
- Transcripts: `~/.chatterbug/transcripts.xml`
- Logs: `~/.chatterbug/chatterbug.log`

## Development
- See `.github/copilot-instructions.md` for AI agent and contributor guidelines
- See `DEVDIARY.md` for ongoing development notes (not tracked in git)
- See `chatterbug_design_doc.md` for detailed architecture and requirements

## Testing
- Run `pytest` for unit and integration tests
- Acceptance and integration tests are described in the design doc

## Status
MVP in active development. Core modules and documentation are being scaffolded. See DEVDIARY.md for daily progress.

---
For more details, see `chatterbug_design_doc.md` and `.github/copilot-instructions.md`.