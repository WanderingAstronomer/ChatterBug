# History Storage

Transcription history is persisted using JSONL (JSON Lines) format.

## File Location

```
~/.config/vociferous/history.jsonl
```

Created automatically on first transcription.

## Format

Each line is a complete JSON object:

```json
{"timestamp":"2025-01-15T10:30:45.123456","text":"Hello world","duration_ms":2500}
{"timestamp":"2025-01-15T10:31:12.654321","text":"Another transcription","duration_ms":1800}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | ISO-8601 format with microseconds |
| `text` | string | Transcribed text |
| `duration_ms` | int | Recording duration in milliseconds |

## Why JSONL?

- **Append-only**: New entries added without reading entire file
- **Thread-safe**: Single-line writes are atomic on most filesystems
- **Human-readable**: Easy to inspect and edit manually
- **Streamable**: Can process line by line without loading all into memory
- **Export-friendly**: Simple to convert to CSV, markdown, etc.

## Operations

### Add Entry

```python
entry = HistoryEntry(
    timestamp=datetime.now().isoformat(),
    text="Transcribed text",
    duration_ms=2500
)

with open(history_file, 'a') as f:
    f.write(entry.to_json() + '\n')
```

### Read Recent

```python
with open(history_file) as f:
    lines = f.readlines()

entries = [HistoryEntry.from_json(line) for line in lines[-100:]]
entries.reverse()  # Newest first
```

### Update Entry

Requires rewriting the entire file (infrequent operation):

```python
entries = []
for line in open(history_file):
    entry = HistoryEntry.from_json(line)
    if entry.timestamp == target_timestamp:
        entry.text = new_text
    entries.append(entry)

with open(history_file, 'w') as f:
    for entry in entries:
        f.write(entry.to_json() + '\n')
```

### Delete Entry

Similar to update - filter out the target entry and rewrite.

## Rotation

When entries exceed `max_history_entries` (default 1000), oldest entries are removed:

```python
if len(lines) > max_entries:
    with open(history_file, 'w') as f:
        f.writelines(lines[-max_entries:])
```

Rotation happens automatically after each write.

## Export Formats

### Plain Text (.txt)
```
[2025-01-15T10:30:45]
Hello world

[2025-01-15T10:31:12]
Another transcription
```

### CSV
```csv
Timestamp,Text,Duration (ms)
2025-01-15T10:30:45,Hello world,2500
2025-01-15T10:31:12,Another transcription,1800
```

### Markdown
```markdown
# Vociferous Transcription History

## January 15th, 2025

### 10:30 a.m.

Hello world

*Duration: 2500ms*

---
```

## Configuration

```yaml
output_options:
  max_history_entries: 1000  # 0 = unlimited
```

## HistoryEntry Dataclass

```python
@dataclass(slots=True)
class HistoryEntry:
    timestamp: str      # ISO-8601
    text: str
    duration_ms: int = 0
    
    def to_json(self) -> str: ...
    
    @classmethod
    def from_json(cls, json_str: str) -> 'HistoryEntry': ...
```

Uses `slots=True` for memory efficiency with many entries.
