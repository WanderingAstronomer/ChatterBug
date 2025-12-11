Below is a **fully rebuilt, corrected, modernized version** of the Codex Context + Redesign Plan.
It removes all mismatches, incorporates your decisions, clarifies Whisper usage, demotes vLLM to optional reference-only status, and eliminates microservice implications.

This is now the **authoritative version** to use as `codex_context.md` or as the system instructions for Codex.

---

# VOCIFEROUS — **CODEX CONTEXT & REDESIGN PLAN (FINAL, CLEAN, CURRENT)**

This document tells Codex exactly how Vociferous works, what architectural boundaries it must respect, how engines operate, and how the staged redesign must proceed.
It reflects *all* decisions we have made and removes outdated or conflicting ideas.

---

# 1. Project Identity and Vision

Vociferous is a:

* **Local-first**
* **Offline, privacy-preserving**
* **Linux-native**
* **Component-based**
* **CLI-first**
* **Testable**
* **Extensible**

speech transcription system.

The system uses:

* **Canary-Qwen 2.5B** (primary ASR + refinement engine)
* **Whisper Turbo / V3 / Large** (fallback ASR engine family)

Refinement is a **text-only second pass** provided by Canary.
Everything happens *locally* with no cloud inference or telemetry.

Codex must treat this architecture as foundational and must not collapse modules or convert the project into a monolithic GUI or a Whisper-centric system.

---

# 2. Canonical Module Responsibilities (Contractual Boundaries)

Codex must treat the module responsibilities below as **strict, inviolable boundaries**.

| Module         | Responsibility                                                     |
| -------------- | ------------------------------------------------------------------ |
| **domain**     | Data structures, protocols, constants. No logic.                   |
| **audio**      | decode, vad, condense, record. No ML inference.                    |
| **engines**    | ASR and refinement engines only. No VAD. No silence logic. No GUI. |
| **refinement** | Text-only second-pass refinement. No audio logic.                  |
| **app**        | Orchestration of pipelines. No direct model loading.               |
| **config**     | Declarative engine & segmentation profiles.                        |
| **cli**        | Thin commands calling `app` or `audio`.                            |
| **sources**    | File/mic/memory → file path resolution.                            |
| **gui**        | Thin UI over workflows. Never contains logic.                      |

Codex must **not restructure modules** or push logic across these boundaries.

---

# 3. Performance Context Codex Must Consider

Vociferous is optimized for a single user running on an **RTX 3090 (24 GB)**.

### Canary-Qwen-2.5B constraints:

* Operates best on **≤40-second segments** (hard rule).
* Best performance in **FP16/BF16**.
* Model should be loaded **once** and reused.
* Dual mode (ASR and refinement) is essential.
* No built-in VAD or silence handling — those must be external.

### Batching:

* Must use **duration-based batching** (`batch_target_seconds`).
* Do NOT use “batch_size = N files.”
* Clean up GPU tensors between batches to control KV cache growth.

### Segmentation:

* Must use **Silero VAD** with merging and padding.
* Must enforce ≤40s chunks after condense.
* Use segmentation heuristics inspired by faster-whisper:

  * `min_silence_ms ≈ 1500–2000`
  * `speech_pad_ms ≈ 200–400`

Codex must code with these assumptions baked in.

---

# 4. Code Heuristics Codex Must Follow

1. Prefer **composition** over inheritance.
2. Engine-specific quirks must **never leak** into `audio`, `app`, `cli`.
3. Every refactor requires updated tests.
4. Refinement must **not** alter timestamps or segment structure.
5. CLI commands must remain stable, minimal, predictable.
6. All public-facing behaviors must remain backward compatible unless told otherwise.

---

# 5. Code Quality Expectations for Codex

Codex should:

* Use PEP 8 + strict type hints.
* Use Python 3.10+ idioms.
* Avoid global state unless explicitly allowed (engine worker).
* Use `Path` everywhere.
* Add clear docstrings and internal comments.

Codex should **avoid**:

* Random print statements.
* New third-party dependencies without being asked.
* Embedding logic inside GUI or CLI.
* Large, tangled scripts.

---

# 6. Reference URLs (For Codex Context Only)

Codex may reference these for patterns and behaviors:

