"""SQLite access and schema management for the companion app."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path


class Database:
    """Provides SQLite connections and initializes the companion schema."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or self.default_db_path()

    @staticmethod
    def default_db_path() -> Path:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            base_dir = Path(local_app_data)
        elif os.name == "nt":
            base_dir = Path.home() / "AppData" / "Local"
        else:
            base_dir = Path.home() / ".local" / "share"
        return base_dir / "CollectiveMindGraphCompanion" / "companion.sqlite3"

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        return connection

    def initialize(self) -> None:
        if self._has_legacy_schema():
            self._backup_legacy_database()

        schema = """
        CREATE TABLE IF NOT EXISTS main_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sub_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            main_category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (main_category_id) REFERENCES main_categories(id) ON DELETE CASCADE,
            UNIQUE (main_category_id, name)
        );

        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            main_category_id INTEGER NOT NULL,
            sub_category_id INTEGER,
            template_name TEXT NOT NULL,
            mood TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (main_category_id) REFERENCES main_categories(id) ON DELETE RESTRICT,
            FOREIGN KEY (sub_category_id) REFERENCES sub_categories(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS note_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL UNIQUE,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES user_sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_main_categories_name
            ON main_categories(name);
        CREATE INDEX IF NOT EXISTS idx_sub_categories_main
            ON sub_categories(main_category_id, name);
        CREATE INDEX IF NOT EXISTS idx_user_sessions_updated_at
            ON user_sessions(updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_user_sessions_main_category
            ON user_sessions(main_category_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_user_sessions_sub_category
            ON user_sessions(sub_category_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_note_entries_session
            ON note_entries(session_id);
        """
        with self.connect() as connection:
            connection.executescript(schema)

    def _has_legacy_schema(self) -> bool:
        if not self.db_path.exists():
            return False
        connection = sqlite3.connect(self.db_path)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            if "user_sessions" not in tables:
                return False
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(user_sessions)").fetchall()
            }
            return not {"main_category_id", "template_name"}.issubset(columns)
        finally:
            connection.close()

    def _backup_legacy_database(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = self.db_path.with_name(f"{self.db_path.stem}.legacy-{timestamp}{self.db_path.suffix}")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.db_path.replace(backup_path)
        except PermissionError:
            # If an older companion build still holds the file open, continue on a fresh v2 database path.
            self.db_path = self.db_path.with_name(f"{self.db_path.stem}-v2{self.db_path.suffix}")
