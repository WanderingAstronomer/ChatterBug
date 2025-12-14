"""
Transcription history management with JSONL storage.

This module provides persistent storage for transcription history using
JSON Lines format. Each transcription is stored as a single JSON object
per line, enabling efficient append operations and easy human inspection.

Storage Format:
---------------
File: ~/.config/vociferous/history.jsonl

Each line:
    {"timestamp": "2025-12-14T15:30:45.123456", "text": "...", "duration_ms": 1234}

Why JSONL?
----------
- **Append-only**: Thread-safe writes without locking entire file
- **Human-readable**: Users can inspect/edit with any text editor
- **Streaming**: Can read large files line-by-line without loading all
- **Upgrade path**: Easy migration to SQLite if search is needed later

Performance Characteristics:
----------------------------
- 1000 entries: ~150KB, ~20ms read (acceptable)
- 10000 entries: ~1.5MB, ~200ms read (noticeable)
- Rotation keeps file size bounded

Python 3.12+ Features:
----------------------
- Dataclass with slots for memory efficiency
- Match/case for export format selection
- Pathlib throughout
"""
import csv
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from utils import ConfigManager

logger = logging.getLogger(__name__)

# History file location
HISTORY_DIR = Path.home() / '.config' / 'vociferous'
HISTORY_FILE = HISTORY_DIR / 'history.jsonl'


@dataclass(slots=True)
class HistoryEntry:
    """
    Single transcription history entry.

    Designed for future SQLite compatibility:
    - All fields map directly to SQL columns
    - timestamp is ISO8601 (sortable string)
    - duration_ms is integer (efficient storage)

    Attributes:
        timestamp: ISO8601 format string
        text: The transcribed text
        duration_ms: Recording duration in milliseconds
    """
    timestamp: str
    text: str
    duration_ms: int

    @classmethod
    def from_json(cls, json_str: str) -> 'HistoryEntry':
        """Parse from JSON line."""
        data = json.loads(json_str)
        return cls(**data)

    def to_json(self) -> str:
        """Serialize to JSON line."""
        return json.dumps(asdict(self), ensure_ascii=False)

    def to_display_string(self, max_length: int = 80) -> str:
        """
        Format for display in list widget.

        Shows timestamp (HH:MM:SS) followed by truncated text preview.
        Full text available via tooltip or Qt.UserRole data.
        """
        timestamp_short = self.timestamp.split('T')[1][:8]  # HH:MM:SS
        if len(self.text) > max_length:
            text_preview = self.text[:max_length] + '...'
        else:
            text_preview = self.text
        return f"[{timestamp_short}] {text_preview}"


