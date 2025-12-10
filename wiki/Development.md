# Development

This page covers development setup, architecture guidelines, coding standards, and how to contribute to Vociferous.

## Getting Started with Development

### Prerequisites

- Python 3.11 or later
- Git
- ffmpeg
- Familiarity with Python type hints and dataclasses

### Development Setup

1. **Clone the repository**:
```bash
git clone https://github.com/WanderingAstronomer/Vociferous.git
cd Vociferous
```

2. **Install with development extras**:
```bash
pip install -e .[dev]
```

This installs:
- pytest for testing
- mypy for type checking
- All runtime dependencies

3. **Verify installation**:
```bash
# Run tests
pytest

# Run type checker
mypy vociferous/

# Check vociferous works
vociferous check
```

## Project Structure

```
Vociferous/
├── vociferous/           # Main package
│   ├── domain/          # Domain models and protocols (dependency-free)
│   ├── engines/         # ASR engine adapters (Whisper, Voxtral)
│   ├── audio/           # Audio I/O, VAD (sounddevice, ffmpeg)
│   ├── sources/         # Audio sources (file, microphone, memory)
│   ├── storage/         # File I/O, history, config
│   ├── app/             # Application orchestration, use cases
│   ├── cli/             # CLI commands and sinks
│   ├── gui/             # KivyMD graphical interface
│   └── polish/          # Grammar/fluency polishing (optional)
├── tests/               # Test suite
├── Planning and Documentation/  # Architecture and specs
├── wiki/                # Wiki pages (this documentation)
├── pyproject.toml       # Package configuration
└── README.md            # Quick start guide
```

## Architecture Principles

Vociferous follows a **ports-and-adapters** (hexagonal) architecture with strict dependency rules.

### Layer Diagram

```
UI (CLI/TUI/GUI)
    ↓
Application (Use Cases, TranscriptionSession)
    ↓
Domain (Models, Protocols)
    ↓
Adapters/Infrastructure (Engines, Audio, Storage)
```

### Dependency Rules

1. **Domain Layer** (`domain/`):
   - Pure Python, stdlib only
   - No external dependencies
   - Defines protocols (interfaces) for adapters
   - Contains typed dataclasses for core entities

2. **Adapters Layer** (`engines/`, `audio/`, `storage/`):
   - Implements domain protocols
   - Can depend on: domain + specific runtime (e.g., faster-whisper)
   - Cannot depend on: other adapters, UI, application layer

3. **Application Layer** (`app/`):
   - Orchestrates use cases
   - Depends on: domain + adapters (via protocols)
   - Cannot depend on: UI specifics

4. **UI Layer** (`cli/`, `gui/`):
   - Entry points for users
   - Depends on: application layer + config
   - Cannot depend on: domain or adapters directly

**Forbidden**:
- UI importing domain/adapters directly
- Adapters importing other adapters
- Circular dependencies between any modules

### Key Design Patterns

**Protocols over Interfaces**: Use Python protocols (structural typing) for adapter contracts:

```python
# domain/protocols.py
from typing import Protocol, Iterator

class TranscriptionEngine(Protocol):
    def start(self, language: str) -> None: ...
    def push_audio(self, chunk: AudioChunk) -> None: ...
    def flush(self) -> None: ...
    def poll_segments(self) -> Iterator[TranscriptSegment]: ...
```

**Frozen Dataclasses**: Domain models are immutable:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class AudioChunk:
    data: bytes
    sample_rate: int
    timestamp: float
```

**Push-Based Streaming**: Engines are stateful and push-based:

```python
# start → push → flush → poll
session.start(language="en")
session.push_audio(chunk1)
session.push_audio(chunk2)
session.flush()
segments = list(session.poll_segments())
```

## Coding Standards

### Type Hints

**Strict typing is enforced** via mypy:

```python
# Good: Fully typed
def transcribe_file(path: Path, engine: TranscriptionEngine) -> TranscriptSegment:
    ...

# Bad: Missing type hints
def transcribe_file(path, engine):
    ...
```

Run type checker:
```bash
mypy vociferous/
```

### Dataclasses

Use frozen dataclasses for domain models:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class TranscriptSegment:
    text: str
    start: float
    end: float
    language: str
```

### Error Handling

Use typed exceptions for domain errors:

