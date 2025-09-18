# Copilot Instructions for ChatterBug (concise)

Purpose: Help an AI code agent become productive quickly in this Linux-first Python STT repo.

Quick Architecture
- UI (`ui.py`): Tkinter mainloop + background threads; update UI with `root.after(...)`.
- Audio (`audio.py`): record 16 kHz mono PCM; public API returns `(wav_bytes, duration_s)`.
- ASR (`asr.py`): prefer Voxtral (CUDA), fallback to Faster-Whisper; `transcribe_wav(wav_bytes, lang="en") -> (text, meta)`.
- Storage (`storage.py`): append transcripts to `~/.chatterbug/transcripts.xml` via atomic temp-replace.

Developer Shortcuts
- Run: `python3 main.py`
- Install deps: `pip install -r requirements.txt` (system deps: `portaudio`, `libsndfile`, optional CUDA)
- Tests: `pytest`

Conventions & Patterns (project-specific)
- No network calls in the core flow — avoid introducing remote dependencies.
- GPU-aware code paths: check for CUDA availability and keep CPU fallback.
- Max recording duration enforced (default 60s) — prefer explicit time checks over open-ended recording loops.
- UI thread safety: do not touch Tkinter widgets outside the main thread; use `root.after()` for updates.
- Use background threads for both recording and ASR; keep threads short-lived and join/cleanup on errors.
- Storage must be atomic: write to a temp file then `os.replace()`.

Examples to reference
- `transcribe_wav(wav_bytes, lang="en")` should return `(text, meta)` where `meta` contains `engine`, `model`, `dur_s`, `load_ms`, `mem_mb`, `rtf`.
- XML entries: `<t at="ISO8601" engine="..." model="..." lang="en" dur_s="...">...</t>` appended under root `<transcripts>`.

Where to look
- `chatterbug_design_doc.md` — authoritative design and acceptance criteria.
- `README.md`, `.github/copilot-instructions.md` — developer workflows and quick run commands.

When editing: keep changes minimal and module-scoped. If you add new behavior, update `chatterbug_design_doc.md`.
