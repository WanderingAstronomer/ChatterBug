"""
Transcription history display widget.

Displays scrollable list of past transcriptions with day grouping.
Single-click loads into editor, double-click copies to clipboard.
"""
import subprocess
from contextlib import suppress
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QRect, QSize
from PyQt5.QtCore import QFileSystemWatcher
from PyQt5.QtGui import QBrush, QColor, QFont, QPen, QKeySequence
from PyQt5.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QMenu,
    QShortcut,
    QStyledItemDelegate,
    QStyle,
)

from history_manager import HistoryEntry, HistoryManager

# Optional clipboard support
try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False


class HistoryDelegate(QStyledItemDelegate):
    """Delegate for rendering history entries with blue timestamp and wrapped text."""

    def __init__(self, time_role, parent=None) -> None:
        super().__init__(parent)
        self.time_role = time_role

    def paint(self, painter, option, index) -> None:
        """Paint timestamp and preview with proper colors and wrapping."""
        # Headers use default rendering
        if index.data(HistoryWidget.ROLE_IS_HEADER):
            super().paint(painter, option, index)
            return
        
        painter.save()
        
        # Draw background color based on state (no text)
        rect = option.rect
        if option.state & QStyle.State_Selected:
            painter.fillRect(rect, option.palette.highlight())
        elif option.state & QStyle.State_MouseOver:
            # Hover color from stylesheet will be applied by the item itself
            pass
        
        time_str = index.data(self.time_role) or ""
        preview = index.data(Qt.DisplayRole) or ""
        
        fm = painter.fontMetrics()
        
        # Margins
        margin_left = 12
        margin_top = 8
        spacing = 12
        
        # Calculate timestamp width (fixed for alignment)
        time_width = fm.horizontalAdvance("12:59 p.m.") + spacing
        
        # Draw timestamp (blue, bold)
        painter.setPen(QPen(QColor("#5a9fd4")))
        font = painter.font()
        font.setWeight(QFont.Bold)
        painter.setFont(font)
        
        painter.drawText(
            rect.x() + margin_left,
            rect.y() + fm.ascent() + margin_top,
            time_str
        )
        
        # Draw preview text (normal weight, wrapped)
        font.setWeight(QFont.Normal)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#d4d4d4")))
        
        text_rect = QRect(
            rect.x() + margin_left + time_width,
            rect.y() + margin_top,
            rect.width() - margin_left - time_width - margin_left,
            rect.height() - margin_top - margin_top
        )
        
        painter.drawText(text_rect, Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, preview)
        
        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        """Calculate proper height for wrapped text."""
        # Headers use default size
        if index.data(HistoryWidget.ROLE_IS_HEADER):
            return super().sizeHint(option, index)
        
        preview = index.data(Qt.DisplayRole) or ""
        fm = option.fontMetrics
        
        margin_left = 12
        margin_top = 8
        spacing = 12
        
        # Fixed timestamp width
        time_width = fm.horizontalAdvance("12:59 p.m.") + spacing
        
        # Available width for text
        text_width = option.rect.width() - margin_left - time_width - margin_left
        if text_width < 50:
            text_width = 200  # Fallback for initial layout
        
        # Calculate wrapped text height
        text_rect = fm.boundingRect(
            0, 0, text_width, 10000,
            Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop,
            preview
        )
        
        height = text_rect.height() + margin_top * 2
        min_height = fm.height() + margin_top * 2
        
        return QSize(option.rect.width(), max(height, min_height))


