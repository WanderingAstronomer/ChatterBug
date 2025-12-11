# Vociferous: Executive Architecture Philosophy & Design Principles

**Date:** December 2025  
**Version:** 2.0  
**Status:** Architecture Refactor in Progress (see module table)

## Module Implementation Status

| Module | Status | Notes |
|--------|--------|-------|
| **audio** | ✅ Implemented | Audio primitives (decoder, vad, condenser, recorder) |
| **engines** | 🚧 In Progress | Canary dual-pass implementation ongoing (Issue #9) |
| **refinement** | 🚧 In Progress | Replacing polish module; depends on Canary LLM mode (Issues #8, #10) |
| **cli** | ✅ Implemented | Commands and interface adapters (cli.components); explicit deps provisioning (Issue #1) |
| **app** | 🚧 In Progress | Removing TranscriptionSession/Arbiter; workflow function in progress (Issues #5, #6, #7) |
| **config** | ✅ Implemented | Config loading and management working |
| **domain** | ✅ Implemented | Core types, models, exceptions defined |
| **sources** | ✅ Implemented | File sources and microphone capture working |
| **gui** | ✅ Implemented | KivyMD GUI functional; integration ongoing |

**Legend:** ✅ Implemented · 🚧 In Progress · ❌ Not Started · 🔄 Needs Refactor

## Architecture Refactor Progress

**Completed:**
- [x] Audio preprocessing pipeline (decode, vad, condense, record)
- [x] Real-file contract testing philosophy (no mocks)
- [x] Module-based test organization
- [x] Move CLI adapter components to cli.components (separation of concerns)

**In Progress:**
- [ ] Canary-Qwen dual-pass architecture (Issue #9)
- [ ] Remove SegmentArbiter over-engineering (Issue #5)
- [ ] Remove TranscriptionSession (Issue #6)
- [ ] Redesign transcribe workflow (Issue #7)
- [ ] Rename polish → refinement (Issue #8)
- [ ] Two-tier help system implementation (Issue #15)

**Planned:**
- [ ] Deprecate Whisper/Voxtral as primary engines (Issue #20)
- [ ] Standardize batch-only engine interface (Issue #21)
- [ ] Documentation alignment and release prep (Issue #1)

---

## Core Philosophy

### **"Components, Not Monoliths"**

Vociferous is built on the principle that **every meaningful unit of functionality must be independently verifiable, composable, and debuggable.**

**Guiding Principle:**

> If you can't run it from the command line with real files and see real output, it's not a component—it's just code.

---

## Architectural Hierarchy

### **Three-Tier Structure**

```mermaid
graph TD
    M["MODULE<br/>Organizational grouping"]
    C["COMPONENT<br/>Independently executable"]
    U["UTILITY<br/>Internal helper"]

    M --> C
    C --> U
```

### **Definitions**

| Term | Definition | CLI Accessible? | Example |
| --- | --- | --- | --- |
| **Module** | Collection of related components with unified purpose | No  | `audio`, `engines` |
| **Component** | Independently executable, testable, chainable unit | **Yes** | `vociferous decode`, `vociferous vad` |
| **Utility** | Internal helper used by components | No  | `VadWrapper`, `FFmpegHelper` |

---

## Component Design Principles

### **1. Independent Executability**

**Requirement:** Every component must be callable via CLI.

**Example:**

```bash
# Component: Decoder
vociferous decode audio.mp3
# ✅ Runs standalone, no dependencies on other components

# Component: VAD
vociferous vad audio_decoded.wav
# ✅ Runs standalone, operates on standardized input

# Component: Condenser
vociferous condense timestamps.json audio_decoded.wav
# ✅ Runs standalone, explicit dependencies
```

**Anti-pattern:**

```python
# ❌ This is NOT a component (no CLI interface)
class InternalAudioProcessor:
    def process(self, data): ... 
```

---

### **2. Observable Outputs**

**Requirement:** Components must produce real, inspectable files.

**Example:**

```bash
vociferous decode input.mp3
# → Creates:  input_decoded.wav (you can listen to it)

vociferous vad input_decoded.wav
# → Creates: input_decoded_vad_timestamps.json (you can read it)

vociferous condense timestamps.json input_decoded.wav
# → Creates: input_decoded_condensed.wav (you can verify quality)
```

**Why:** If output is only in memory or internal state, you can't verify correctness.

---

### **3. Manual Chainability**

**Requirement:** Components must be manually chainable for debugging.

**Example:**

```bash
# Debug by running each step manually
vociferous decode lecture.mp3
vociferous vad lecture_decoded.wav
vociferous condense lecture_decoded_vad_timestamps.json lecture_decoded.wav
vlc lecture_decoded_condensed.wav  # ← Listen to verify! 
vociferous transcribe lecture_decoded_condensed.wav
```

**Why:** When the pipeline fails, you can isolate exactly which component broke.

---

### **4. Automatic Composition**

**Requirement:** Provide convenience commands that chain components automatically.

**Example:**

```bash
# Convenience:  runs decode → vad → condense → transcribe → refine
vociferous transcribe lecture.mp3
```

**But:** Manual chaining must always remain possible.

---

### **5. Single Responsibility**

**Requirement:** Each component does exactly one thing.

| Component | Responsibility | NOT Responsible For |
| --- | --- | --- |
| **Decoder** | Normalize to PCM mono 16kHz | ❌ VAD, ❌ Transcription |
| **VAD** | Detect speech boundaries | ❌ Audio format, ❌ Silence removal |
| **Condenser** | Remove silence using timestamps | ❌ VAD detection, ❌ Decoding |
| **Recorder** | Capture microphone audio | ❌ Preprocessing, ❌ Transcription |
| **Refiner** | Improve grammar/punctuation using LLM | ❌ ASR decoding, ❌ Audio preprocessing |

**Note:** Engines are infrastructure modules called by workflows, not CLI-accessible components themselves. The CLI exposes workflow commands like `transcribe` which orchestrate engine usage internally.

**Anti-pattern:**

```python
# ❌ Engine doing VAD (violates single responsibility)
class WhisperEngine:
    def transcribe(self, audio):
        # Detect speech (❌ should be separate component)
        vad_segments = self.detect_speech(audio)
        # Remove silence (❌ should be separate component)
        clean_audio = self.remove_silence(audio, vad_segments)
        # Transcribe (✅ correct responsibility)
        return self.transcribe(clean_audio)
```

---

### **6. Fail Loudly**

**Requirement:** Components must fail with clear error messages, not silent failures.

**Example:**

```bash
$ vociferous condense missing. json audio.wav
❌ Error:  Timestamps file not found:  missing.json

$ vociferous decode invalid.txt
❌ Error: Not a valid audio file: invalid.txt
```

**Anti-pattern:**

```python
# ❌ Silent failure (returns empty, no error)
def detect_speech(audio):
    try:
        return vad.process(audio)
    except:
        return []  # ❌ Hides the problem! 
```

---

## Testing Philosophy

### **"No Mocks, Real Files Only"**

**Problem Identified:**

- Had 100+ mock-based unit tests
  
- All tests passed ✅
  
- Program was completely broken 🔴
  

**Root Cause:** Tests tested mocks, not real behavior.

---

### **New Testing Standard**

**Requirement:** Tests must use real files and subprocess calls.

**Example:**

```python
def test_vad_detects_speech():
    """VAD detects speech in real audio file."""

    # ✅ Real file
    audio_file = Path("samples/speech_30s.wav")

    # ✅ Real CLI call
    result = subprocess.run(
        ["vociferous", "vad", str(audio_file)],
        capture_output=True,
        timeout=30,  # ← Catches hangs! 
    )

    # ✅ Real output verification
    assert result.returncode == 0
    timestamps_file = Path("speech_30s_vad_timestamps.json")
    assert timestamps_file.exists()

    with open(timestamps_file) as f:
        timestamps = json.load(f)
    assert len(timestamps) > 0
```

**Why This Works:**

- If component hangs → timeout catches it
  
- If component fails → returncode ≠ 0
  
- If output wrong → file assertions fail
  
- **Tests prove real behavior, not mocked behavior**
  

---

### **Test Organization**

```mermaid
graph TD
    T["tests/"]
    A["audio/"]
    E["engines/"]
    R["refinement/"]
    C["cli/"]
    AP["app/"]
    G["gui/"]
    I["integration/"]
    S["samples/"]

    T --> A
    T --> E
    T --> R
    T --> C
    T --> AP
    T --> G
    T --> I
    T --> S

    A --> A1["test_decoder_contract.py"]
    A --> A2["test_vad_contract.py"]
    A --> A3["test_condenser_contract.py"]
    A --> AA["artifacts/<br/>test outputs"]

    E --> E1["test_whisper_turbo_refactored.py"]
    E --> E2["test_canary_qwen_contract.py"]
    E --> EA["artifacts/<br/>test outputs"]

    R --> R1["test_refiner_contract.py"]
    R --> RA["artifacts/<br/>test outputs"]

    C --> C1["test_transcribe_command.py"]
    C --> C2["test_decode_command.py"]

    AP --> AP1["test_workflow.py"]
    AP --> AP2["test_config_resolution.py"]

    G --> G1["test_gui_integration.py"]

    I --> I1["test_full_pipeline.py"]
    I --> IA["artifacts/<br/>test outputs"]

    S --> S1["speech_30s.flac"]
    S --> S2["speech_30s.wav"]
    S --> S3["silence_5s.wav"]
```

**Organization Principles:**

- Tests mirror the `src/` module structure
- Each module has its own test directory
- `artifacts/` subdirectories contain test outputs (overwritten each run)
- `samples/` contains shared test audio files
- `integration/` tests full workflows across modules

**Principle:** If a test passes, the component works. If it fails, the component is broken.

---

## Data Flow Architecture

### **Linear Pipeline, No Cycles**

```mermaid
graph LR
  IN[Input Audio]
  D["Decoder<br/>standardized.wav"]
  V["VAD<br/>timestamps.json"]
  C["Condenser<br/>condensed.wav"]
  ASR["Canary ASR<br/>raw text"]
  R["Canary Refiner<br/>refined text"]
  OUT[Output]

  IN --> D --> V --> C --> ASR --> R --> OUT
```

**Key Principles:**

- Each stage produces a **file** (not just in-memory data)
  
- Each stage can be **run independently**
  
- No component depends on another component's **internal state**
  
- Data flows **forward only** (no backwards dependencies)
  
- Workflow orchestration is explicit and stateless—there is no `TranscriptionSession` or `SegmentArbiter`. Canary ASR receives condensed audio and must emit non-overlapping segments; refinement is a second pass over the resulting text.
  

---

## Canary-Qwen Dual-Pass Architecture

### **Two-Phase Processing**

The Canary-Qwen engine implements a sophisticated dual-pass design that separates speech recognition from text refinement:

**Pass 1: ASR Mode (Speech → Raw Text)**
- Model configured as Automatic Speech Recognition (ASR)
- Converts audio directly to raw transcribed text
- Fast, focused on accurate speech-to-text conversion
- Output: Unrefined text with potential artifacts

**Pass 2: LLM Mode (Raw Text → Refined Text)**
- Same model reconfigured as Language Model (LLM)
- Takes raw text as input and applies linguistic refinement
- Fixes grammar, punctuation, capitalization
- Output: Clean, publication-ready text

### **Key Optimization**

**Model stays loaded between passes.** This is critical for performance:
- No model reload overhead between ASR and refinement
- Memory footprint remains constant (single model in VRAM/RAM)
- Makes dual-pass practical for batch processing

### **Architecture Diagram**

```mermaid
graph LR
    A[Condensed Audio] --> ASR[Canary ASR<br/>Pass 1: Speech→Text]
    ASR --> RAW[Raw Transcription<br/>unrefined text]
    RAW --> LLM[Canary Refiner<br/>Pass 2: Text→Refined]
    LLM --> OUT[Final Output<br/>refined text]
    
    style ASR fill:#e1f5ff
    style LLM fill:#fff4e1
```

### **Usage**

```bash
# Run both passes (ASR + refinement)
vociferous transcribe audio.wav --engine canary_qwen --refine

# Run ASR only (skip refinement)
vociferous transcribe audio.wav --engine canary_qwen --no-refine

# Custom refinement instructions
vociferous transcribe audio.wav --engine canary_qwen --refine \
  --refinement-instructions "Medical terminology, formal tone"
```

### **Design Rationale**

1. **Separation of Concerns:** Speech recognition and text refinement are fundamentally different tasks
2. **Flexibility:** Users can skip refinement for speed or run it for quality
3. **Performance:** Single model load, dual-purpose usage maximizes efficiency
4. **Quality:** Dedicated refinement pass produces better results than single-pass ASR

---

## Provisioner & Engine Requirements

### **Explicit Dependency Management**

Vociferous follows a **fail-loud** principle: engines do not automatically install dependencies or download models. Instead, the system provides explicit provisioning commands to check and manage requirements.

**Core Principle:** No implicit installs, no silent downloads, no mocks in production.

### **Provisioner Commands**

The `vociferous deps` command group provides explicit dependency management:

```bash
# Check for missing dependencies and models
vociferous deps check --engine canary_qwen

# Example output shows missing packages and provides install commands
```

**Available Commands:**

| Command | Purpose | Behavior |
|---------|---------|----------|
| `deps check` | Detect missing Python packages and model weights | Non-invasive; reports status and provides actionable commands |
| `deps install` | (Future) Automated dependency installation | Will install required packages via pip |
| `deps download` | (Future) Explicit model download | Will pre-download models to cache |

**Exit Codes:**
- `0` - All dependencies satisfied
- `2` - Missing dependencies or models detected

**Philosophy:** Dependencies are managed explicitly by the user, not implicitly by the application. This prevents surprise installations, respects user control, and makes dependency issues visible immediately.

---

### **Engine Requirements Table**

Each engine declares its required packages and models explicitly. The `deps check` command inspects these requirements without triggering heavy imports.

| Engine | Required Packages | Model Repository | Model Cache Location |
|--------|------------------|------------------|---------------------|
| **canary_qwen** | `transformers>=4.38.0`<br/>`torch>=2.0.0`<br/>`accelerate>=0.28.0` | `nvidia/canary-qwen-2.5b` | `~/.cache/vociferous/models/` |
| **whisper_turbo** | `faster-whisper>=1.0.0`<br/>`ctranslate2>=4.0.0` | `Systran/faster-whisper-large-v3` | `~/.cache/vociferous/models/` |

**Notes:**
- Package versions are minimum requirements; newer versions typically work
- Models are downloaded automatically on first use if not cached
- Cache location can be configured via `model_cache_dir` in `~/.config/vociferous/config.toml`
- GPU support requires appropriate CUDA-capable `torch` installation

---

### **Cache Behavior**

**Model Cache Directory:** `~/.cache/vociferous/models/` (default)

**Behavior:**
- Models are downloaded on first use to the cache directory
- Subsequent runs reuse cached models (no re-download)
- Cache can be pre-populated using `deps download` (planned)
- Cache location is configurable via `config.toml`

**Hugging Face Cache Integration:**
- Models use Hugging Face Hub's cache structure
- Cache entries follow `models/hub/model--<org>--<name>/` pattern
- Compatible with `HF_HOME` environment variable

**Cache Verification:**
- `deps check` inspects cache for model presence
- Reports "CACHED" for available models, "NOT CACHED" otherwise
- Does not validate model integrity (assumes cached = valid)

---

### **Fail-Loud Contract**

**Principle:** If a dependency is missing, the system must fail immediately with a clear, actionable error message.

**What This Means:**
- ❌ **No implicit installs** - The system never runs `pip install` automatically
- ❌ **No silent downloads** - Model downloads are explicit and visible
- ❌ **No mock fallbacks** - Production code must use real implementations
- ✅ **Clear error messages** - Missing dependencies trigger errors with installation instructions
- ✅ **Explicit provisioning** - User controls when and how dependencies are installed

**Example Error Flow:**

```bash
$ vociferous transcribe audio.wav --engine canary_qwen

❌ Error: Missing required packages for canary_qwen engine
   - transformers>=4.38.0 (not installed)
   - torch>=2.0.0 (not installed)

Run: vociferous deps check --engine canary_qwen
Then: pip install transformers torch accelerate
```

**Anti-Pattern (What We Don't Do):**

```python
# ❌ Silent fallback to mock (hides the problem)
try:
    from transformers import AutoModel
    use_mock = False
except ImportError:
    use_mock = True  # User doesn't know they're not getting real results!

# ❌ Implicit dependency installation (violates user control)
try:
    import torch
except ImportError:
    print("Installing torch...")
    subprocess.run(["pip", "install", "torch"])  # Surprise!
```

**Correct Pattern (What We Do):**

```python
# ✅ Explicit check with clear error
try:
    from transformers import AutoModel
except ImportError:
    raise RuntimeError(
        "Missing required package: transformers\n"
        "Run: pip install transformers>=4.38.0\n"
        "Or check dependencies: vociferous deps check --engine canary_qwen"
    )
```

---

### **Developer Workflow**

**Setting Up a New Engine:**

1. **Check dependencies:**
   ```bash
   vociferous deps check --engine canary_qwen
   ```

2. **Install missing packages:**
   ```bash
   pip install transformers torch accelerate
   ```

3. **Verify installation:**
   ```bash
   vociferous deps check --engine canary_qwen
   # Should show: ✓ All dependencies satisfied
   ```

4. **First run (downloads model):**
   ```bash
   vociferous transcribe audio.wav --engine canary_qwen
   # Model downloads to ~/.cache/vociferous/models/ on first use
   ```

**CI/Offline Workflows:**

For environments without internet access:
1. Pre-populate model cache on a machine with internet
2. Copy `~/.cache/vociferous/models/` to offline environment
3. `deps check` verifies cached models are present
4. Transcription runs without network access

**Future Enhancements (Planned):**

```bash
# Explicit dependency installation (Issue #1 follow-up)
vociferous deps install --engine canary_qwen --yes

# Explicit model download (Issue #1 follow-up)
vociferous deps download --engine canary_qwen
```

---

## Module Architecture

### **Complete Module List**

Vociferous is organized into **9 modules**, each with a clear responsibility and visibility boundary:

| Module | Purpose | CLI Components? | Key Responsibilities |
|--------|---------|-----------------|---------------------|
| **audio** | Audio processing primitives | ❌ No (primitives only) | FfmpegDecoder, SileroVAD, FFmpegCondenser, SoundDeviceRecorder |
| **engines** | Speech-to-text conversion | ❌ No (infrastructure) | Canary-Qwen (default), Whisper Turbo, Voxtral |
| **refinement** | Text post-processing via Canary LLM pass | ❌ No (internal, future CLI `refine`) | Grammar/punctuation refinement, prompt handling |
| **cli** | Command-line interface | ✅ Yes | Typer commands, argument parsing, help system, interface adapters (cli.components) |
| **app** | Workflow orchestration | ❌ No | Transparent workflow functions (no sessions, no arbiters) |
| **config** | Configuration management | ❌ No | Settings, defaults, config file handling |
| **domain** | Core domain models & protocols | ❌ No | Typed data structures, contracts, errors |
| **sources** | Audio input abstractions | ❌ No | File/memory/microphone sources producing files |
| **gui** | Graphical user interface | ❌ No (separate interface) | KivyMD GUI wrapper around workflows |

**Notes:**
- Engines and refinement are infrastructure invoked by workflows and components; they are not exposed as standalone CLI commands.
- The `app` module coordinates workflows explicitly—there is **no** `TranscriptionSession` or `SegmentArbiter`.
- **Audio module contains only primitives** (decoder, VAD, condenser, recorder classes); **CLI adapters** (DecoderComponent, VADComponent, etc.) are in `cli.components`.

### **Module Organization Principles**

**1. CLI-Accessible Commands (via cli.components)**

These components can be invoked directly from the command line:
- `vociferous decode` - Audio format normalization (DecoderComponent)
- `vociferous vad` - Voice activity detection (VADComponent)
- `vociferous condense` - Silence removal (CondenserComponent)
- `vociferous record` - Microphone capture (RecorderComponent)

**2. Infrastructure Modules (engines, refinement)**

These modules are called by workflows, not directly by users:
- Engines provide transcription capabilities
- Refinement modules improve text quality
- Accessed through high-level commands like `transcribe`

**3. Support Modules (config, domain, sources)**

These modules provide supporting functionality:
- Configuration management
- Data structure definitions
- I/O abstractions that emit files for downstream processing

---

## User Help vs Developer Help

### **Two-Tier Help System**

Vociferous provides separate help interfaces for users and developers:

**User-Facing Commands (`--help`)**

These are production-ready commands intended for end users:
- `vociferous transcribe` - Complete transcription workflow
- `vociferous languages` - List supported languages
- `vociferous check` - Verify system dependencies

**Developer-Facing Commands (`--dev-help`)**

These are individual components for debugging and development:
- `vociferous decode` - Test audio decoding
- `vociferous vad` - Test voice activity detection
- `vociferous condense` - Test silence removal
- `vociferous refine` - Text-only refinement (planned CLI component; LLM pass)
- `vociferous record` - Test microphone capture
- `vociferous transcribe` - Full workflow orchestrator (shows how components chain)

**Rationale:**

- **Users** want simple, high-level workflows that "just work"
- **Developers** need access to individual components for debugging
- Separating help prevents overwhelming users with internal details
- Makes component-level testing possible without exposing complexity

---

## Artifact Management

### **Test Artifacts**

**Location:** `tests/<module>/artifacts/`

Tests produce artifacts (audio files, timestamps, transcripts) for verification:

```
tests/
  audio/
    artifacts/
      test_decode_output.wav
      test_vad_timestamps.json
  engines/
    artifacts/
      test_transcription.json
  integration/
    artifacts/
      test_full_pipeline_output.txt
```

**Behavior:**
- Artifacts are **overwritten on each test run**
- Allows developers to inspect test outputs
- Not committed to git (in `.gitignore`)
- Helps debug test failures

### **User-Facing Artifacts**

**Default Behavior:** Temporary files

```bash
# Creates temp files, cleans up automatically
vociferous transcribe lecture.mp3
# → Uses /tmp/vociferous-XXXXX/ for intermediates
# → Only final output kept: lecture_transcript.txt
```

**Debugging Mode:** Keep intermediate files

```bash
# Keeps all intermediate files for inspection
vociferous transcribe lecture.mp3 --keep-intermediates
# → Creates: lecture_decoded.wav
# → Creates: lecture_vad_timestamps.json
# → Creates: lecture_condensed.wav
# → Creates: lecture_transcript.txt
```

### **Manual Component Execution**

When running components manually, files are **always kept**:

```bash
vociferous decode lecture.mp3
# → Creates lecture_decoded.wav (permanent file)

vociferous vad lecture_decoded.wav
# → Creates lecture_decoded_vad_timestamps.json (permanent file)

vociferous condense lecture_decoded_vad_timestamps.json lecture_decoded.wav
# → Creates lecture_decoded_condensed.wav (permanent file)
```

**Rationale:** When debugging, you want to inspect every step's output.

---

## Separation of Concerns

### **Audio Module vs Engine Module**

| Concern | Audio Module | Engine Module |
| --- | --- | --- |
| **Responsibility** | Prepare audio for transcription | Convert speech to text |
| **Operations** | Decode, VAD, condense, record | Transcribe (ASR), provide segments for refinement |
| **Output** | Clean audio files | Text segments (non-overlapping) |
| **No Overlap** | ❌ No transcription | ❌ No audio preprocessing |

**Anti-pattern (Old Architecture):**

```python
# ❌ Engine doing audio preprocessing
class WhisperEngine:
    def __init__(self, vad_service):  # ❌ Shouldn't have VAD
        self.vad = vad_service

    def transcribe(self, audio):
        # ❌ Engine shouldn't do VAD
        segments = self.vad.detect_speech(audio)
        # ❌ Engine shouldn't remove silence
        clean = self.remove_silence(audio, segments)
        return self.whisper_model.transcribe(clean)
```

**Correct Architecture:**

```python
# ✅ Audio Module handles preprocessing
decoded = decoder.decode("audio.mp3")
timestamps = vad.detect_speech(decoded)
condensed = condenser.condense(decoded, timestamps)

# ✅ Engine only transcribes
segments = engine.transcribe(condensed)
```

---

## Module Architecture

### **What is a Module?**

**Definition:** A module is a logical collection of related functionality that serves a specific architectural purpose. Not all modules need CLI-accessible components - some provide infrastructure (config, domain), orchestration (app), or interfaces (cli, gui).

**Key Characteristics:**
- **Cohesive Purpose:** All code in a module serves a unified architectural goal
- **Clear Boundaries:** Modules interact through well-defined interfaces
- **Varying Accessibility:** Some modules expose CLI components, others provide internal infrastructure

---

### **Complete Module Inventory**

| Module | Purpose | Contains Components? | Key Responsibilities |
| --- | --- | --- | --- |
| **audio** | Audio preprocessing | ✅ Yes | Decode, VAD, condense, record - prepares audio for transcription |
| **engines** | Speech-to-text transcription | ❌ No* | Canary-Qwen, Whisper Turbo, Voxtral - invoked by workflows |
| **refinement** | Text post-processing via Canary LLM | ❌ No (internal; future `refine` CLI) | Grammar/punctuation refinement, prompt handling |
| **cli** | Command-line interface | ✅ Yes (workflows) | Typer commands, argument parsing, help tiers |
| **app** | Workflow orchestration | ❌ No | Transparent workflow functions; no sessions, no arbiters |
| **config** | Configuration management | ❌ No | Load/validate settings from files and CLI arguments |
| **domain** | Core types and contracts | ❌ No | Models, exceptions, protocols, constants |
| **sources** | Audio input sources | ❌ No | File readers, memory buffers, microphone capture |
| **gui** | Graphical interface | ❌ No | KivyMD application, screens, UI components |

**\*Note:** Engines are not directly CLI-accessible. They are infrastructure called by workflow commands such as `transcribe`.

---

### **Module Categories**

Modules fall into four architectural categories:

#### **1. Processing Modules**
- **audio**: Transforms raw audio into standardized, preprocessed files
- **engines**: Converts preprocessed audio into text transcripts
- **refinement**: Runs Canary LLM refinement over transcripts

**Characteristic:** These modules perform domain transformations (audio → text → refined text)

#### **2. Interface Modules**
- **cli**: Command-line user interface
- **gui**: Graphical user interface

**Characteristic:** These modules expose functionality to users but don't contain business logic

#### **3. Infrastructure Modules**
- **config**: Manages system configuration
- **domain**: Defines core types and contracts
- **sources**: Provides audio input abstractions

**Characteristic:** These modules provide foundational services used by other modules

#### **4. Orchestration Modules**
- **app**: Coordinates workflows and manages execution

**Characteristic:** This module composes components from other modules into complete workflows

---

### **Module Boundaries and Interactions**

#### **What Belongs Where**

| If you're implementing... | It belongs in... | NOT in... |
| --- | --- | --- |
| Audio format conversion (primitive) | `audio` | ❌ `engines`, ❌ `app` |
| Speech detection (VAD primitive) | `audio` | ❌ `engines`, ❌ `cli` |
| File-IO adapter for audio primitives | `cli.components` | ❌ `audio`, ❌ `app` |
| Transcription algorithm | `engines` | ❌ `audio`, ❌ `app` |
| Text grammar fixes | `refinement` | ❌ `engines`, ❌ `audio` |
| Command parsing | `cli` | ❌ `app`, ❌ `audio` |
| Pipeline coordination | `app` | ❌ `cli`, ❌ `engines` |
| Configuration loading | `config` | ❌ `cli`, ❌ `app` |
| Data models | `domain` | ❌ Any specific module |
| File/microphone input | `sources` | ❌ `audio`, ❌ `cli` |
| UI screens | `gui` | ❌ `cli`, ❌ `app` |

#### **Module Interaction Flow**

```mermaid
graph TD
        CLI[cli Module]
        GUI[gui Module]
        APP[app Module]
        CFG[config Module]
        SRC[sources Module]
        AUD[audio Module]
        ENG[engines Module]
        REF[refinement Module]
        DOM[domain Module]

        CLI --> APP
        GUI --> APP
        APP --> CFG
        APP --> SRC
        APP --> AUD
        APP --> ENG
        APP --> REF
    
        AUD --> DOM
        ENG --> DOM
        REF --> DOM
        SRC --> DOM
        CFG --> DOM

        style CLI fill:#e1f5ff
        style GUI fill:#e1f5ff
        style APP fill:#fff4e1
        style AUD fill:#e8f5e9
        style ENG fill:#e8f5e9
        style REF fill:#e8f5e9
        style CFG fill:#f3e5f5
        style DOM fill:#f3e5f5
        style SRC fill:#f3e5f5
```

**Data Flow Example:**
```
User Input (cli/gui)
    → app orchestrates workflow (no session objects)
    → sources provides audio input
    → audio preprocesses (decode → VAD → condense)
    → engines transcribe preprocessed audio
    → refinement improves transcript text via Canary LLM
    → app returns results to the user interface
```

---

### **Infrastructure vs Components Distinction**

**Critical Understanding:** Not all modules need CLI-accessible components.

**Modules WITH Components (CLI-accessible)**

**audio module:**
```bash
vociferous decode audio.mp3       # ✅ Component
vociferous vad audio.wav          # ✅ Component
vociferous condense timestamps.json audio.wav  # ✅ Component
vociferous record                 # ✅ Component
```

Recorder component implementation lives in `vociferous/cli/components/recorder.py` and wraps the low-level `SoundDeviceRecorder` primitive defined in `vociferous/audio/recorder.py`.

**cli module (workflows):**
```bash
vociferous transcribe audio.mp3   # ✅ Workflow orchestrator (calls components + engines)
# `vociferous refine` is planned as a developer-facing component for text-only refinement
```

#### **Modules WITHOUT Components (Infrastructure)**

**engines module:**
```python
# ❌ NOT directly callable via CLI
# ✅ Called by app workflow functions
engine = build_engine("canary_qwen")
segments = engine.transcribe_file(audio_path)
```

**refinement module:**
```python
# ❌ NOT directly callable via CLI (refine CLI planned)
# ✅ Invoked by workflows for Canary LLM pass
refined = engine.refine_text(raw_text, instructions)
```

**config module:**
```python
# ❌ NOT a component
# ✅ Infrastructure used by all modules
config = load_config()
```

**domain module:**
```python
# ❌ NOT a component
# ✅ Core types used everywhere
segment = TranscriptSegment(text="...", start=0.0, end=1.0)
```

**sources module:**
```python
# ❌ NOT a component
# ✅ Infrastructure providing input abstractions
source = FileSource(path)
audio_data = source.read()
```

**gui module:**
```python
# ❌ NOT CLI-accessible (separate interface)
# ✅ Alternative UI layered on workflows
app = VociferousGUI()
app.run()
```

---

### **Module Design Guidelines**

When adding functionality, ask:

1. **Which module's purpose does this serve?**
   - Audio transformation → `audio`
   - Transcription → `engines`
    - Text refinement → `refinement`
   - User interaction → `cli` or `gui`
   - Workflow coordination → `app`
   - Configuration → `config`
   - Core types → `domain`
   - Input handling → `sources`
    - Persistence helpers → handled within workflows as needed (not a separate module)

2. **Does it need to be a CLI component?**
   - Independently testable operation → Consider making it a component
   - Infrastructure/helper → Keep it as internal module functionality
   - Workflow coordination → Keep in `app`, expose via `cli` component

3. **What are its dependencies?**
   - Depends on specific module → It might belong in that module
   - Used by multiple modules → Consider `domain` or infrastructure module
   - Orchestrates multiple modules → Belongs in `app`

4. **Is it independently verifiable?**
   - Yes, produces observable output → Strong candidate for component
   - No, internal transformation → Keep as module internal

---

## Batch vs Streaming

### **Design Decision: Batch Processing**

**What is Batch Processing?**

Batch processing means: **complete file in → complete result out**. The entire audio file is processed as a single unit, from start to finish, producing the complete transcription before returning.

**Use Case:**

Vociferous is designed for users who submit **complete audio files** for transcription, not continuous real-time streams. Examples:
- Pre-recorded lectures
- Meeting recordings
- Podcast episodes
- Completed interviews

**Why Batch is Correct for Vociferous:**

1. **Simpler Architecture:** No buffering state, no overlap handling, no partial results
2. **Matches ML APIs:** Whisper, Canary-Qwen, and similar models expect complete audio inputs
3. **Matches Use Case:** Users have complete files they want transcribed, not live microphone streams
4. **Eliminates Complexity:** No need to handle chunk boundaries, duplicates, or partial segments
5. **Easier to Test:** Deterministic input/output relationships

**Architecture:**

```python
# ✅ Simple batch interface
class TranscriptionEngine:
    def transcribe_file(self, audio_path: Path) -> list[TranscriptSegment]:
        """Transcribe entire file in one operation."""
        ... 
```

**Anti-pattern (Old Architecture):**

```python
# ❌ Unnecessary streaming complexity for batch use case
class TranscriptionEngine:
    def start(self): ...
    def push_audio(self, chunk: bytes): ...  # Why chunks for complete files?
    def flush(): ...
    def poll_segments(): ...  # When to poll? How to handle overlaps?
```

**Guardrail:** Any `start/push_audio/flush/poll` API you see is legacy—do not reintroduce streaming abstractions. Engines take a **file path in** and return **full-sequence segments out**.

**Note:** While Vociferous uses batch processing, individual components like `record` can still capture audio from the microphone. The difference is that recording produces a **complete file** which is then processed in batch, rather than streaming audio chunks directly to the transcription engine.
  

---

## Configuration Philosophy

### **Sane Defaults, Explicit Overrides**

**Principle:** System should work out-of-the-box, but allow customization.

**Example:**

```bash
# ✅ Works with defaults
vociferous transcribe audio.mp3

# ✅ Override when needed
vociferous transcribe audio.mp3 \
  --engine canary_qwen \
  --language es \
  --refine
```

**Configuration Hierarchy:**

1. **Hardcoded defaults** (in code)
  
2. **Config file** (`~/.config/vociferous/config.toml`)
  
3. **CLI flags** (highest priority)
  

---

## Error Handling Strategy

### **Fail Fast, Fail Clear**

**Principle:** Better to crash with a clear error than continue silently broken.

**Example:**

```python
# ✅ Explicit validation
def condense(audio_path:  Path, timestamps_path: Path):
    if not timestamps_path.exists():
        raise FileNotFoundError(
            f"Timestamps file not found: {timestamps_path}\n"
            f"Run 'vociferous vad {audio_path}' first."
        )

    timestamps = json.loads(timestamps_path.read_text())
    if not timestamps:
        raise ValueError(
            f"No speech detected in {audio_path}.\n"
            f"Audio may be silent or VAD threshold too high."
        )

    # ... proceed with condensation
```

**Anti-pattern:**

```python
# ❌ Silent failure
def condense(audio_path, timestamps_path):
    try:
        timestamps = json.loads(timestamps_path.read_text())
    except: 
        timestamps = []  # ❌ Hides the problem!

    if not timestamps:
        return audio_path  # ❌ No error, user doesn't know it failed
```

---

## Dependency Management

### **Components Declare Dependencies Explicitly**

**Principle:** If Component B needs Component A's output, it should **require the file**, not call Component A internally.

**Example:**

```bash
# ✅ Explicit dependency (user provides VAD output)
vociferous condense timestamps.json audio.wav

# ❌ Implicit dependency (condenser calls VAD internally)
# This would hide the VAD step and make debugging impossible
vociferous condense audio.wav  # Where are timestamps?
```

**Why:** Makes data flow visible and debuggable.

---

## Performance Optimization Strategy

### **Correctness First, Speed Second**

**Principle:** Optimize only after proving correctness.

**Workflow:**

1. Implement simple, correct version
  
2. Test thoroughly with real files
  
3. Profile to find bottlenecks
  
4. Optimize hot paths only
  
5. Re-test to ensure correctness preserved
  

**Example:**

```python
# Phase 1: Correct but slow
def condense(audio, timestamps):
    segments = []
    for start, end in timestamps:
        segment = extract_audio_range(audio, start, end)
        segments.append(segment)
    return concatenate(segments)

# Phase 2: Optimized (only after profiling showed this was slow)
def condense(audio, timestamps):
    # Use FFmpeg concat demuxer (O(n) instead of O(n²))
    return ffmpeg_concat_segments(audio, timestamps)
```

---

## Documentation Standards

### **Every Component Needs:**

1. **Purpose** - What does it do?
  
2. **CLI Usage** - How to run it?
  
3. **Input Format** - What does it expect?
  
4. **Output Format** - What does it produce?
  
5. **Example** - Real command with real files
  
6. **Error Cases** - What can go wrong?
  

**Example:**

````markdown
## Condenser Component

**Purpose:** Remove silence from audio using VAD timestamps.

**Usage:**
```bash
vociferous condense <timestamps.json> <audio.wav> [--output <path>]
````

**Input:**

- `timestamps.json`: Speech boundaries from VAD (format: `[{"start": 0.0, "end": 2.5}, ...]`)
  
- `audio.wav`: Decoded audio file (PCM mono 16kHz)
  

**Output:**

- Condensed WAV file with silence removed

**Example:**

```bash
vociferous vad lecture.wav
vociferous condense lecture_vad_timestamps.json lecture.wav
# → Creates lecture_condensed.wav
```

**Errors:**

- `FileNotFoundError`: Timestamps file doesn't exist
  
- `ValueError`: Timestamps list is empty (no speech detected)
  
---

## Version Control Strategy

### **Commit Message Standard**

**Format:**
Commit messages must follow this structure and be limited to a single affected file or logical change:

```markdown
[CREATE/UPDATE/DELETE]: file1, file2, ...
```

**Changes:**

- A bullet point description of what changed
- Why it changed
- Impact on system
  
**Testing:**

- A bullet point description of tests added/modified
- What scenarios are covered
- How it ensures correctness

**Example:**

```markdown
[CREATE]: vociferous/cli/components/vad.py, tests/audio/test_vad_contract.py

**Changes:**

- Added VAD component with CLI interface
- Implements speech boundary detection using Silero
- Returns timestamps as JSON for downstream components

**Testing:**

- Added contract test using real 30s audio sample
- Verifies JSON output format and timestamp validity
- Includes timeout protection (catches hangs)
```

---

## Deprecation Policy

### **Don't Break, Replace**

**Principle:** When refactoring, keep old interface working until new interface proven.

**Workflow:**

1. Implement new interface
2. Add tests for new interface
3. Mark old interface as deprecated
4. Run both in parallel for one release
5. Remove old interface only after new one stable

**Example:**

```python
# Old interface (deprecated but still works)
@deprecated("Use transcribe_file() instead")
def push_audio(self, chunk: bytes):
    # ...code

# New interface
def transcribe_file(self, audio_path: Path):
    # ... code
```

## CLI Design - Two-Tier Help System

### **Philosophy: User Convenience vs Developer Transparency**

**Problem:**

- End users want simple, focused commands for everyday transcription tasks
- Developers need access to low-level components for debugging and manual pipeline execution
- Showing all commands in default help creates clutter and overwhelms new users

**Solution:** Two separate help flags targeting different audiences.

---

### **`--help` (User-Facing)**

Shows only high-level commands for typical use cases.

**Target Audience:** End users who want to transcribe audio files.

**Commands Included:**

- `transcribe` - Main transcription workflow (audio → text)
- `languages` - List supported language codes
- `check` - Verify system prerequisites (ffmpeg, dependencies)

**Example Output:**

```bash
$ vociferous --help

Usage: vociferous [OPTIONS] COMMAND

Vociferous - Local-first AI transcription

Commands:
  transcribe  Transcribe audio file to text
  languages   List supported language codes
  check       Verify system prerequisites

Options:
  --help      Show this message and exit
  --dev-help  Show developer commands

Run 'vociferous COMMAND --help' for more information on a command.
```

**Design Goal:** Keep it simple - users see only what they need for daily work.

---

### **`--dev-help` (Developer-Facing)**

Shows all components including low-level debugging tools.

**Target Audience:** Developers debugging issues, building custom pipelines, or understanding internals.

**Commands Included:**

**Audio Components:**
- `decode` - Normalize audio to PCM mono 16kHz
- `vad` - Detect speech boundaries (Voice Activity Detection)
- `condense` - Remove silence using VAD timestamps
- `record` - Capture microphone audio

**Workflow Commands:**
- `transcribe` - Main transcription workflow (decode → VAD → condense → Canary ASR → Canary Refiner)
- `refine` - Text-only refinement (planned CLI; Canary LLM pass)

**Utilities:**
- `languages` - List supported language codes
- `check` - Verify system prerequisites

**Example Output:**

```bash
$ vociferous --dev-help

Usage: vociferous [OPTIONS] COMMAND

Vociferous - Developer Commands
(For debugging and manual pipeline construction)

Audio Components:
  decode     Normalize audio to PCM mono 16kHz
  vad        Detect speech boundaries
  condense   Remove silence using VAD timestamps
  record     Capture microphone audio

Workflow Commands:
    transcribe   Main transcription workflow (decode → VAD → condense → Canary ASR → Canary Refiner)
    refine       Text-only refinement (planned CLI; Canary LLM mode)

Utilities:
  languages  List supported language codes
  check      Verify system prerequisites

Options:
  --help      Show user commands (simplified)
  --dev-help  Show this developer help

Note: These low-level components allow manual pipeline debugging.
      Most users should use 'transcribe' instead.
```

**Design Goal:** Full transparency - developers see everything.

---

### **Command Categorization Criteria**

**User Help (`--help`) includes:**

- ✅ High-level workflows (transcribe audio → get text)
- ✅ Configuration/setup utilities (languages, check)
- ✅ Commands 90% of users need
- ❌ No low-level components
- ❌ No manual pipeline steps

**Developer Help (`--dev-help`) includes:**

- ✅ All commands from user help
- ✅ Low-level audio processing components (decode, vad, condense)
- ✅ Workflow orchestrators (transcribe) and refinement tools (planned `refine`)
- ✅ Recording and capture tools
- ✅ Everything needed for manual debugging

**Decision Rule:**

> *If a user needs to understand the internal pipeline to use it → Developer Help*  
> *If a user just wants results without internal knowledge → User Help*

---

### **Implementation Notes**

**Current Status (as of December 2025):**

The CLI currently uses `rich_help_panel` in Typer to organize commands into visual groups:

- `"Core Commands"` - Main workflows (transcribe)
- `"Utilities"` - Helper commands (languages, check)
- `"Audio Components"` - Low-level components (decode, vad, condense)

**Future Implementation (Issue #15):**

The two-tier help system will be implemented by:

1. Adding custom `--dev-help` flag handling in the main CLI callback
2. Filtering visible commands based on which help flag is used
3. Using Typer's command metadata to mark commands as "user" or "developer"
4. Preserving the existing `rich_help_panel` for visual organization

**Code Pattern for Categorizing Commands:**

```python
# User-facing command (appears in --help)
@app.command(
    rich_help_panel="Core Commands",
    hidden=False,  # Visible in default help
)
def transcribe(...):
    """Transcribe audio file to text."""
    pass

# Developer-facing command (only in --dev-help)
@app.command(
    rich_help_panel="Audio Components",
    hidden=True,  # Hidden from default help, shown in --dev-help
)
def decode(...):
    """Normalize audio to PCM mono 16kHz."""
    pass
```

**Testing Requirements:**

- `vociferous --help` must show only user commands
- `vociferous --dev-help` must show all commands
- Both help outputs must be clear and well-organized
- Command descriptions must be appropriate for their audience

---

### **User Experience Goals**

**For New Users:**

- See 3-5 essential commands, not 10+
- Understand "what can I do?" in 5 seconds
- Get hint about developer commands without overwhelming

**For Developers:**

- Access all components for debugging
- Understand component responsibilities
- Manually chain pipeline steps when needed

**For Everyone:**

- Consistent command naming and behavior
- Clear error messages explaining what went wrong
- Discoverable features through progressive disclosure

---

## Summary: Core Tenets

1. **Components over monoliths** - Every meaningful unit must be independently executable
  
2. **Real files over mocks** - Tests must use actual I/O to prove correctness
  
3. **Observable outputs** - Every component produces inspectable files
  
4. **Manual chainability** - Pipeline must be debuggable step-by-step
  
5. **Single responsibility** - Each component does exactly one thing
  
6. **Fail loudly** - Explicit errors over silent failures
  
7. **Batch over streaming** - Simpler architecture for preprocessed audio
  
8. **Separation of concerns** - Audio preprocessing ≠ transcription
  
9. **Correctness first** - Optimize only after proving correctness
  
10. **Sane defaults** - Works out-of-the-box, customizable when needed
  

---

## Architecture Diagram

### **Component vs Workflow Distinction**

```mermaid
graph TD
    U["USER INPUT<br/>audio.mp3"]

    %% CLI-Accessible Components (solid boxes)
    D_CMD["vociferous decode<br/>CLI Component"]
    D_OUT["audio_decoded.wav<br/>observable file"]

    V_CMD["vociferous vad<br/>CLI Component"]
    V_OUT["audio_vad_timestamps.json<br/>observable file"]

    C_CMD["vociferous condense<br/>CLI Component"]
    C_OUT["audio_condensed.wav<br/>observable file"]

    %% Workflow Orchestrator (dashed box)
    T_WORKFLOW["vociferous transcribe<br/>Workflow Orchestrator"]
    
    %% Internal Components (rounded boxes)
    ASR["Canary ASR<br/>Internal: Pass 1"]
    REF["Canary Refiner<br/>Internal: Pass 2"]
    
    T_OUT["transcript.txt<br/>observable file"]

    %% Data Flow (solid arrows)
    U --> D_CMD
    D_CMD --> D_OUT
    D_OUT --> V_CMD
    V_CMD --> V_OUT
    D_OUT --> C_CMD
    V_OUT --> C_CMD
    C_CMD --> C_OUT

    %% Workflow Orchestration (dotted arrows)
    C_OUT -.-> T_WORKFLOW
    T_WORKFLOW -.calls.-> ASR
    ASR -.raw text.-> REF
    REF -.refined.-> T_WORKFLOW
    T_WORKFLOW --> T_OUT

    style D_CMD fill:#a8d5ff
    style V_CMD fill:#a8d5ff
    style C_CMD fill:#a8d5ff
    style T_WORKFLOW fill:#fff3a8
    style ASR fill:#d5ffd5
    style REF fill:#d5ffd5
```

**Legend:**
- **Solid Boxes (Blue)**: CLI-accessible components - users can run these directly
- **Dashed Box (Yellow)**: Workflow orchestrator - coordinates multiple operations
- **Rounded Boxes (Green)**: Internal components - called by workflows, not directly accessible
- **Solid Arrows**: Data flow - files passed between components
- **Dotted Arrows**: Orchestration - workflow calls and coordinates

**Key Principles:**
- CLI components produce **observable files** that can be inspected
- Workflows **coordinate** components but don't expose internal steps
- Internal components (Canary ASR, Refiner) are implementation details
- Each data flow arrow represents an **independently testable** transition

---

**Architecture Validation Checklist:**

Each arrow (→) represents a relationship that is:
- ✅ Independently testable 
- ✅ Manually runnable (for components)
- ✅ Produces observable output 
- ✅ Single responsibility

---

**This is the agreed architecture philosophy for Vociferous.** All future development must adhere to these principles.