class HistoryManager:
    """
    Manages transcription history with JSONL storage.

    Design Goals:
    -------------
    - Simple append-only writes (thread-safe)
    - Efficient for < 1000 entries
    - Easy to upgrade to SQLite later
    - Export-friendly format

    Thread Safety:
    --------------
    Append operations are atomic on most filesystems. The file is opened
    in append mode, written, and closed in a single operation. This makes
    concurrent writes from multiple threads safe without explicit locking.

    Rotation:
    ---------
    When entries exceed max_history_entries (default 1000), oldest entries
    are removed to keep file size bounded. This happens after each write
    to prevent unbounded growth.
    """

    def __init__(self, history_file: Path | None = None) -> None:
        """Initialize history manager with optional custom file path."""
        self.history_file = history_file or HISTORY_FILE
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        # Create file if doesn't exist
        if not self.history_file.exists():
            self.history_file.touch()

    def add_entry(self, text: str, duration_ms: int = 0) -> HistoryEntry:
        """
        Add new transcription to history.

        Thread-safe: Append operation is atomic on most filesystems.

        Args:
            text: Transcribed text
            duration_ms: Recording duration in milliseconds

        Returns:
            Created HistoryEntry
        """
        entry = HistoryEntry(
            timestamp=datetime.now().isoformat(),
            text=text,
            duration_ms=duration_ms
        )

        try:
            with open(self.history_file, 'a', encoding='utf-8') as f:
                f.write(entry.to_json() + '\n')
        except OSError as e:
            logger.error(f"Failed to write history entry: {e}")

        # Check if rotation needed
        max_entries = ConfigManager.get_config_value(
            'output_options', 'max_history_entries'
        ) or 1000
        if max_entries > 0:
            self._rotate_if_needed(max_entries)

        return entry

    def get_recent(self, limit: int = 100) -> list[HistoryEntry]:
        """
        Get most recent entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of HistoryEntry, newest first
        """
        entries = []

        try:
            with open(self.history_file, encoding='utf-8') as f:
                lines = f.readlines()

            # Parse last N lines (newest at end of file)
            for line in lines[-limit:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = HistoryEntry.from_json(line)
                    entries.append(entry)
                except json.JSONDecodeError:
                    logger.warning(f"Skipping invalid history line: {line[:50]}")

            # Reverse to show newest first
            entries.reverse()

        except FileNotFoundError:
            pass  # No history yet
        except OSError as e:
            logger.error(f"Failed to read history: {e}")

        return entries

    def clear(self) -> None:
        """Clear all history (truncate file)."""
        try:
            self.history_file.unlink(missing_ok=True)
            self.history_file.touch()
            logger.info("History cleared")
        except OSError as e:
            logger.error(f"Failed to clear history: {e}")

    def export_to_file(self, export_path: Path, format: str = 'txt') -> bool:
        """
        Export history to file.

        Args:
            export_path: Destination file path
            format: Export format ('txt', 'csv', 'md')

        Returns:
            True if successful
        """
        entries = self.get_recent(limit=10000)  # Export all

        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                match format:
                    case 'txt':
                        for entry in entries:
                            f.write(f"[{entry.timestamp}]\n{entry.text}\n\n")

                    case 'csv':
                        writer = csv.writer(f)
                        writer.writerow(['Timestamp', 'Text', 'Duration (ms)'])
                        for entry in entries:
                            writer.writerow([
                                entry.timestamp,
                                entry.text,
                                entry.duration_ms
                            ])

                    case 'md':
                        f.write("# Vociferous Transcription History\n\n")
                        current_day = None
                        for entry in entries:
                            # Parse timestamp for grouping by day
                            dt = datetime.fromisoformat(entry.timestamp)
                            day_key = dt.date().isoformat()
                            
                            # New day header
                            if current_day != day_key:
                                current_day = day_key
                                # Format: "December 13th, 2025"
                                month = dt.strftime("%B")
                                day = dt.day
                                suffix = self._ordinal_suffix(day)
                                year = dt.year
                                f.write(f"## {month} {day}{suffix}, {year}\n\n")
                            
                            # Time header: "10:03 p.m."
                            time_str = dt.strftime("%I:%M %p")
                            time_str = time_str.replace("AM", "a.m.").replace("PM", "p.m.")
                            if time_str.startswith("0"):
                                time_str = time_str[1:]
                            f.write(f"### {time_str}\n\n")
                            
                            # Content
                            f.write(f"{entry.text}\n\n")
                            
                            # Duration as italicized note
                            if entry.duration_ms > 0:
                                f.write(f"*Duration: {entry.duration_ms}ms*\n\n")
                            
                            f.write("---\n\n")

                    case _:
                        logger.error(f"Unknown export format: {format}")
                        return False

            logger.info(f"Exported {len(entries)} entries to {export_path}")
            return True

        except OSError as e:
            logger.error(f"Export failed: {e}")
            return False

    def _rotate_if_needed(self, max_entries: int) -> None:
        """Remove oldest entries if exceeding limit."""
        try:
            with open(self.history_file, encoding='utf-8') as f:
                lines = f.readlines()

            if len(lines) > max_entries:
                # Keep only most recent entries
                with open(self.history_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines[-max_entries:])

                removed = len(lines) - max_entries
                logger.info(f"Rotated history: removed {removed} old entries")

        except OSError as e:
            logger.warning(f"History rotation failed: {e}")

    def _ordinal_suffix(self, n: int) -> str:
        """Return English ordinal suffix for a day (st/nd/rd/th)."""
        if 11 <= (n % 100) <= 13:
            return "th"
        match n % 10:
            case 1:
                return "st"
            case 2:
                return "nd"
            case 3:
                return "rd"
            case _:
                return "th"
