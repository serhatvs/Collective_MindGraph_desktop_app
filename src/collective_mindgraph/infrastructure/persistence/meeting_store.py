"""SQLite meeting persistence."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from collective_mindgraph.application.pagination import Page, PageRequest
from collective_mindgraph.domain import Meeting, MeetingId, MeetingStatus

from .row_mapping import parse_timestamp
from .sqlite_database import SqliteDatabase
from .sqlite_pagination import decode_offset, encode_offset


class SqliteMeetingStore:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def create(
        self,
        *,
        title: str,
        status: MeetingStatus,
        input_device: str | None,
        now: datetime,
    ) -> Meeting:
        timestamp = now.isoformat()
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO meetings(title, status, input_device, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, status.value, input_device, timestamp, timestamp),
            )
            meeting_id = MeetingId(int(cursor.lastrowid))
        meeting = self.get(meeting_id)
        if meeting is None:
            raise RuntimeError("Created meeting could not be loaded.")
        return meeting

    def get(self, meeting_id: MeetingId) -> Meeting | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM meetings WHERE id = ?",
                (int(meeting_id),),
            ).fetchone()
        return self._map(row) if row is not None else None

    def list(self, request: PageRequest, *, query: str = "") -> Page[Meeting]:
        offset = decode_offset(request.cursor)
        normalized_query = query.strip()
        where = "WHERE title LIKE ? ESCAPE '\\'" if normalized_query else ""
        parameters: list[object] = []
        if normalized_query:
            escaped = normalized_query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            parameters.append(f"%{escaped}%")
        with self._database.connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM meetings {where}",
                    tuple(parameters),
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"""
                SELECT * FROM meetings
                {where}
                ORDER BY updated_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (*parameters, request.limit, offset),
            ).fetchall()
        items = tuple(self._map(row) for row in rows)
        return Page(
            items=items,
            total=total,
            next_cursor=encode_offset(offset + len(items), total),
        )

    def rename(self, meeting_id: MeetingId, *, title: str, now: datetime) -> Meeting | None:
        return self._update(meeting_id, "title", title, now)

    def set_status(
        self,
        meeting_id: MeetingId,
        *,
        status: MeetingStatus,
        now: datetime,
    ) -> Meeting | None:
        return self._update(meeting_id, "status", status.value, now)

    def delete(self, meeting_id: MeetingId) -> bool:
        with self._database.connect() as connection:
            cursor = connection.execute("DELETE FROM meetings WHERE id = ?", (int(meeting_id),))
        return cursor.rowcount > 0

    def count(self) -> int:
        with self._database.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM meetings").fetchone()[0])

    def _update(
        self,
        meeting_id: MeetingId,
        column: str,
        value: str,
        now: datetime,
    ) -> Meeting | None:
        if column not in {"title", "status"}:
            raise ValueError("Unsupported meeting update.")
        with self._database.connect() as connection:
            cursor = connection.execute(
                f"UPDATE meetings SET {column} = ?, updated_at = ? WHERE id = ?",
                (value, now.isoformat(), int(meeting_id)),
            )
        return self.get(meeting_id) if cursor.rowcount else None

    @staticmethod
    def _map(row: sqlite3.Row) -> Meeting:
        return Meeting(
            id=MeetingId(int(row["id"])),
            title=str(row["title"]),
            status=MeetingStatus(str(row["status"])),
            input_device=str(row["input_device"]) if row["input_device"] else None,
            created_at=parse_timestamp(str(row["created_at"])),
            updated_at=parse_timestamp(str(row["updated_at"])),
        )
