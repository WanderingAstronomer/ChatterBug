# Vociferous Functional + NFR Specification
Reference requirements checklist derived from the PRD (Whisper large-v3-turbo, local-only by default).

## Functional Requirements
| ID  | Description | Notes / Acceptance |
| --- | ----------- | ------------------ |
| FR1 | Allow users to select audio files from local storage for transcription. | File chooser in UI; file path argument in CLI. |
| FR2 | Transcribe audio with Whisper large-v3-turbo (faster-whisper). | Model loads locally; VAD-trimmed sliding window; CPU-safe preset by default, CUDA auto-float16 for stability. |
| FR3 | Provide start/stop via customizable hotkeys. | System hotkey registration; conflicts detected and surfaced. |
| FR4 | Support MP3, WAV, AAC inputs (extensible). | Uses decoder abstraction; failures handled per FR11. |
| FR5 | Process all audio locally without internet. | Offline mode default; no outbound network by design. |
| FR6 | Provide a CLI for transcription. | `vociferous transcribe <files>` with flags for output/config. |
| FR7 | Allow batch transcription of N files in one command. | Sequential by default per session; parallel only when resource caps allow (per architecture doc). |
| FR8 | Write transcription output to specified path, stdout (CLI), or paste bin/text area (GUI). | Defaults documented; avoid overwriting without explicit permission. |
| FR9 | On hotkey invoke, show in-progress indicator and notify on completion. | Minimal UI element; clipboard copy optional per config. |
| FR10 | Preserve history of N recent transcriptions in UI (configurable, default 20). | Allows copy/export; supports clearing history. |
| FR11 | If a file cannot be decoded, show clear error, log file path, continue running. | Non-zero exit code for CLI; toast/dialog in UI. |
| FR12 | If model fails (e.g., OOM), abort cleanly and provide recovery suggestion. | Suggest shorter clip or smaller model/config; logs include error type. |
| FR13 | Read model/device/config from config file and/or environment variables. | CLI flags override config; validation errors surfaced. |
| FR14 | Expose a safe-default configuration that runs on modest CPU-only machines. | Default preset keeps RAM within NFR3, CPU-only path. |
| FR15 | Allow selecting the engine (whisper_turbo default; voxtral optional smart mode; parakeet_rnnt for Riva endpoint). | Config/CLI flag chooses engine; factory enforces pluggability; push-based engine API across implementations. |

## Non-Functional Requirements
| ID   | Description | Measurement |
| ---- | ----------- | ----------- |
| NFR1 | 1-minute audio on mid-range CPU-only machine transcribes in <= 90 seconds. | Benchmark on reference spec from PRD assumptions. |
| NFR2 | Hotkey latency (key release -> transcription start) <= 300 ms. | Instrument hotkey listener to model start. |
| NFR3 | Default configuration shall not exceed 8 GB RAM. | Peak RSS during transcription under default preset. |
| NFR4 | Runs on Windows, macOS, Linux with consistent CLI and config semantics. | Same commands/flags; documented OS-specific install steps only. |
| NFR5 | Can process >= 100 files sequentially without leaks/restarts. | Long-run test on reference machine. |
| NFR6 | Primary actions reachable within <= 2 steps from main UI. | UX review against UI wireframes/prototype. |
| NFR7 | Default pipeline uses a single shared model instance with bounded queues. | Profiling shows steady RSS within NFR3 under default config. |

## Feature-to-Requirement Mapping
| Key Feature | Linked Requirements |
| ----------- | ------------------ |
| High-Quality Transcription | FR2; NFR1, NFR3 |
| Local Processing | FR5; NFR4; SC4 (from PRD success criteria) |
| Hotkey Support | FR3, FR9; NFR2 |
| Multi-Format Audio Support | FR4, FR7, FR11 |
| CLI Support | FR6, FR7, FR8, FR11, FR12, FR13 |
| Engine Pluggability | FR2, FR15; NFR3, NFR7 |
| Transcription Journalizing & Organization (future) | Roadmap; not in FR set |
| Speech Analysis (future) | Roadmap; not in FR set |