```python
# domain/errors.py
class VociferousError(Exception):
    """Base exception for Vociferous."""
    pass

class AudioDecodingError(VociferousError):
    """Audio could not be decoded."""
    pass

class ModelLoadError(VociferousError):
    """Engine model could not be loaded."""
    pass
```

Handle errors gracefully in application layer:

```python
try:
    segments = transcribe_file(path, engine)
except AudioDecodingError as e:
    logger.error(f"Failed to decode audio: {e}")
    return None
```

### Logging

Use structured logging with `structlog`:

```python
import structlog

logger = structlog.get_logger()

def transcribe(path: Path) -> None:
    logger.info("transcription_started", path=str(path))
    try:
        ...
        logger.info("transcription_completed", duration=elapsed)
    except Exception as e:
        logger.error("transcription_failed", error=str(e))
```

### Code Style

- **Line length**: 120 characters max
- **Imports**: Organized (stdlib, third-party, local)
- **Naming**: 
  - Functions/variables: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
  - Private: `_leading_underscore`

Example:

```python
# Good
class TranscriptionEngine:
    def __init__(self, model_path: Path) -> None:
        self._model_path = model_path
        self.is_ready = False

    def start(self) -> None:
        ...

# Bad
class transcriptionEngine:
    def __init__(self, ModelPath):
        self.ModelPath = ModelPath
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_vad_wrapper_basic.py

# Run with coverage
pytest --cov=vociferous --cov-report=html

# Run with verbose output
pytest -v
```

### Writing Tests

Tests are located in `tests/` directory:

```python
# tests/test_my_feature.py
import pytest
from vociferous.domain.models import AudioChunk

def test_audio_chunk_creation():
    chunk = AudioChunk(
        data=b'\x00\x01',
        sample_rate=16000,
        timestamp=0.0
    )
    assert chunk.sample_rate == 16000
    assert len(chunk.data) == 2

def test_invalid_audio_chunk():
    with pytest.raises(ValueError):
        AudioChunk(data=b'', sample_rate=-1, timestamp=0.0)
```

### Test Guidelines

1. **Test domain logic extensively**: Pure functions, no I/O
2. **Mock adapters in application tests**: Don't hit real engines
3. **Integration tests for adapters**: Test with real dependencies
4. **Prefer pytest fixtures for setup**: Reusable test data

Example fixture:

```python
@pytest.fixture
def sample_audio_chunk() -> AudioChunk:
    return AudioChunk(
        data=b'\x00\x01\x02\x03',
        sample_rate=16000,
        timestamp=0.0
    )

def test_with_fixture(sample_audio_chunk: AudioChunk):
    assert sample_audio_chunk.sample_rate == 16000
```

## Contributing

### Workflow

1. **Fork the repository** on GitHub
2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/Vociferous.git
   ```
3. **Create a feature branch**:
   ```bash
   git checkout -b feature/my-new-feature
   ```
4. **Make your changes** following coding standards
5. **Run tests and type checker**:
   ```bash
   pytest
   mypy vociferous/
   ```
6. **Commit with clear messages**:
   ```bash
   git commit -m "Add feature: support for new audio format"
   ```
7. **Push to your fork**:
   ```bash
   git push origin feature/my-new-feature
   ```
8. **Open a Pull Request** on GitHub

### Pull Request Guidelines

- **Clear description**: Explain what and why
- **Tests included**: Add tests for new features
- **Type hints**: All new code must be typed
- **Documentation**: Update relevant docs if needed
- **Small PRs**: Prefer focused changes over large rewrites

### Commit Message Format

```
<type>: <short summary>

<optional longer description>

<optional footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code restructuring
- `test`: Test additions/changes
- `chore`: Build/tooling changes

**Examples**:
```
feat: add Voxtral engine support

Implements VoxtralEngine adapter using mistral-common for audio
transcription with enhanced punctuation.

Closes #42
```

```
fix: handle empty audio chunks in VAD

Previously crashed on zero-length audio. Now returns empty segments.
```

## Module Development Guide

### Adding a New Engine

1. **Define protocol** (if not exists):
```python
# vociferous/domain/protocols.py
class TranscriptionEngine(Protocol):
    def start(self, language: str) -> None: ...
    def push_audio(self, chunk: AudioChunk) -> None: ...
    def flush(self) -> None: ...
    def poll_segments(self) -> Iterator[TranscriptSegment]: ...
```