* Canary-Qwen model
  [https://huggingface.co/nvidia/canary-qwen-2.5b](https://huggingface.co/nvidia/canary-qwen-2.5b)
* Silero VAD
  [https://github.com/snakers4/silero-vad](https://github.com/snakers4/silero-vad)
* faster-whisper VAD/segmentation heuristics (patterns only)
  [https://github.com/SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper)
* vLLM (reference architecture only; **not planned for Vociferous**)
  [https://vllm.ai/](https://vllm.ai/)

**Important:**
vLLM is included as inspiration for what a scalable text backend looks like,
**not** because Vociferous intends to use it.

Vociferous is permanently **local-single-user**, so vLLM is not part of the roadmap.

---

# 7. Required Behaviors for Codex During Refactor

Codex must:

1. Work in this strict order:
   **domain → engines → audio → app → config → refinement → cli → sources → gui → tests**
2. After each phase, **summarize changes** (if in iterative mode).
3. Never break tests.
4. Never regress performance.
5. Update docs along the way.
6. Preserve repo structure.
7. Request clarification **only if** ambiguity affects API or architecture; otherwise make conservative assumptions.

---

# 8. Implementation Philosophy

Codex must behave like a senior engineer:

* Faithful to the architecture.
* Cautious with assumptions.
* Protective of modularity.
* Focused on clarity and correctness.
* Avoiding premature optimization.
* Ensuring maintainability and clean seams.

---

# ADDITIONAL CONTEXT FROM OUR ENGINEERING DECISIONS

Codex must incorporate the following insights, discovered experimentally or architecturally:

---

## 1. Canary-Qwen Internal Behaviors (Important)

1. Canary loads in **float32 by default**;
   Must cast weights to FP16/BF16 **before** moving to GPU.
2. Operates best on **≤40s** segments.
3. Does not handle silence well; VAD + condense is mandatory.
4. Dual-pass architecture (ASR → LLM refinement) is foundational.
5. Refinement must be constrained (grammar + punctuation only).
6. Batching must use **audio duration**, not batch count.
7. VRAM fluctuates heavily with token count and chunk length;
   Codex must manage memory accordingly.

---

## 2. Architecture & Module Findings

Codex must maintain:

* A **strongly modular** architecture.
* A **clean domain layer** with zero logic.
* Engines that are fully **pluggable**.
* A system that is **not Whisper-centric**.
* A **file-first** (batch, not streaming) model.
* No session managers, arbiters, or global workflow objects.

---

## 3. Performance Targets

These are **design constraints**, not suggestions:

* **30 minutes of audio must transcribe in ≤60 seconds** on RTX 3090.
* **Typical batches of 30–60 seconds must finish in <5 seconds.**
* RTF target:

  * ≥30× conservative
  * ≥200× stretch
* A `vociferous bench` command will enforce performance contracts.

---

## 4. Community Techniques Vociferous Should Reuse

Codex must reuse:

* Silero VAD
* faster-whisper segmentation heuristics
* ffmpeg decoding
* PyTorch pinned memory practices

Codex must **not** reimplement these manually.

---

## 5. Long-Term Trajectory (Codex Must Design For)

Vociferous aims to be:

* The **best Linux-native ASR + refinement tool**.
* Centered on Canary as the gold-standard engine.
* Whisper as optional fallback.
* GUI as a thin surface, not a logic host.
* Stable, predictable, extensible.

vLLM is optional inspiration only — *not* part of the roadmap.

---

# PHASED REDESIGN PLAN (Current and Aligned)

Codex must follow this exact sequence.

---

# Phase 1 — DOMAIN

### Goals

* Establish canonical types and protocols.

### Tasks

* Implement `TranscriptSegment`.
* Implement `TranscriptionEngine` and `RefinementEngine` protocols.
* Add engine/config type definitions.
* Zero business logic.

---

# Phase 2 — ENGINES

### Canary Engine

* Implement dual-pass ASR + refinement.
* FP16/BF16 only.
* Load once, reuse.
* No silence logic.

### Whisper Engine

* Implement ASR-only.
* Support Turbo, V3, Large.
* Use **official local Whisper** implementation via OpenAI/HF, not faster-whisper.
* No refinement here.

### Common

* Engines must accept files only.
* Must implement `TranscriptionEngine`.
* Must be instantiated via engine factory.

---

# Phase 3 — AUDIO

### decode

* ffmpeg → 16kHz mono WAV.

### vad

* Silero VAD V3 → timestamp JSON.

### condense

* Merge timestamps.
* Apply padding.
* Enforce ≤40s chunk limit.

### record

* Microphone → WAV.

---

# Phase 4 — APP

* Create `transcribe_file_workflow()`.
* Create `transcribe_full` and `transcribe_simple` workflows.
* No direct model loading.
* Optionally introduce a *local* engine worker abstraction (in-process only).

---

# Phase 5 — CONFIG

* Implement TOML/YAML engine profiles.
* Implement segmentation profiles.
* Provide profile loaders and validators.

---

# Phase 6 — REFINEMENT

* Implement a `RefinementEngine` abstraction.
* Current impl: Canary LLM mode.
* No timestamp changes.
* Grammar/punctuation only.

---

# Phase 7 — CLI

* Wire all components individually.
* Wire workflow commands.
* Implement `vociferous bench`.

---

# Phase 8 — SOURCES

* Implement FileSource, MicSource, etc.
* Always resolve to file paths.

---

# Phase 9 — GUI

* Thin wrapper over workflows.
* No logic duplication.
* Optional, lower priority.

---

# Phase 10 — TESTS & DOCS

* All tests use real files via subprocess.
* Update architecture docs after each major phase.