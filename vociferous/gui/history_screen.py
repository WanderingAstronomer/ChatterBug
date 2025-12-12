"""History browser screen for Vociferous GUI.

Provides:
- Local SQLite database for transcription history
- Search and filter functionality
- Re-export in different formats
- Metadata display (date, duration, engine used)
- Delete/archive functionality
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.list import (
    IconLeftWidget,
    ThreeLineIconListItem,
)
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.textfield import MDTextField

from .widgets import Colors, TooltipIconButton

logger = structlog.get_logger(__name__)

# Database location
DB_PATH = Path.home() / ".cache" / "vociferous" / "history.db"


@dataclass
class TranscriptionRecord:
    """A saved transcription record."""
    
    id: int
    filename: str
    file_path: str
    transcript: str
    engine: str
    language: str
    duration_seconds: float
    refined: bool
    created_at: datetime
    file_size_mb: float
    
    @property
    def created_formatted(self) -> str:
        """Format creation time as human-readable string."""
        now = datetime.now()
        delta = now - self.created_at
        
        if delta.days == 0:
            return f"Today at {self.created_at.strftime('%H:%M')}"
        elif delta.days == 1:
            return f"Yesterday at {self.created_at.strftime('%H:%M')}"
        elif delta.days < 7:
            return self.created_at.strftime("%A at %H:%M")
        else:
            return self.created_at.strftime("%Y-%m-%d %H:%M")
    
    @property
    def duration_formatted(self) -> str:
        """Format duration as MM:SS or HH:MM:SS."""
        total = int(self.duration_seconds)
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
    
    @property
    def word_count(self) -> int:
        """Get word count of transcript."""
        return len(self.transcript.split()) if self.transcript else 0


class HistoryDatabase:
    """SQLite database for transcription history."""
    
    def __init__(self) -> None:
        """Initialize the database."""
        self._ensure_db_exists()
    
    def _ensure_db_exists(self) -> None:
        """Create database and tables if they don't exist."""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transcriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    transcript TEXT NOT NULL,
                    engine TEXT NOT NULL,
                    language TEXT DEFAULT 'en',
                    duration_seconds REAL DEFAULT 0,
                    refined INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    file_size_mb REAL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON transcriptions(created_at DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_filename 
                ON transcriptions(filename)
            """)
            conn.commit()
    
    def add_record(
        self,
        filename: str,
        file_path: str,
        transcript: str,
        engine: str,
        language: str = "en",
        duration_seconds: float = 0,
        refined: bool = False,
        file_size_mb: float = 0,
    ) -> int:
        """Add a new transcription record.
        
        Returns:
            The ID of the new record.
        """
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                """
                INSERT INTO transcriptions 
                (filename, file_path, transcript, engine, language, 
                 duration_seconds, refined, created_at, file_size_mb)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    filename,
                    file_path,
                    transcript,
                    engine,
                    language,
                    duration_seconds,
                    1 if refined else 0,
                    datetime.now().isoformat(),
                    file_size_mb,
                ),
            )
            conn.commit()
            return cursor.lastrowid or 0
    
    def get_all_records(self, limit: int = 100) -> list[TranscriptionRecord]:
        """Get all transcription records, newest first."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM transcriptions 
                ORDER BY created_at DESC 
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
    
    def search_records(self, query: str) -> list[TranscriptionRecord]:
        """Search records by filename or transcript content."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM transcriptions 
                WHERE filename LIKE ? OR transcript LIKE ?
                ORDER BY created_at DESC 
                LIMIT 50
                """,
                (f"%{query}%", f"%{query}%"),
            )
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
    
    def get_record(self, record_id: int) -> TranscriptionRecord | None:
        """Get a specific record by ID."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM transcriptions WHERE id = ?",
                (record_id,),
            )
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None
    
    def delete_record(self, record_id: int) -> None:
        """Delete a record by ID."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM transcriptions WHERE id = ?", (record_id,))
            conn.commit()
    
    def clear_all(self) -> None:
        """Delete all records."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM transcriptions")
            conn.commit()
    
    def _row_to_record(self, row: sqlite3.Row) -> TranscriptionRecord:
        """Convert a database row to a TranscriptionRecord."""
        return TranscriptionRecord(
            id=row["id"],
            filename=row["filename"],
            file_path=row["file_path"],
            transcript=row["transcript"],
            engine=row["engine"],
            language=row["language"] or "en",
            duration_seconds=row["duration_seconds"] or 0,
            refined=bool(row["refined"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            file_size_mb=row["file_size_mb"] or 0,
        )


def _get_app() -> Any:
    """Get the running MDApp instance."""
    from kivymd.app import MDApp
    return MDApp.get_running_app()


class HistoryListItem(ThreeLineIconListItem):
    """Custom list item for history entries."""
    
    def __init__(self, record: TranscriptionRecord, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.record = record
        
        # Set text
        self.text = record.filename
        self.secondary_text = (
            f"{record.duration_formatted}  |  "
            f"🔧 {record.engine}  •  "
            f"{'Refined' if record.refined else 'Raw'}"
        )
        self.tertiary_text = f"{record.created_formatted}  •  {record.word_count} words"
        
        # Add icon
        icon = IconLeftWidget(icon="file-document-outline")
        self.add_widget(icon)


class HistoryScreen(Screen):
    """History browser screen."""
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.db = HistoryDatabase()
        self.records: list[TranscriptionRecord] = []
        self.selected_record: TranscriptionRecord | None = None
        self.detail_dialog: MDDialog | None = None
        self.confirm_dialog: MDDialog | None = None
        self.filter_menu: MDDropdownMenu | None = None
        
        self._build_ui()
    
    def on_enter(self, *args: Any) -> None:
        """Refresh history when entering screen."""
        super().on_enter(*args)
        Clock.schedule_once(lambda dt: self._load_records())
    
    def _build_ui(self) -> None:
        """Build the history screen UI."""
        main_layout = MDBoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=[dp(16), dp(12)],
        )
        
        # Header
        main_layout.add_widget(self._build_header())
        
        # Search bar
        main_layout.add_widget(self._build_search_bar())
        
        # History list
        main_layout.add_widget(self._build_history_list())
        
        self.add_widget(main_layout)
    
    def _build_header(self) -> MDBoxLayout:
        """Build the header with title and actions."""
        header = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(48),
            spacing=dp(8),
        )
        
        # Title
        title = MDLabel(
            text="[b]📜 Transcription History[/b]",
            markup=True,
            font_style="H5",
            theme_text_color="Primary",
            size_hint=(1, 1),
            valign="center",
        )
        header.add_widget(title)
        
        # Refresh button
        refresh_btn = TooltipIconButton(
            icon="refresh",
            on_release=lambda x: self._load_records(),
        )
        refresh_btn.tooltip_text = "Refresh (F5)"
        header.add_widget(refresh_btn)
        
        # Filter button
        filter_btn = TooltipIconButton(
            icon="filter-variant",
            on_release=self._show_filter_menu,
        )
        filter_btn.tooltip_text = "Filter"
        self.filter_button = filter_btn
        header.add_widget(filter_btn)
        
        # Clear all button
        clear_btn = TooltipIconButton(
            icon="delete-sweep",
            on_release=self._confirm_clear_all,
        )
        clear_btn.tooltip_text = "Clear all history"
        header.add_widget(clear_btn)
        
        return header
    
    def _build_search_bar(self) -> MDBoxLayout:
        """Build the search bar."""
        search_layout = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(56),
            spacing=dp(8),
        )
        
        # Search field
        self.search_field = MDTextField(
            hint_text="🔍 Search transcriptions...",
            mode="rectangle",
            size_hint=(1, 1),
        )
        self.search_field.bind(text=self._on_search_text_changed)
        search_layout.add_widget(self.search_field)
        
        return search_layout
    
    def _build_history_list(self) -> MDCard:
        """Build the scrollable history list."""
        list_card = MDCard(
            orientation="vertical",
            padding=[dp(8), dp(8)],
            size_hint=(1, 1),
            elevation=2,
            radius=[dp(12)],
        )
        list_card.md_bg_color = Colors.SURFACE_VARIANT
        
        # Scroll view
        scroll = MDScrollView(size_hint=(1, 1))
        
        # List container
        self.history_list = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(4),
        )
        self.history_list.bind(minimum_height=self.history_list.setter("height"))
        
        # Empty state
        self.empty_label = MDLabel(
            text="No transcriptions yet.\nTranscribe an audio file to get started!",
            halign="center",
            theme_text_color="Secondary",
            font_style="Body1",
            size_hint=(1, None),
            height=dp(100),
        )
        self.history_list.add_widget(self.empty_label)
        
        scroll.add_widget(self.history_list)
        list_card.add_widget(scroll)
        
        return list_card
    
    def _load_records(self) -> None:
        """Load records from database."""
        try:
            self.records = self.db.get_all_records()
            self._update_list()
            logger.info("Loaded history records", count=len(self.records))
        except Exception as e:
            logger.error("Failed to load history", error=str(e))
            self._show_snackbar(f"Failed to load history: {e}", error=True)
    
    def _update_list(self) -> None:
        """Update the history list display."""
        self.history_list.clear_widgets()
        
        if not self.records:
            self.history_list.add_widget(self.empty_label)
            return
        
        # Group by date
        today = datetime.now().date()
        yesterday = today.replace(day=today.day - 1) if today.day > 1 else today
        
        current_date = None
        
        for record in self.records:
            record_date = record.created_at.date()
            
            # Add date header if date changed
            if record_date != current_date:
                current_date = record_date
                
                if record_date == today:
                    date_text = "Today"
                elif record_date == yesterday:
                    date_text = "Yesterday"
                else:
                    date_text = record_date.strftime("%B %d, %Y")
                
                header = MDLabel(
                    text=f"[b]{date_text}[/b]",
                    markup=True,
                    font_style="Subtitle2",
                    theme_text_color="Secondary",
                    size_hint=(1, None),
                    height=dp(32),
                    padding=[dp(16), dp(8)],
                )
                self.history_list.add_widget(header)
            
            # Add record item
            item = HistoryListItem(
                record=record,
                on_release=lambda x, r=record: self._show_record_detail(r),
            )
            self.history_list.add_widget(item)
    
    def _on_search_text_changed(self, instance: Any, text: str) -> None:
        """Handle search text changes."""
        if not text:
            self._load_records()
            return
        
        # Debounce search
        Clock.unschedule(self._perform_search)
        Clock.schedule_once(lambda dt: self._perform_search(text), 0.3)
    
    def _perform_search(self, query: str) -> None:
        """Perform search query."""
        try:
            self.records = self.db.search_records(query)
            self._update_list()
            logger.info("Search completed", query=query, results=len(self.records))
        except Exception as e:
            logger.error("Search failed", error=str(e))
    
    def _show_filter_menu(self, button: Any) -> None:
        """Show filter dropdown menu."""
        filters = [
            ("All", self._filter_all),
            ("Today", self._filter_today),
            ("This Week", self._filter_week),
            ("Refined Only", self._filter_refined),
        ]
        
        menu_items = [
            {
                "text": text,
                "on_release": callback,
            }
            for text, callback in filters
        ]
        
        self.filter_menu = MDDropdownMenu(
            caller=button,
            items=menu_items,
            width_mult=3,
        )
        self.filter_menu.open()
    
    def _filter_all(self) -> None:
        """Show all records."""
        if self.filter_menu:
            self.filter_menu.dismiss()
        self._load_records()
    
    def _filter_today(self) -> None:
        """Filter to today's records."""
        if self.filter_menu:
            self.filter_menu.dismiss()
        
        today = datetime.now().date()
        self.records = [
            r for r in self.db.get_all_records()
            if r.created_at.date() == today
        ]
        self._update_list()
    
    def _filter_week(self) -> None:
        """Filter to this week's records."""
        if self.filter_menu:
            self.filter_menu.dismiss()
        
        from datetime import timedelta
        week_ago = datetime.now() - timedelta(days=7)
        self.records = [
            r for r in self.db.get_all_records()
            if r.created_at >= week_ago
        ]
        self._update_list()
    
    def _filter_refined(self) -> None:
        """Filter to refined records only."""
        if self.filter_menu:
            self.filter_menu.dismiss()
        
        self.records = [r for r in self.db.get_all_records() if r.refined]
        self._update_list()
    
    def _show_record_detail(self, record: TranscriptionRecord) -> None:
        """Show detailed view of a record."""
        self.selected_record = record
        
        # Build content
        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(12),
            size_hint_y=None,
            padding=[dp(16), dp(8)],
        )
        content.height = dp(400)
        
        # Metadata
        meta_text = (
            f"**File:** {record.filename}\n"
            f"**Duration:** {record.duration_formatted}\n"
            f"**Engine:** {record.engine}\n"
            f"**Created:** {record.created_formatted}\n"
            f"**Words:** {record.word_count}\n"
            f"**Refined:** {'Yes' if record.refined else 'No'}"
        )
        
        meta_label = MDLabel(
            text=meta_text,
            markup=False,
            font_style="Body2",
            theme_text_color="Secondary",
            size_hint=(1, None),
            height=dp(120),
        )
        content.add_widget(meta_label)
        
        # Transcript preview
        preview_label = MDLabel(
            text="[b]Transcript Preview:[/b]",
            markup=True,
            font_style="Subtitle2",
            size_hint=(1, None),
            height=dp(24),
        )
        content.add_widget(preview_label)
        
        # Scrollable transcript
        scroll = MDScrollView(size_hint=(1, 1))
        transcript_field = MDTextField(
            text=record.transcript[:2000] + ("..." if len(record.transcript) > 2000 else ""),
            multiline=True,
            mode="rectangle",
            readonly=True,
        )
        scroll.add_widget(transcript_field)
        content.add_widget(scroll)
        
        # Actions
        if self.detail_dialog:
            self.detail_dialog.dismiss()
        
        self.detail_dialog = MDDialog(
            title=record.filename,
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="DELETE",
                    theme_text_color="Custom",
                    text_color=Colors.ERROR,
                    on_release=lambda x: self._delete_record(record.id),
                ),
                MDFlatButton(
                    text="EXPORT",
                    on_release=lambda x: self._export_record(record),
                ),
                MDFlatButton(
                    text="COPY",
                    on_release=lambda x: self._copy_record(record),
                ),
                MDFlatButton(
                    text="CLOSE",
                    on_release=lambda x: self.detail_dialog.dismiss(),
                ),
            ],
        )
        self.detail_dialog.open()
    
    def _delete_record(self, record_id: int) -> None:
        """Delete a record."""
        if self.detail_dialog:
            self.detail_dialog.dismiss()
        
        try:
            self.db.delete_record(record_id)
            self._load_records()
            self._show_snackbar("Record deleted")
            logger.info("Record deleted", id=record_id)
        except Exception as e:
            logger.error("Delete failed", error=str(e))
            self._show_snackbar(f"Delete failed: {e}", error=True)
    
    def _export_record(self, record: TranscriptionRecord) -> None:
        """Export a record to file."""
        if self.detail_dialog:
            self.detail_dialog.dismiss()
        
        try:
            # Export to user's downloads or home
            downloads = Path.home() / "Downloads"
            if not downloads.exists():
                downloads = Path.home()
            
            filename = f"{Path(record.filename).stem}_transcript.txt"
            output_path = downloads / filename
            
            output_path.write_text(record.transcript, encoding="utf-8")
            self._show_snackbar(f"Exported to {output_path.name}")
            logger.info("Record exported", path=str(output_path))
        except Exception as e:
            logger.error("Export failed", error=str(e))
            self._show_snackbar(f"Export failed: {e}", error=True)
    
    def _copy_record(self, record: TranscriptionRecord) -> None:
        """Copy record transcript to clipboard."""
        if self.detail_dialog:
            self.detail_dialog.dismiss()
        
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(record.transcript)
            self._show_snackbar("Copied to clipboard")
        except Exception as e:
            logger.error("Copy failed", error=str(e))
            self._show_snackbar("Copy failed", error=True)
    
    def _confirm_clear_all(self, *args: Any) -> None:
        """Show confirmation dialog before clearing all history."""
        if self.confirm_dialog:
            self.confirm_dialog.dismiss()
        
        self.confirm_dialog = MDDialog(
            title="Clear All History?",
            text="This will permanently delete all transcription history. This cannot be undone.",
            buttons=[
                MDFlatButton(
                    text="CANCEL",
                    on_release=lambda x: self.confirm_dialog.dismiss(),
                ),
                MDFlatButton(
                    text="CLEAR ALL",
                    theme_text_color="Custom",
                    text_color=Colors.ERROR,
                    on_release=lambda x: self._clear_all(),
                ),
            ],
        )
        self.confirm_dialog.open()
    
    def _clear_all(self) -> None:
        """Clear all history."""
        if self.confirm_dialog:
            self.confirm_dialog.dismiss()
        
        try:
            self.db.clear_all()
            self._load_records()
            self._show_snackbar("History cleared")
            logger.info("History cleared")
        except Exception as e:
            logger.error("Clear failed", error=str(e))
            self._show_snackbar(f"Clear failed: {e}", error=True)
    
    def _show_snackbar(self, text: str, error: bool = False) -> None:
        """Show a snackbar notification (KivyMD 1.2 compatible)."""
        from kivymd.uix.snackbar import MDSnackbar
        snackbar = MDSnackbar(text, duration=3 if not error else 5)
        if error:
            snackbar.md_bg_color = Colors.ERROR
        snackbar.open()
    
    def add_transcription(
        self,
        filename: str,
        file_path: str,
        transcript: str,
        engine: str,
        duration_seconds: float = 0,
        refined: bool = False,
        file_size_mb: float = 0,
    ) -> int:
        """Add a new transcription to history.
        
        Called by the home screen when a transcription completes.
        
        Returns:
            The ID of the new record.
        """
        try:
            record_id = self.db.add_record(
                filename=filename,
                file_path=file_path,
                transcript=transcript,
                engine=engine,
                duration_seconds=duration_seconds,
                refined=refined,
                file_size_mb=file_size_mb,
            )
            logger.info("Added transcription to history", id=record_id)
            return record_id
        except Exception as e:
            logger.error("Failed to add to history", error=str(e))
            return 0
