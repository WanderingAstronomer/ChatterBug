# Vociferous Product Requirements Document (PRD)
*AI-powered ASR that runs locally with Whisper large-v3-turbo.*

## Problem Statement
Transcribing audio is slow, error-prone, and often privacy-invasive when cloud services are involved. Users need a reliable, local-first way to turn speech into text quickly without sending data off their machine. A polished desktop experience (especially on Linux) is missing for this class of tool.

### User Personas & Primary Use Cases
- **Dev recording standups**: Wants fast, local text from short clips to paste into tickets or docs.
- **Student recording lectures**: Wants private, offline transcription of long recordings for study.
- **Privacy-focused creator**: Needs accurate, local transcription for publishing without data leakage.

### Use-Case Flows
- **Hotkey capture to clipboard**: User presses a hotkey, records up to 30s, releases; text is ready in the clipboard or UI within <= 3 seconds after release.
- **Drag-and-drop file**: User drops an audio file; a `.txt` is created alongside the source file.
- **CLI batch**: User runs a CLI command on N files; transcriptions stream to stdout or specified output paths.

## Overview
Vociferous is a local Automatic Speech Recognition (ASR) tool that uses the Whisper large-v3-turbo model (via faster-whisper) for fast, high-quality transcription, with optional Voxtral "smart mode" for long-context/Q&A and Parakeet RNNT for Riva endpoint integration. Engines are stateful and push-based (start/push/flush/poll) with VAD-trimmed sliding windows by default. All processing stays on-device to preserve privacy. Architecture follows a small, typed ports-and-adapters pattern: dependency-free domain, application orchestrators, and swappable adapters for audio I/O, ASR engines, storage, hotkeys, and UI. The initial release focuses on the core ASR pipeline (hotkey capture, batch CLI/TUI, multi-format support). Future releases add transcription journaling/organization and speech analysis.

## Key Features
### v1
- **High-Quality Transcription**: Whisper large-v3-turbo for accurate, efficient speech-to-text (CPU-safe defaults; GPU when available).
- **Local Processing**: On-device inference; offline mode by default.
- **Hotkey Support**: Customizable start/stop for quick capture.
- **Multi-Format Audio Support**: MP3, WAV, AAC (extensible via decoder).
- **CLI/TUI Support**: Typer CLI and Rich/Textual TUI for live output from terminal.
- **Pluggable Engines**: Engine factory with `whisper_turbo` default, `voxtral` optional smart mode, and `parakeet_rnnt` for Riva endpoint integration.

### Future Roadmap
- **Transcription Journalizing & Organization**.
- **Speech Analysis**: Sentiment, keyword frequency, spoken-language suggestions.
- **Mobile/real-time streaming** (post-v1).

## Out of Scope and Assumptions (v1)
- Cloud storage/processing, mobile apps.
- Languages beyond English; non-English inputs may fail gracefully (configurable for future engines).
- Advanced analytics (sentiment/keywording), journaling, organization until later versions.
- **Assumptions**: Single user on a single machine (no concurrent sessions). Reference machine has >= 16 GB RAM; GPU is optional/auto-detected but CPU defaults must meet NFRs. English-only defaults; failures fall back with clear errors. Offline mode is default; zero intentional network calls.

## Functional Requirements (FR)
1. The application shall allow users to select audio files from local storage for transcription.
2. The application shall transcribe audio files using the Whisper large-v3-turbo model.
3. The application shall provide start/stop via customizable hotkeys.
4. The application shall support MP3, WAV, AAC input (extensible to other decodable formats).
5. The application shall process all audio locally without requiring an internet connection.
6. The application shall provide a CLI to transcribe audio files from the terminal.
7. The application shall allow batch transcription of N files in one command.
8. The application shall write transcription output to a user-specified path, stdout (CLI), or a paste bin/text area (GUI).
9. When invoked via hotkey, the app shall show a minimal in-progress indicator and notify on completion.
10. The app shall preserve a history of N recent transcriptions in the UI (configurable, default 20).
11. If a file cannot be decoded, the app shall surface a clear error, log the file path, and continue running.
12. If the model fails (e.g., OOM), the app shall abort gracefully and provide a recovery suggestion (e.g., shorter clip).
13. The app shall read model/device/configuration from a config file and/or environment variables.
14. The app shall expose a safe-default configuration that runs on a modest CPU-only machine.

## Non-Functional Requirements (NFR)
- **Performance**: NFR1: 1-minute audio on a mid-range CPU-only machine transcribes in <= 90 seconds. NFR2: Hotkey latency (key release -> transcription start) <= 300 ms.
- **Resource Usage**: NFR3: Default configuration shall not exceed 8 GB RAM with chosen model settings.
- **Portability**: NFR4: Runs on Windows, macOS, and Linux with consistent CLI and config semantics.
- **Reliability**: NFR5: Process at least 100 files sequentially without memory leaks or required restarts.
- **Usability**: NFR6: Primary actions (select file, start transcription, copy text) reachable within <= 2 steps from main UI.

## High-Level Architecture
- **UI Layer**: Typer CLI + Rich/Textual TUI; optional desktop UI (Tauri/Svelte recommended; Electron/Qt acceptable fallback).
- **Application Layer (Use Cases)**: `TranscriptionSession` orchestrator; Transcribe file; Transcribe from hotkey capture; Save/export transcription.
- **Domain Layer**: Dependency-free types `AudioChunk`, `TranscriptSegment`, `TranscriptionRequest/Result`, Protocols (`AudioSource`, `TranscriptionEngine`, `TranscriptSink`).
- **Adapters Layer**: ASR engines (WhisperTurbo default, Voxtral optional), audio decode/capture (ffmpeg + sounddevice), storage/history/config, hotkey manager (OS-specific bindings behind a shared interface).

### Data Flow
`UI -> Application -> TranscriptionEngine (via factory) -> Sink/UI/Storage`

## Runtime Flow + Dependencies
- User action (file select/drag-drop/CLI/hotkey) -> audio capture/decode -> `TranscriptionEngine` (default whisper_turbo via faster-whisper) -> transcript stream -> sinks (stdout/file/UI/clipboard/history).
- Dependencies: CTranslate2/faster-whisper runtime; optional Voxtral runtime; ffmpeg (or equivalent) for decode; sounddevice for capture; local filesystem; optional clipboard API. GPU used when available; CPU-safe defaults always available.
- Permissions: Microphone access for live capture; filesystem read/write for inputs/outputs; clipboard access for copy operations. No network permissions required in offline mode.

## Success Criteria
- SC1: 95% of transcription jobs for files <= 2 minutes complete without error on reference hardware.
- SC2: Median runtime <= 1.5x audio length on reference hardware.
- SC3: Hotkey -> text appears in UI or clipboard within <= 5 seconds for 30-second recordings.
- SC4: Zero network traffic during normal operation when offline mode is enabled.