2. **Implement adapter**:
```python
# vociferous/engines/my_engine.py
from vociferous.domain.protocols import TranscriptionEngine
from vociferous.domain.models import AudioChunk, TranscriptSegment

class MyEngine:
    def start(self, language: str) -> None:
        # Initialize engine
        pass

    def push_audio(self, chunk: AudioChunk) -> None:
        # Process audio chunk
        pass

    def flush(self) -> None:
        # Finalize processing
        pass

    def poll_segments(self) -> Iterator[TranscriptSegment]:
        # Yield transcription segments
        yield TranscriptSegment(...)
```

3. **Register in factory**:
```python
# vociferous/engines/factory.py
def create_engine(engine_name: str) -> TranscriptionEngine:
    if engine_name == "my_engine":
        return MyEngine()
    ...
```

4. **Add tests**:
```python
# tests/test_my_engine.py
def test_my_engine_basic():
    engine = MyEngine()
    engine.start("en")
    chunk = AudioChunk(...)
    engine.push_audio(chunk)
    engine.flush()
    segments = list(engine.poll_segments())
    assert len(segments) > 0
```

### Adding a New CLI Command

1. **Create command module**:
```python
# vociferous/cli/commands/my_command.py
import typer

app = typer.Typer()

@app.command()
def my_command(
    input_file: str = typer.Argument(..., help="Input file"),
    option: bool = typer.Option(False, help="Some option")
) -> None:
    """My new command description."""
    # Command logic
    typer.echo(f"Processing {input_file}")
```

2. **Register in main CLI**:
```python
# vociferous/cli/main.py
from vociferous.cli.commands import my_command

app = typer.Typer()
app.add_typer(my_command.app, name="mycommand")
```

3. **Add tests**:
```python
# tests/test_cli_my_command.py
from typer.testing import CliRunner
from vociferous.cli.main import app

runner = CliRunner()

def test_my_command():
    result = runner.invoke(app, ["mycommand", "test.wav"])
    assert result.exit_code == 0
```

## Debugging

### Debug Mode

Enable verbose logging:

```bash
export VOCIFEROUS_LOG_LEVEL=DEBUG
vociferous transcribe file.wav
```

### Interactive Debugging

Use Python debugger:

```python
# Add to code
import pdb; pdb.set_trace()
```

Run with debugger:

```bash
python -m pdb -c continue $(which vociferous) transcribe file.wav
```

### Debug Scripts

Several debug scripts are included:

- `debug_audio.py`: Test audio decoding
- `debug_vad_timestamps.py`: Test VAD detection
- `debug_vad_wrapper.py`: Test VAD wrapper

Example:

```bash
python debug_audio.py path/to/audio.wav
```

## Documentation

### Updating Wiki

Wiki pages are in `wiki/` directory:

1. Edit markdown files
2. Follow existing structure
3. Include code examples
4. Test links between pages

### Docstrings

Use Google-style docstrings:

```python
def transcribe(path: Path, language: str = "en") -> list[TranscriptSegment]:
    """Transcribe audio file to text.

    Args:
        path: Path to audio file
        language: ISO 639-1 language code (default: "en")

    Returns:
        List of transcription segments with timestamps

    Raises:
        AudioDecodingError: If audio cannot be decoded
        ModelLoadError: If engine fails to load
    """
    ...
```

## Resources

### Internal Documentation

- `Planning and Documentation/`: Architecture specs and design docs
  - `Architecture and Module Design.md`: System architecture
  - `Product Design & Requirements.md`: Requirements and use cases
  - `Interface Contracts.md`: Protocol definitions

### External Resources

- **faster-whisper**: [github.com/guillaumekln/faster-whisper](https://github.com/guillaumekln/faster-whisper)
- **OpenAI Whisper**: [github.com/openai/whisper](https://github.com/openai/whisper)
- **Silero VAD**: [github.com/snakers4/silero-vad](https://github.com/snakers4/silero-vad)

## Getting Help

- **Issues**: GitHub Issues for bug reports and feature requests
- **Discussions**: GitHub Discussions for questions and ideas
- **Email**: Maintainer contact in repository

## Next Steps

- **[How It Works](How-It-Works.md)**: Understand the architecture
- **[Configuration](Configuration.md)**: Configuration deep dive
- **[Getting Started](Getting-Started.md)**: User guide
