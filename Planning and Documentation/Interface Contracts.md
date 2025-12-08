# Vociferous Interface Contracts
Language-agnostic contracts to keep layers decoupled. Domain is dependency-free and typed; engines/audio/storage plug in via Protocol-style interfaces. Methods are assumed async or background-capable unless stated otherwise.

## Domain Types (dependency-free)
```
struct AudioChunk { bytes samples; int sample_rate; int channels; float start_s; float end_s; }
struct TranscriptSegment { string text; float start_s; float end_s; string language; float confidence; }
struct TranscriptionRequest { AudioSource source; string language?; EngineKind engine; TranscriptionOptions opts; }
struct TranscriptionResult { string text; list<TranscriptSegment> segments; Metadata meta; list<Warning> warnings; }
```

## Protocols / Interfaces

### TranscriptionEngine
```
void start(TranscriptionOptions opts)
void push_audio(bytes pcm16, int timestamp_ms)
void flush()
list<TranscriptSegment> poll_segments()
```
- **Implementations**: `WhisperTurboEngine` (default, faster-whisper large-v3-turbo with VAD sliding window and optional batching), `VoxtralEngine` (optional smart mode), `ParakeetEngine` (optional RNNT via Riva endpoint).
- **Behavior**: Stateful, push-based. Buffers audio internally (sliding window + VAD). Callers must poll for segments; legacy pull API exists as a shim.
- **Errors**: `ModelLoadError`, `InferenceError` (wrapped as `RuntimeError` from engine), `TimeoutError`, `ResourceLimitError`.

### EngineFactory
```
TranscriptionEngine build_engine(EngineKind kind, EngineConfig config)
```
- **EngineKind**: Literal `"whisper_turbo"` (default), `"voxtral"` (smart/long-context), `"parakeet_rnnt"` (RNNT via Riva endpoint).
- **Purpose**: Enforces pluggability; core-app never depends on concrete engine classes.

### AudioSource
```
Iterable<AudioChunk> stream()
```
- **Implementations**: `MicrophoneSource`, `FileSource`, `BufferSource`.
- **Behavior**: Emits normalized PCM chunks with timestamps; must be stop-able on demand (for hotkey capture).

### AudioDecoder
```
DecodedAudio decode(AudioSource source)
bool supports_format(string extension_or_mime)
```
- **Outputs**: PCM/normalized audio with sample rate, channels, duration.
- **Errors**: `UnsupportedFormatError`, `DecodeError`, `TooLongError` (with max duration), `IoError`.

### TranscriptSink
```
void handle_segment(TranscriptSegment segment)
void complete(TranscriptionResult result)
```
- **Implementations**: stdout sink, file writer, clipboard/UI event sink, in-memory history collector.

### TranscriptionSession (application orchestrator)
```
void start(AudioSource src, TranscriptionEngine engine, TranscriptSink sink, TranscriptionOptions opts)
void stop()
```
- **Behavior**: Wires source -> engine -> sink using bounded queues; runs off UI thread; ensures single-model instance by default.
- **Errors**: Propagates typed errors (decode/model/inference/timeout/resource) to UI/CLI boundary.

### HotkeyListener
```
void registerHotkey(Hotkey hotkey, HotkeyCallback cb)
void unregisterHotkey(Hotkey hotkey)
bool isRegistered(Hotkey hotkey)
```
- **Outputs**: Events for press/release; callback receives start/stop signals and optional audio buffer handles.
- **Errors**: `HotkeyConflictError`, `PermissionError`, `RegistrationError`.

### StorageRepository
```
void saveTranscription(TranscriptionResult result, OutputTarget target)
TranscriptionHistory loadHistory(int limit)
void clearHistory()
AppConfig loadConfig()
void saveConfig(AppConfig config)
```
- **Outputs**: Persisted files/history/config; supports stdout/paste bin pathways via adapters.
- **Errors**: `IoError`, `ValidationError`, `PermissionError`.

## Threading & Concurrency Guarantees
- Engine and decoder run off UI thread; callbacks marshalled to UI/TUI/CLI loop.
- Bounded queues connect `AudioSource` -> engine -> sink to control latency and respect NFR3 memory caps.
- Hotkey listener emits onto app queue and must never block UI thread.