class HistoryWidget(QListWidget):
    """
    Display transcription history with context menu.

    Day headers are collapsible (click to toggle).
    Single-click loads entry into editor, double-click copies.
    """

    entrySelected = pyqtSignal(str, str)
    historyCountChanged = pyqtSignal(int)

    # Custom data roles
    ROLE_DAY_KEY = Qt.UserRole + 1  # Store day key on headers and entries
    ROLE_IS_HEADER = Qt.UserRole + 2  # True if item is a day header
    ROLE_TIME = Qt.UserRole + 3  # Store formatted timestamp string
    ROLE_TIMESTAMP_ISO = Qt.UserRole + 4  # Store ISO timestamp

    def __init__(self, history_manager: HistoryManager | None = None, parent=None) -> None:
        super().__init__(parent)

        self.history_manager = history_manager
        self._file_watcher = QFileSystemWatcher(self)
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._reload_from_file)

        # Track collapsed day groups
        self._collapsed_days: set[str] = set()

        # Set custom delegate for rendering
        self.setItemDelegate(HistoryDelegate(self.ROLE_TIME, self))

        # Adjust item sizes to current width without user interaction
        self.setSizeAdjustPolicy(QListWidget.AdjustToContents)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setResizeMode(QListWidget.Adjust)
        self.setFocusPolicy(Qt.StrongFocus)

        # Keyboard shortcut for deletion even if focus momentarily leaves the list
        delete_shortcut = QShortcut(QKeySequence.Delete, self)
        delete_shortcut.setContext(Qt.ApplicationShortcut)
        delete_shortcut.activated.connect(self._delete_current)

        # Enable custom context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Double-click to copy (but not on headers)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)

        # Single click: header toggles collapse; entry loads into editor
        self.itemClicked.connect(self._on_item_clicked)

        # Set accessible name
        self.setAccessibleName("Transcription History")
        self.setAccessibleDescription(
            "List of recent transcriptions. Double-click to copy, right-click for options. Click day headers to collapse/expand."
        )

        self._init_file_watch()
        self._emit_count_changed()

    def add_entry(self, entry: HistoryEntry) -> None:
        """Add a single history entry, inserting a day header if needed."""
        dt = datetime.fromisoformat(entry.timestamp)
        day_key = dt.date().isoformat()

        # Determine insert position: after the header for this day
        insert_pos = 0
        has_header = self._has_header_for_day_at_top(day_key)

        if not has_header:
            # Create new header at top (no triangle indicator)
            header_item = QListWidgetItem(self._format_day_header(dt))
            header_item.setFlags(Qt.ItemIsEnabled)  # non-selectable header
            header_item.setTextAlignment(Qt.AlignCenter)
            header_item.setData(self.ROLE_DAY_KEY, day_key)
            header_item.setData(self.ROLE_IS_HEADER, True)
            # No tooltip needed; click toggles collapse
            self._style_header_item(header_item, is_collapsed=False)
            self.insertItem(0, header_item)
            insert_pos = 1  # Insert entry right after new header
        else:
            insert_pos = 1  # Insert entry right after existing header

        # Create entry item (delegate will handle rendering)
        timestamp_str = self._format_timestamp(entry)
        preview_text = entry.text.strip()
        if len(preview_text) > 100:
            preview_text = preview_text[:100] + "…"
        
        item = QListWidgetItem()
        item.setData(Qt.DisplayRole, preview_text)
        item.setData(self.ROLE_TIME, timestamp_str)
        item.setData(self.ROLE_TIMESTAMP_ISO, entry.timestamp)
        item.setData(Qt.UserRole, entry.text)
        item.setData(self.ROLE_DAY_KEY, day_key)
        item.setData(self.ROLE_IS_HEADER, False)
        # No tooltip – single-click loads text for editing
        
        self.insertItem(insert_pos, item)

        # If this day is collapsed, hide the new entry
        if day_key in self._collapsed_days:
            item.setHidden(True)

        self._refresh_layout()
        self._emit_count_changed()

    def load_history(self, history_manager: HistoryManager | None = None) -> None:
        """Load recent history entries grouped by day with headers."""
        if history_manager:
            self.history_manager = history_manager

        # Ensure watcher tracks the current file
        self._reset_file_watch()

        if not self.history_manager:
            return

        self.clear()
        self._collapsed_days.clear()
        entries = self.history_manager.get_recent(limit=100)

        # Get today's date for auto-collapse logic
        today_key = datetime.now().date().isoformat()

        current_day: str | None = None
        for entry in entries:
            dt = datetime.fromisoformat(entry.timestamp)
            day_key = dt.date().isoformat()
            if current_day != day_key:
                current_day = day_key
                
                # Auto-collapse all days except today
                is_today = (day_key == today_key)
                if not is_today:
                    self._collapsed_days.add(day_key)
                
                header_item = QListWidgetItem(self._format_day_header(dt))
                header_item.setFlags(Qt.ItemIsEnabled)
                header_item.setTextAlignment(Qt.AlignCenter)
                header_item.setData(self.ROLE_DAY_KEY, day_key)
                header_item.setData(self.ROLE_IS_HEADER, True)
                # No tooltip for headers
                self._style_header_item(header_item, is_collapsed=not is_today)
                self.addItem(header_item)

            # Create entry item (delegate will handle rendering)
            timestamp_str = self._format_timestamp(entry)
            preview_text = entry.text.strip()
            if len(preview_text) > 100:
                preview_text = preview_text[:100] + "…"
            
            item = QListWidgetItem()
            item.setData(Qt.DisplayRole, preview_text)
            item.setData(self.ROLE_TIME, timestamp_str)
            item.setData(self.ROLE_TIMESTAMP_ISO, entry.timestamp)
            item.setData(Qt.UserRole, entry.text)
            item.setData(self.ROLE_DAY_KEY, day_key)
            item.setData(self.ROLE_IS_HEADER, False)
            # No tooltip – single-click loads text for editing
            
            # Hide if day is collapsed
            if day_key in self._collapsed_days:
                item.setHidden(True)
            
            self.addItem(item)

        self._refresh_layout()
        self._emit_count_changed()

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle single click: header toggles collapse, entry selects for edit."""
        if item.data(self.ROLE_IS_HEADER):
            day_key = item.data(self.ROLE_DAY_KEY)
            self._toggle_day_collapse(day_key, item)
            return

        # Entry: emit text + ISO timestamp for edit pane
        full_text = item.data(Qt.UserRole)
        ts_iso = item.data(self.ROLE_TIMESTAMP_ISO) or ""
        self.entrySelected.emit(full_text, ts_iso)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double click - copy if it's an entry (not a header)."""
        if not item.data(self.ROLE_IS_HEADER):
            self._copy_item(item)

    def _toggle_day_collapse(self, day_key: str, header_item: QListWidgetItem) -> None:
        """Toggle visibility of all entries under a day header."""
        is_collapsed = day_key in self._collapsed_days

        if is_collapsed:
            # Expand: show all entries for this day
            self._collapsed_days.discard(day_key)
            self._style_header_item(header_item, is_collapsed=False)
        else:
            # Collapse: hide all entries for this day
            self._collapsed_days.add(day_key)
            self._style_header_item(header_item, is_collapsed=True)

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

        # No reinject action; single-click loads text for editing
        menu.addSeparator()

        delete_action = menu.addAction("Delete Entry")
        delete_action.triggered.connect(lambda: self._delete_item(item))

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
                # Delete key → remove item (with persistence)
                if current_item:
                    self._delete_item(current_item)
                    event.accept()
                    return

            case _:
                super().keyPressEvent(event)

    def _delete_current(self) -> None:
        """Delete the currently selected item (shortcut helper)."""
        item = self.currentItem()
        if item and not item.data(self.ROLE_IS_HEADER):
            self._delete_item(item)

    def _delete_item(self, item: QListWidgetItem) -> None:
        """Remove an entry from the list and persistent storage."""
        if item.data(self.ROLE_IS_HEADER):
            return

        ts_iso = item.data(self.ROLE_TIMESTAMP_ISO)
        day_key = item.data(self.ROLE_DAY_KEY)
        current_row = self.row(item)

        # Remove from UI
        self.takeItem(self.row(item))

        # Persist deletion
        if self.history_manager and ts_iso:
            self.history_manager.delete_entry(ts_iso)

        # Remove header if no more entries under that day
        self._remove_header_if_empty(day_key)

        # Select a sensible fallback item (previous entry preferred)
        self._select_fallback_after_delete(current_row)
        self._emit_count_changed()

    def _remove_header_if_empty(self, day_key: str | None) -> None:
        """Delete the day header if it has no remaining entries."""
        if not day_key:
            return

        # Check for any remaining entries in the same day
        has_entries = False
        header_row = None
        for i in range(self.count()):
            item = self.item(i)
            if item.data(self.ROLE_DAY_KEY) != day_key:
                continue
            if item.data(self.ROLE_IS_HEADER):
                header_row = i
            else:
                has_entries = True
                break

        if not has_entries and header_row is not None:
            self.takeItem(header_row)

    def _select_fallback_after_delete(self, deleted_row: int) -> None:
        """After deletion, select the nearest entry and emit selection, or clear."""
        # Prefer previous items above the deleted row
        for i in range(deleted_row - 1, -1, -1):
            candidate = self.item(i)
            if candidate and not candidate.data(self.ROLE_IS_HEADER):
                self.setCurrentItem(candidate)
                self._emit_entry_selected(candidate)
                return

        # Fall back to the next items below
        for i in range(deleted_row, self.count()):
            candidate = self.item(i)
            if candidate and not candidate.data(self.ROLE_IS_HEADER):
                self.setCurrentItem(candidate)
                self._emit_entry_selected(candidate)
                return

        # No entries left - signal clear
        self.entrySelected.emit("", "")

    def entry_count(self) -> int:
        """Return number of non-header history entries."""
        count = 0
        for i in range(self.count()):
            item = self.item(i)
            if item and not item.data(self.ROLE_IS_HEADER):
                count += 1
        return count

    def _emit_count_changed(self) -> None:
        self.historyCountChanged.emit(self.entry_count())

    def _emit_entry_selected(self, item: QListWidgetItem) -> None:
        """Emit entrySelected for the given item."""
        full_text = item.data(Qt.UserRole)
        ts_iso = item.data(self.ROLE_TIMESTAMP_ISO) or ""
        self.entrySelected.emit(full_text, ts_iso)

    def _refresh_layout(self) -> None:
        """Force item relayout to respect current viewport width."""
        self.doItemsLayout()
        self.updateGeometries()
        if self.viewport():
            self.viewport().update()

    def _init_file_watch(self) -> None:
        """Start watching the history file for external changes."""
        self._reset_file_watch()

    def _reset_file_watch(self) -> None:
        """Reset watcher to follow the current history file path."""
        if not self.history_manager:
            return

        path = getattr(self.history_manager, "history_file", None)
        if not path:
            return

        # Ensure file exists so watcher can attach
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
        except Exception:
            return

        with suppress(TypeError):
            self._file_watcher.fileChanged.disconnect(self._on_history_file_changed)

        self._file_watcher.removePaths(self._file_watcher.files())
        self._file_watcher.addPath(str(path))
        self._file_watcher.fileChanged.connect(self._on_history_file_changed)

    def _on_history_file_changed(self, _) -> None:
        """Debounce reload when the history file changes on disk."""
        self._debounce_timer.start(200)

    def _reload_from_file(self) -> None:
        """Reload history after an external file change."""
        # Reattach watcher in case the file was recreated
        self._reset_file_watch()
        self.load_history()

    # ---------- Helpers ----------

    def _style_header_item(self, item: QListWidgetItem, is_collapsed: bool) -> None:
        """Apply distinctive styling to day header items."""
        # Bold font for headers
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        item.setFont(font)
        
        # Gray when collapsed, white when expanded
        if is_collapsed:
            item.setForeground(QBrush(QColor("#888888")))
        else:
            item.setForeground(QBrush(QColor("#ffffff")))
        
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

    def _format_timestamp(self, entry: HistoryEntry) -> str:
        """Extract and format just the timestamp portion."""
        dt = datetime.fromisoformat(entry.timestamp)
        time_str = dt.strftime("%I:%M %p")
        time_str = time_str.replace("AM", "a.m.").replace("PM", "p.m.")
        if time_str.startswith("0"):
            time_str = time_str[1:]
        return time_str

    def _format_entry_text(self, entry: HistoryEntry, max_length: int = 80) -> str:
        """Format a single entry line with blue timestamp using HTML."""
        dt = datetime.fromisoformat(entry.timestamp)
        time_str = dt.strftime("%I:%M %p")  # e.g., 10:03 PM
        # Lowercase: p.m. / a.m.
        time_str = time_str.replace("AM", "a.m.").replace("PM", "p.m.")
        # Remove leading zero in hour
        if time_str.startswith("0"):
            time_str = time_str[1:]

        text = entry.text.strip()
        if len(text) > max_length:
            text = text[:max_length] + "…"

        # Return HTML with styled timestamp
        return (
            f"<span style='color:#5a9fd4; font-weight:600;'>{time_str}</span>"
            f"&nbsp;&nbsp;"
            f"<span style='color:#d4d4d4;'>{text}</span>"
        )

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
