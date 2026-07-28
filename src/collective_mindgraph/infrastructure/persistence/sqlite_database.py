"""SQLite connection boundary for the canonical local store."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class SqliteDatabase:
    """Owns SQLite connection configuration without import-time side effects."""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(self.path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def prepare_directory(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def validate_foreign_keys(self) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return list(connection.execute("PRAGMA foreign_key_check").fetchall())
