"""SQLite database access and schema management."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


class Database:
    """Provides SQLite connections and initializes the application schema."""

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
        return base_dir / "CollectiveMindGraph" / "collective_mindgraph.sqlite3"

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        return connection

    def initialize(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            device_id TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            confidence REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS graph_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            transcript_id INTEGER,
            parent_node_id INTEGER,
            branch_type TEXT NOT NULL CHECK (branch_type IN ('root', 'main', 'side')),
            branch_slot INTEGER CHECK (branch_slot IS NULL OR branch_slot IN (1, 2)),
            node_text TEXT NOT NULL,
            override_reason TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE SET NULL,
            FOREIGN KEY (parent_node_id) REFERENCES graph_nodes(id) ON DELETE CASCADE,
            CHECK (
                (branch_type = 'root' AND parent_node_id IS NULL AND branch_slot IS NULL)
                OR (branch_type = 'main' AND parent_node_id IS NOT NULL AND branch_slot IS NULL)
                OR (branch_type = 'side' AND parent_node_id IS NOT NULL AND branch_slot IN (1, 2))
            )
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            node_count INTEGER NOT NULL,
            hash_sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_sessions_search_title ON sessions(title);
        CREATE INDEX IF NOT EXISTS idx_sessions_search_device ON sessions(device_id);
        CREATE INDEX IF NOT EXISTS idx_transcripts_session ON transcripts(session_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_graph_nodes_session ON graph_nodes(session_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_snapshots_session ON snapshots(session_id, created_at DESC);
        """
        with self.connect() as connection:
            connection.executescript(schema)
