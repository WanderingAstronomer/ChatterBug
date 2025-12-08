# Vociferous Architecture & Module Design

Ports-and-adapters structure with a dependency-free domain, pluggable ASR engines, and a Linux-first (OS-agnostic) delivery target.

## Layer Diagram

```
UI (CLI/TUI, optional Desktop GUI)
  ↓
Application / Use Cases (TranscriptionSession push-stream orchestrator, TranscribeFile, TranscribeHotkey, Save/Export)
  ↓
Domain (AudioChunk, TranscriptSegment, Protocols: AudioSource, TranscriptionEngine, TranscriptSink)
  ↓
Adapters / Infrastructure (Audio I/O, ASR engines, Storage, Hotkeys, Config)
```

## Module Catalog

| Module              | Layer          | Responsibilities                                                                                 | Allowed Dependencies                                                   | Forbidden Dependencies                 |
| ------------------- | -------------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------- | -------------------------------------- |
| ui-cli              | UI             | Typer CLI entrypoints; stdout/stderr output; progress/state display.                            | core-app; config; logging                                              | Direct model access; OS hotkey APIs    |
| ui-tui              | UI             | Textual/Rich TUI for live transcripts, status, history.                                          | core-app; config; logging                                              | Direct model access; decoder access    |
| ui-desktop          | UI (optional)  | Desktop shell (Tauri/Electron/Qt) with history, clipboard/paste bin, drag-drop.                 | core-app; infra-hotkeys (via app callbacks); config; logging           | Model/backend calls; decoder access    |
| core-app            | Application    | Orchestrate use cases; validate requests; manage queues; route outputs; map errors to UX.       | domain; infra-storage; infra-hotkeys; infra-audio; engines (via factory); config; logging | UI toolkit specifics; OS APIs directly |
| domain              | Domain         | Typed dataclasses and Protocols; no IO or external deps.                                         | stdlib only                                                            | UI/infra modules                        |
| engines             | Adapter        | Implement `TranscriptionEngine` (WhisperTurbo default, Voxtral optional “smart” mode).           | domain; engine runtimes; logging                                       | UI modules                             |
| audio               | Adapter        | Audio capture/decoding; format detection; normalization; mic/file sources.                       | domain; ffmpeg/sounddevice; logging                                    | UI modules; model backend directly     |
| infra-storage       | Adapter        | File I/O for inputs/outputs/history/config; atomic writes.                                       | domain; filesystem APIs; logging                                       | Model backend                          |
| infra-hotkeys       | Adapter        | Register/manage system hotkeys; emit events to app queue.                                        | domain; OS hotkey bindings; logging                                    | Model backend; decoder                 |
| config              | Cross-cutting  | Load/validate config; resolve CLI/env overrides.                                                 | domain; infra-storage; logging                                         | UI toolkit specifics                   |

## Use Case Flows (Application Layer)

- **TranscribeFile**: Resolve paths -> decode/normalize -> `TranscriptionEngine` -> sink (stdout/file/UI) -> update history.
- **TranscribeHotkey**: Capture audio snippet -> decode -> `TranscriptionEngine` -> clipboard/UI sink -> notify completion -> update history.
- **Save/Export**: Take `TranscriptionResult` -> write to selected path/format -> return status/errors.

## Interfaces by Module (contracted in Interface Contracts doc)

- **domain**: `AudioChunk`, `TranscriptSegment`, Protocols `AudioSource`, `TranscriptionEngine`, `TranscriptSink`.
- **core-app**: `TranscriptionSession` coordinates push-based streaming (`start` → `push_audio` → `flush` → `poll_segments`); use-case facades accept DTOs and surface typed errors.
- **audio**: `AudioSource` implementations (MicrophoneSource, FileSource); `AudioDecoder` abstraction for decode/normalize.
- **engines**: `WhisperTurboEngine` via faster-whisper (CTranslate2 backend); `VoxtralEngine` optional for smart/long-context; `ParakeetEngine` optional for RNNT/Riva.
- **infra-storage**: `StorageRepository` for read/write/history/config.
- **infra-hotkeys**: `HotkeyListener`/`HotkeyManager` to register/unregister and emit events to app queue.
- **config**: Typed config loader (TOML in `~/.config/vociferous/config.toml`), CLI/env overrides resolved centrally.

## Engine Strategy

- Default: Whisper large-v3-turbo via faster-whisper (CTranslate2) with config for `device` and `compute_type` (e.g., int8/CPU-safe, auto-float16 on CUDA for stability) and VAD-trimmed sliding windows.
- Optional: Voxtral Mini/Small engine for "smart mode" (long-context Q&A/summaries). Selected via engine factory and config flag.
- Optional: Parakeet RNNT engine for Riva endpoint integration (local Nemo or remote Riva server).
- Single shared model instance by default to meet NFR3 (memory cap); core-app serializes work or uses bounded queues to prevent OOM.

## Streaming & Concurrency Model

- Push-based streaming: `TranscriptionSession` calls engine `start()` then feeds chunks via `push_audio()`, `flush()`, and polls segments for sinks/UI.
- Sliding window with VAD trimming inside engines (Whisper Turbo) to reduce latency and keep timestamps consistent with streamed buffers.
- Background thread for session orchestration keeps UI/CLI responsive; any thread errors propagate via `join()`.
- Batch CLI defaults to sequential per-session runs to respect NFR3; no concurrent model instances by default.

## Dependency Rules

- UI -> Application -> Domain -> Adapters (one-directional).
- Cross-layer calls upward are forbidden (infra/adapters cannot call UI).
- Shared DTOs (`TranscriptionRequest`, `TranscriptionResult`, `JobStatus`) live in Domain to avoid cycles.

## Feasibility, Compatibility, and Simplicity Check

- **Desktop stack**: Maintain a single cross-platform toolkit; Tauri + Svelte recommended for footprint; Electron acceptable fallback; Qt is an alternative if native widgets are required. UI talks only to core-app over callbacks/IPC.
- **Audio/decoder**: Standardize on ffmpeg (or static equivalent) for decode; `sounddevice` (PortAudio) for capture/playback. Adapters hide OS specifics.
- **Config & storage**: Single config loader shared by CLI/UI; overrides resolved in core-app; history storage uses the same repository to avoid drift.
- **Hotkeys**: Hotkey capture produces the same `AudioSource` DTO used by CLI/file flows to prevent divergence.
- **Error surfaces**: Typed errors flow from adapters -> domain -> application; mapping to UX happens only at UI/CLI boundary.
- **Packaging**: Poetry/uv for dev; PyInstaller bundles for Linux-first, with macOS/Windows targets using the same codepath. GPU/CPU presets determined by config.
