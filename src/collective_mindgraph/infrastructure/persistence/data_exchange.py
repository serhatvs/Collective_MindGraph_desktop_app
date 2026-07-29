"""Versioned import and export for canonical local data."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from collective_mindgraph.domain import MeetingId

from .data_exchange_mapping import safe_import_value
from .data_exchange_schema import (
    FORMAT_VERSION,
    SUPPORTED_CANONICAL_VERSIONS,
    V5_TABLE_COLUMNS,
    columns_for_import,
    select_rows,
    validate_import_rows,
)
from .encrypted_backup import read_encrypted_backup, write_encrypted_backup
from .legacy_graph_exchange import import_legacy_graph_export
from .sqlite_database import SqliteDatabase


class SqliteDataExchange:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def export(self, meeting_id: MeetingId | None = None) -> dict[str, object]:
        with self._database.connect() as connection:
            tables: dict[str, list[dict[str, object]]] = {}
            for table, columns in V5_TABLE_COLUMNS.items():
                rows = select_rows(connection, table, meeting_id)
                tables[table] = [{column: row[column] for column in columns} for row in rows]
        return {
            "format": "collective_mindgraph",
            "format_version": FORMAT_VERSION,
            "exported_at": datetime.now(tz=UTC).isoformat(),
            "scope": (
                {"meeting_id": int(meeting_id)}
                if meeting_id is not None
                else {"all_meetings": True}
            ),
            "tables": tables,
        }

    def import_payload(self, payload: dict[str, object]) -> dict[str, int]:
        if "v2_production_graph" in payload or (
            "session" in payload and "format_version" not in payload
        ):
            return import_legacy_graph_export(self._database, payload)
        version = payload.get("format_version")
        if not isinstance(version, int) or version not in SUPPORTED_CANONICAL_VERSIONS:
            raise ValueError(f"Unsupported export format_version: {version!r}.")
        tables = payload.get("tables")
        if not isinstance(tables, dict):
            raise ValueError("Export payload must contain a tables object.")
        return self._import_canonical_tables(version, tables)

    def export_backup(
        self,
        path: Path,
        *,
        passphrase: str,
        meeting_id: MeetingId | None = None,
    ) -> Path:
        return write_encrypted_backup(
            path,
            self.export(meeting_id),
            passphrase=passphrase,
        )

    def import_backup(self, path: Path, *, passphrase: str) -> dict[str, int]:
        return self.import_payload(read_encrypted_backup(path, passphrase=passphrase))

    def _import_canonical_tables(
        self,
        version: int,
        tables: dict[object, object],
    ) -> dict[str, int]:
        table_columns = columns_for_import(version)
        counts: dict[str, int] = {}
        try:
            with self._database.connect() as connection:
                connection.execute("PRAGMA defer_foreign_keys = ON")
                existing_rows = validate_import_rows(
                    connection,
                    tables,
                    table_columns,
                )
                for table, columns in table_columns.items():
                    raw_rows = cast(list[dict[str, object]], tables.get(table, []))
                    imported = 0
                    for raw_row in raw_rows:
                        if raw_row["id"] in existing_rows[table]:
                            continue
                        values = [safe_import_value(table, column, raw_row) for column in columns]
                        placeholders = ", ".join("?" for _ in columns)
                        connection.execute(
                            f"""
                            INSERT INTO {table} ({", ".join(columns)})
                            VALUES ({placeholders})
                            """,
                            values,
                        )
                        imported += 1
                    counts[table] = imported
        except sqlite3.IntegrityError as error:
            raise ValueError("Export payload violates canonical data constraints.") from error
        return counts


__all__ = ["FORMAT_VERSION", "SqliteDataExchange"]
