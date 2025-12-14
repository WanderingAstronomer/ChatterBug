"""
Transcription history display widget.

This widget displays a scrollable list of past transcriptions with:
- Timestamp + truncated preview for each entry
- Full text available via tooltip
- Double-click to copy to clipboard
- Right-click context menu: Copy, Re-inject, Delete

Display Format:
---------------
Each item shows: [HH:MM:SS] Preview text truncated to 80 chars...

The full text is stored in Qt.UserRole and displayed in tooltip.

Python 3.12+ Features:
----------------------
- Match/case for keyboard event handling
- Union type hints with |
"""
import subprocess
from contextlib import suppress
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont
from PyQt5.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QMenu,
)

from history_manager import HistoryEntry, HistoryManager

# Optional clipboard support
try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False


class HistoryWidget(QListWidget):
    """
    Display transcription history with context menu.

    Design:
    -------
    - Each item shows timestamp + truncated text
    - Full text stored in Qt.UserRole
    - Double-click to copy
    - Right-click for context menu
    - Day headers are collapsible (click to toggle)

    Signals:
        reinjectRequested: Emit text to re-inject into active window
    """

    reinjectRequested = pyqtSignal(str)

    # Custom data roles
    ROLE_DAY_KEY = Qt.UserRole + 1  # Store day key on headers and entries
    ROLE_IS_HEADER = Qt.UserRole + 2  # True if item is a day header

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Track collapsed day groups
        self._collapsed_days: set[str] = set()

        # Enable word wrap for long text
        self.setWordWrap(True)

        # Enable custom context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Double-click to copy (but not on headers)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)

        # Single click on header toggles collapse
        self.itemClicked.connect(self._on_item_clicked)

        # Set accessible name
        self.setAccessibleName("Transcription History")
        self.setAccessibleDescription(
            "List of recent transcriptions. Double-click to copy, right-click for options. Click day headers to collapse/expand."
        )

    def add_entry(self, entry: HistoryEntry) -> None:
        """Add a single history entry, inserting a day header if needed."""
        dt = datetime.fromisoformat(entry.timestamp)
        day_key = dt.date().isoformat()

        # Determine insert position: after the header for this day
        insert_pos = 0
        has_header = self._has_header_for_day_at_top(day_key)

        if not has_header:
            # Create new header at top with expand indicator
            header_item = QListWidgetItem("▼ " + self._format_day_header(dt))
            header_item.setFlags(Qt.ItemIsEnabled)  # non-selectable header
            header_item.setTextAlignment(Qt.AlignCenter)
            header_item.setData(self.ROLE_DAY_KEY, day_key)
            header_item.setData(self.ROLE_IS_HEADER, True)
            header_item.setToolTip("Click to collapse/expand this day")
            self._style_header_item(header_item)
            self.insertItem(0, header_item)
            insert_pos = 1  # Insert entry right after new header
        else:
            insert_pos = 1  # Insert entry right after existing header

        # Entry item with time + preview (indented for nesting visual)
        item = QListWidgetItem()
        item.setText("    " + self._format_entry_text(entry, max_length=75))
        item.setData(Qt.UserRole, entry.text)
        item.setData(self.ROLE_DAY_KEY, day_key)
        item.setData(self.ROLE_IS_HEADER, False)
        item.setToolTip(f"Full text:\n{entry.text}\n\nDuration: {entry.duration_ms}ms")
        self.insertItem(insert_pos, item)

        # If this day is collapsed, hide the new entry
        if day_key in self._collapsed_days:
            item.setHidden(True)

    def load_history(self, history_manager: HistoryManager) -> None:
        """Load recent history entries grouped by day with headers."""
        self.clear()
        self._collapsed_days.clear()
        entries = history_manager.get_recent(limit=100)

        current_day: str | None = None
        for entry in entries:
            dt = datetime.fromisoformat(entry.timestamp)
            day_key = dt.date().isoformat()
            if current_day != day_key:
                current_day = day_key
                header_item = QListWidgetItem("▼ " + self._format_day_header(dt))
                header_item.setFlags(Qt.ItemIsEnabled)
                header_item.setTextAlignment(Qt.AlignCenter)
                header_item.setData(self.ROLE_DAY_KEY, day_key)
                header_item.setData(self.ROLE_IS_HEADER, True)
                header_item.setToolTip("Click to collapse/expand this day")
                self._style_header_item(header_item)
                self.addItem(header_item)

            # Indent entries to show they're nested under the header
            item = QListWidgetItem("    " + self._format_entry_text(entry, max_length=75))
            item.setData(Qt.UserRole, entry.text)
            item.setData(self.ROLE_DAY_KEY, day_key)
            item.setData(self.ROLE_IS_HEADER, False)
            item.setToolTip(f"Full text:\n{entry.text}\n\nDuration: {entry.duration_ms}ms")
            self.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle single click - toggle collapse if clicking a header."""
        if item.data(self.ROLE_IS_HEADER):
            day_key = item.data(self.ROLE_DAY_KEY)
            self._toggle_day_collapse(day_key, item)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double click - copy if it's an entry (not a header)."""
        if not item.data(self.ROLE_IS_HEADER):
            self._copy_item(item)

    def _toggle_day_collapse(self, day_key: str, header_item: QListWidgetItem) -> None:
        """Toggle visibility of all entries under a day header."""
        is_collapsed = day_key in self._collapsed_days
        header_text = header_item.text()

        if is_collapsed:
            # Expand: show all entries for this day
            self._collapsed_days.discard(day_key)
            # Update header: ▶ → ▼
            if header_text.startswith("▶ "):
                header_item.setText("▼ " + header_text[2:])
        else:
            # Collapse: hide all entries for this day
            self._collapsed_days.add(day_key)
            # Update header: ▼ → ▶
            if header_text.startswith("▼ "):
                header_item.setText("▶ " + header_text[2:])

        # Update visibility of all items for this day
        for i in range(self.count()):
            item = self.item(i)
            item_day = item.data(self.ROLE_DAY_KEY)
            is_header = item.data(self.ROLE_IS_HEADER)
            if item_day == day_key and not is_header:
                item.setHidden(day_key in self._collapsed_days)

    def _copy_item(self, item: QListWidgetItem) -> None:
        """Copy item text to clipboard on double-click."""
        full_text = item.data(Qt.UserRole)
        self._copy_to_clipboard(full_text)

        # Visual feedback
        original_text = item.text()
        item.setText(f"✓ Copied: {original_text[:60]}...")
        QTimer.singleShot(1000, lambda: item.setText(original_text))

    def _show_context_menu(self, position) -> None:
        """Show context menu on right-click."""
        item = self.itemAt(position)
        if not item:
            return

        full_text = item.data(Qt.UserRole)

        menu = QMenu(self)

        copy_action = menu.addAction("Copy to Clipboard")
        copy_action.triggered.connect(lambda: self._copy_to_clipboard(full_text))

        reinject_action = menu.addAction("Re-inject Text")
        reinject_action.triggered.connect(lambda: self.reinjectRequested.emit(full_text))

        menu.addSeparator()

        delete_action = menu.addAction("Delete Entry")
        delete_action.triggered.connect(lambda: self.takeItem(self.row(item)))

        menu.exec_(self.mapToGlobal(position))

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard using available method."""
        if HAS_PYPERCLIP:
            with suppress(Exception):
                pyperclip.copy(text)
                return

        # Fallback to wl-copy (Wayland)
        with suppress(Exception):
            subprocess.run(["wl-copy"], input=text, text=True, check=True)

    def keyPressEvent(self, event) -> None:
        """Handle keyboard events for item actions."""
        current_item = self.currentItem()

        match event.key():
            case Qt.Key_Return | Qt.Key_Enter:
                # Enter on history item → copy
                if current_item:
                    self._copy_item(current_item)

            case Qt.Key_Delete:
                # Delete key → remove item
                if current_item:
                    self.takeItem(self.row(current_item))

            case _:
                super().keyPressEvent(event)

    # ---------- Helpers ----------

    def _style_header_item(self, item: QListWidgetItem) -> None:
        """Apply distinctive styling to day header items."""
        # Bold font for headers
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        item.setFont(font)
        # Blue accent color matching the theme
        item.setForeground(QBrush(QColor("#5a9fd4")))
        # Darker background to distinguish from entries
        item.setBackground(QBrush(QColor("#1a1a1a")))

    def _has_header_for_day_at_top(self, day_key: str) -> bool:
        """Check if the first item is a header for the given day."""
        if self.count() == 0:
            return False
        first_item = self.item(0)
        # Use the ROLE_IS_HEADER flag we set
        if not first_item.data(self.ROLE_IS_HEADER):
            return False
        # Compare day key directly
        return first_item.data(self.ROLE_DAY_KEY) == day_key

    def _format_day_header(self, dt: datetime) -> str:
        """Return a friendly day header like 'December 13th'."""
        month = dt.strftime("%B")
        day = dt.day
        suffix = self._ordinal_suffix(day)
        return f"{month} {day}{suffix}"

    def _format_entry_text(self, entry: HistoryEntry, max_length: int = 80) -> str:
        """Format a single entry line: '10:03 p.m. Preview...'."""
        dt = datetime.fromisoformat(entry.timestamp)
        time_str = dt.strftime("%I:%M %p")  # e.g., 10:03 PM
        # Lowercase with dots: 'p.m.' / 'a.m.'
        time_str = time_str.replace("AM", "a.m.").replace("PM", "p.m.")
        # Remove leading zero in hour
        if time_str.startswith("0"):
            time_str = time_str[1:]

        text = entry.text
        if len(text) > max_length:
            text = text[:max_length] + "..."

        return f"{time_str}  {text}"

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
