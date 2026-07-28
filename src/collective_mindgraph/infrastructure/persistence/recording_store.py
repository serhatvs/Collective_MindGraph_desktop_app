"""SQLite recording metadata persistence."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from collective_mindgraph.domain import (
    MeetingId,
    Recording,
    RecordingId,
    RecordingStorageStatus,
)

from .row_mapping import parse_timestamp
from .sqlite_database import SqliteDatabase


class SqliteRecordingStore:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def save(self, recording: Recording) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO recordings (
                    id, meeting_id, source_uri, duration_seconds,
                    input_device, storage_status, keep_audio, deleted_at, captured_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    meeting_id = excluded.meeting_id,
                    source_uri = excluded.source_uri,
                    duration_seconds = excluded.duration_seconds,
                    input_device = excluded.input_device,
                    storage_status = excluded.storage_status,
                    keep_audio = excluded.keep_audio,
                    deleted_at = excluded.deleted_at,
                    captured_at = excluded.captured_at
                """,
                (
                    str(recording.id),
                    int(recording.meeting_id),
                    recording.source_uri,
                    recording.duration_seconds,
                    recording.input_device,
                    recording.storage_status.value,
                    int(recording.keep_audio),
                    recording.deleted_at.isoformat() if recording.deleted_at else None,
                    recording.captured_at.isoformat(),
                ),
            )

    def get(self, recording_id: RecordingId) -> Recording | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM recordings WHERE id = ?",
                (str(recording_id),),
            ).fetchone()
        return self._map(row) if row is not None else None

    def list_for_meeting(self, meeting_id: MeetingId) -> tuple[Recording, ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM recordings
                WHERE meeting_id = ?
                ORDER BY captured_at, id
                """,
                (int(meeting_id),),
            ).fetchall()
        return tuple(self._map(row) for row in rows)

    def update_storage(
        self,
        recording_id: RecordingId,
        *,
        status: RecordingStorageStatus,
        deleted_at: datetime | None = None,
    ) -> Recording | None:
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE recordings
                SET storage_status = ?, deleted_at = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    deleted_at.isoformat() if deleted_at else None,
                    str(recording_id),
                ),
            )
        return self.get(recording_id) if cursor.rowcount else None

    @staticmethod
    def _map(row: sqlite3.Row) -> Recording:
        return Recording(
            id=RecordingId(str(row["id"])),
            meeting_id=MeetingId(int(row["meeting_id"])),
            source_uri=str(row["source_uri"]),
            duration_seconds=(
                float(row["duration_seconds"]) if row["duration_seconds"] is not None else None
            ),
            input_device=str(row["input_device"]) if row["input_device"] else None,
            captured_at=parse_timestamp(str(row["captured_at"])),
            storage_status=RecordingStorageStatus(str(row["storage_status"])),
            keep_audio=bool(row["keep_audio"]),
            deleted_at=(parse_timestamp(str(row["deleted_at"])) if row["deleted_at"] else None),
        )
