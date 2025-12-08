# Vociferous Error Handling & Privacy Spec
Defines how errors surface across CLI/UI and how local-only guarantees are enforced.

## Error Categories
- **DecodeError**: Unsupported format, corrupt file, decode failure.
- **ModelLoadError**: Model weights or device init failed.
- **InferenceError**: Runtime failure during transcription.
- **TimeoutError**: Exceeded configured timeout.
- **ResourceLimitError**: Memory/device cap exceeded (ties to NFR3).
- **PermissionError**: Hotkey, microphone, filesystem, or clipboard denied.
- **ValidationError**: Bad input paths/options/config.

## Surfacing Errors
- **CLI**: Non-zero exit codes mapped per category:
  - 2 DecodeError; 3 ModelLoadError; 4 InferenceError; 5 TimeoutError; 6 ResourceLimitError; 7 PermissionError; 8 ValidationError; 1 generic/unexpected.
  - Errors written to stderr with file path/context; stdout reserved for transcription.
- **Desktop UI**: Toast/dialog with short description + suggestion; error details logged. Hotkey path shows non-blocking notification to avoid stealing focus.
- **Logs**: Structured logs include timestamp, category, file path (when applicable), suggestion, and stack trace (debug level). No audio content is logged. Engines wrap inference failures as `RuntimeError` to surface via session.

## Privacy Guarantees
- **Local-only processing**: No network calls in offline mode; model and decode fully local.
- **Data at rest**: Transcriptions saved only to user-selected locations. Temporary audio buffers cleaned after job completion.
- **Data in motion**: Clipboard writes happen only when user opts in (hotkey flow or explicit copy). No uploads or telemetry.
- **Permissions**: Microphone access requested only for hotkey capture; filesystem access limited to user-selected files/paths; clipboard access scoped to copy action.
- **Config**: Offline mode default; any optional network-dependent features must be explicitly enabled (future roadmap).

## Recovery Behaviors
- **DecodeError**: Show format/codec hint; keep processing remaining batch items.
- **ModelLoadError**: Suggest verifying model files/preset; fallback to safe-default preset if available.
- **InferenceError/Timeout**: Abort job; suggest retrying with shorter clip or lower preset.
- **ResourceLimitError**: Abort job; suggest lowering preset or closing other apps; ensure clean unload to prevent leaks.
- **PermissionError**: Prompt user to grant access; provide OS-specific guidance.

## Logging Levels
- **Error**: User-visible failures (categories above).
- **Warn**: Recoverable issues (e.g., fallback to different decoder, minor resampling).
- **Info**: Job lifecycle (queued/running/completed), model preset used, durations.
- **Debug**: Stack traces, detailed timings, decoder command lines (only when enabled).
