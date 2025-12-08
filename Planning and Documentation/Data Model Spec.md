# Vociferous Data Model Specification

Shared data structures for UI, application, and adapter layers. Types shown in pseudo-code with example JSON. Domain remains dependency-free and typed (dataclasses/Protocols in code).

## Core Types

```
enum JobStatus { QUEUED, RUNNING, COMPLETED, FAILED }

enum EngineKind { whisper_turbo, voxtral, parakeet_rnnt }

struct AudioChunk {
  bytes samples;
  int sampleRate;
  int channels;
  float startSec;
  float endSec;
}

struct AudioSourceDescriptor {
  string? path;           // file path or URI to local file
  bytes? buffer;          // optional in-memory audio
  string? mimeType;
  string? inputDevice;    // for mic capture
}

struct TranscriptionRequest {
  AudioSourceDescriptor source;
  string language = "en";
  EngineKind engine = whisper_turbo;  // whisper_turbo (default), voxtral, parakeet_rnnt
  ModelPreset preset;    // e.g., "cpu-safe-default", "gpu-int8", "smart"
  EngineConfig engineConfig;
  int? maxDurationSec;   // reject if exceeded
  map<string,string> metadata; // user/job labels
}

struct TranscriptSegment {
  float startSec;
  float endSec;
  string text;
  string language;
  float confidence;      // model-provided or heuristic
}

struct TranscriptionResult {
  string id;
  JobStatus status;
  string text;
  list<TranscriptSegment> segments;
  float durationSec;
  ModelInfo modelInfo;
  ResourceUsage usage;
  list<string> warnings;
  ErrorInfo? error;
  datetime completedAt;
}

struct ModelInfo {
  string name;          // whisper-large-v3-turbo
  string device;        // cpu/gpu name
  string precision;     // e.g., fp16, int8
  EngineKind engine;
}

struct ResourceUsage {
  float peakRamGb;
  float cpuSeconds;
  float gpuSeconds;
}

struct ErrorInfo {
  string code;         // e.g., DECODE_ERROR, MODEL_LOAD_ERROR, INFERENCE_ERROR, TIMEOUT, RESOURCE_LIMIT
  string message;
  string? filePath;    // for decode errors
  string? suggestion;  // e.g., "Try shorter clip"
}

struct OutputTarget {
  enum kind { FILE, STDOUT, CLIPBOARD, UI_PASTE_BIN }
  string? path;        // required when kind == FILE
}

struct EngineConfig {
  string modelName = "openai/whisper-large-v3-turbo";
  string computeType = "int8";     // int8, int8_float16, float16
  string device = "cpu";           // cpu, cuda, rocm
  string modelCacheDir;            // local path to models
  map<string,string> params;       // enable_batching=true|false, batch_size, beam_size, temperature, word_timestamps, etc.
}
```

## Settings / Config

```
struct AppConfig {
  string modelName = "whisper-large-v3-turbo";
  EngineKind engine = whisper_turbo;
  string device = "cpu";
  string preset = "cpu-safe-default"; // keeps within NFR3
  string computeType = "int8";
  string modelCacheDir;
  int chunkMs = 960;   // default chunk size for streaming
  int historyLimit = 20;
  HotkeyConfig hotkeys;
  PathConfig paths;
  bool offlineMode = true;
  LoggingConfig logging;
}

struct HotkeyConfig { string startStop; }
struct PathConfig { string defaultOutputDir; }
struct LoggingConfig { string level; string filePath; }
```

## Example JSON: TranscriptionResult

```json
{
  "id": "job_123",
  "status": "COMPLETED",
  "text": "Hello world",
  "segments": [
    { "startSec": 0.0, "endSec": 1.2, "text": "Hello", "language": "en", "confidence": 0.92 },
    { "startSec": 1.2, "endSec": 2.0, "text": "world", "language": "en", "confidence": 0.90 }
  ],
  "durationSec": 2.0,
  "modelInfo": { "name": "whisper-large-v3-turbo", "device": "cpu", "precision": "int8", "engine": "whisper_turbo" },
  "usage": { "peakRamGb": 5.5, "cpuSeconds": 3.0, "gpuSeconds": 0.0 },
  "warnings": [],
  "error": null,
  "completedAt": "2024-01-01T12:00:00Z"
}
```
