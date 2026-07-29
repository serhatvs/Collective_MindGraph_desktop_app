"""SQLite outbox, cursor, and conflict persistence for the sync agent."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from collective_mindgraph.domain import (
    ConflictRecord,
    ConflictResolution,
    OutboxEntry,
    SyncCursor,
)
from collective_mindgraph.domain.identifiers import (
    ConflictId,
    OperationId,
    SyncId,
    WorkspaceId,
)

from .row_mapping import parse_timestamp
from .sqlite_database import SqliteDatabase


class SqliteOutboxStore:
    """Durable queue so a restart never loses or duplicates a local change."""

    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    # Outbox --------------------------------------------------------------

    def enqueue(self, entry: OutboxEntry) -> None:
        """Record one pending change idempotently."""

        with self._database.connect() as connection:
            connection.execute(
                # Ignoring any conflict keeps enqueueing idempotent for both the
                # operation id and the one-revision-per-object constraint.
                """
                INSERT OR IGNORE INTO sync_outbox(
                    operation_id, workspace_id, object_id, object_type,
                    base_revision, local_revision, ciphertext, deleted,
                    client_timestamp, state, attempt_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    str(entry.operation_id),
                    str(entry.workspace_id),
                    str(entry.object_id),
                    entry.object_type,
                    entry.base_revision,
                    entry.local_revision,
                    entry.payload or None,
                    int(entry.deleted),
                    entry.client_timestamp.isoformat(),
                    entry.attempt_count,
                    datetime.now(tz=UTC).isoformat(),
                ),
            )

    def pending(self, workspace_id: WorkspaceId, *, limit: int) -> tuple[OutboxEntry, ...]:
        """Return the oldest queued changes, in the order they were made."""

        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM sync_outbox
                WHERE workspace_id = ? AND state IN ('pending', 'failed')
                ORDER BY created_at, operation_id
                LIMIT ?
                """,
                (str(workspace_id), limit),
            ).fetchall()
        return tuple(_map_entry(row) for row in rows)

    def mark_pushed(self, operation_ids: tuple[OperationId, ...]) -> int:
        """Remove operations the service accepted or already had."""

        if not operation_ids:
            return 0
        placeholders = ",".join("?" for _ in operation_ids)
        with self._database.connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM sync_outbox WHERE operation_id IN ({placeholders})",
                tuple(str(value) for value in operation_ids),
            )
            return int(cursor.rowcount)

    def mark_failed(self, operation_id: OperationId, *, error: str) -> None:
        """Record a transient failure so backoff and diagnostics can see it."""

        with self._database.connect() as connection:
            connection.execute(
                """
                UPDATE sync_outbox
                SET state = 'failed', attempt_count = attempt_count + 1, last_error = ?
                WHERE operation_id = ?
                """,
                (error[:500], str(operation_id)),
            )

    def pending_count(self, workspace_id: WorkspaceId) -> int:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM sync_outbox WHERE workspace_id = ?",
                (str(workspace_id),),
            ).fetchone()
        return int(row[0]) if row else 0

    # Cursor --------------------------------------------------------------

    def cursor(self, workspace_id: WorkspaceId) -> SyncCursor:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM sync_state WHERE workspace_id = ?",
                (str(workspace_id),),
            ).fetchone()
        if row is None:
            return SyncCursor(workspace_id=workspace_id)
        return SyncCursor(
            workspace_id=workspace_id,
            remote_cursor=str(row["remote_cursor"] or "0"),
            last_pushed_revision=int(row["last_pushed_revision"]),
            last_pull_at=_optional_time(row["last_pull_at"]),
            last_push_at=_optional_time(row["last_push_at"]),
            last_error=str(row["last_error"]) if row["last_error"] else None,
            backoff_until=_optional_time(row["backoff_until"]),
        )

    def save_cursor(self, cursor: SyncCursor) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO sync_state(
                    workspace_id, remote_cursor, last_pushed_revision,
                    last_pull_at, last_push_at, last_error, backoff_until
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    remote_cursor = excluded.remote_cursor,
                    last_pushed_revision = excluded.last_pushed_revision,
                    last_pull_at = excluded.last_pull_at,
                    last_push_at = excluded.last_push_at,
                    last_error = excluded.last_error,
                    backoff_until = excluded.backoff_until
                """,
                (
                    str(cursor.workspace_id),
                    cursor.remote_cursor,
                    cursor.last_pushed_revision,
                    _isoformat(cursor.last_pull_at),
                    _isoformat(cursor.last_push_at),
                    cursor.last_error,
                    _isoformat(cursor.backoff_until),
                ),
            )

    # Conflicts -----------------------------------------------------------

    def record_conflict(
        self,
        *,
        workspace_id: WorkspaceId,
        object_id: SyncId,
        object_type: str,
        local_revision: int,
        remote_revision: int,
        local_payload: bytes,
        remote_payload: bytes = b"",
    ) -> ConflictRecord:
        """Open a conflict, replacing any earlier open one for the entity."""

        now = datetime.now(tz=UTC)
        conflict_id = ConflictId(str(uuid4()))
        with self._database.connect() as connection:
            connection.execute(
                """
                DELETE FROM conflict_versions
                WHERE workspace_id = ? AND object_id = ? AND resolved_at IS NULL
                """,
                (str(workspace_id), str(object_id)),
            )
            connection.execute(
                """
                INSERT INTO conflict_versions(
                    id, workspace_id, object_id, object_type, local_revision,
                    remote_revision, local_payload_json, remote_payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(conflict_id),
                    str(workspace_id),
                    str(object_id),
                    object_type,
                    local_revision,
                    remote_revision,
                    local_payload,
                    remote_payload,
                    now.isoformat(),
                ),
            )
        return ConflictRecord(
            id=conflict_id,
            workspace_id=workspace_id,
            object_id=object_id,
            object_type=object_type,
            local_revision=local_revision,
            remote_revision=remote_revision,
            created_at=now,
            local_payload=local_payload,
            remote_payload=remote_payload,
        )

    def open_conflicts(self, workspace_id: WorkspaceId) -> tuple[ConflictRecord, ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM conflict_versions
                WHERE workspace_id = ? AND resolved_at IS NULL
                ORDER BY created_at, id
                """,
                (str(workspace_id),),
            ).fetchall()
        return tuple(_map_conflict(row) for row in rows)

    def get_conflict(self, conflict_id: ConflictId) -> ConflictRecord | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM conflict_versions WHERE id = ?",
                (str(conflict_id),),
            ).fetchone()
        return _map_conflict(row) if row is not None else None

    def resolve_conflict(
        self,
        conflict_id: ConflictId,
        resolution: ConflictResolution,
    ) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                UPDATE conflict_versions
                SET resolved_at = ?, resolution = ?
                WHERE id = ? AND resolved_at IS NULL
                """,
                (datetime.now(tz=UTC).isoformat(), resolution.value, str(conflict_id)),
            )

    def open_conflict_count(self, workspace_id: WorkspaceId) -> int:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) FROM conflict_versions
                WHERE workspace_id = ? AND resolved_at IS NULL
                """,
                (str(workspace_id),),
            ).fetchone()
        return int(row[0]) if row else 0


def _map_entry(row: sqlite3.Row) -> OutboxEntry:
    payload = row["ciphertext"]
    return OutboxEntry(
        operation_id=OperationId(str(row["operation_id"])),
        workspace_id=WorkspaceId(str(row["workspace_id"])),
        object_id=SyncId(str(row["object_id"])),
        object_type=str(row["object_type"]),
        base_revision=int(row["base_revision"]),
        local_revision=int(row["local_revision"]),
        client_timestamp=parse_timestamp(str(row["client_timestamp"])),
        payload=bytes(payload) if payload is not None else b"",
        deleted=bool(row["deleted"]),
        attempt_count=int(row["attempt_count"]),
        last_error=str(row["last_error"]) if row["last_error"] else None,
    )


def _map_conflict(row: sqlite3.Row) -> ConflictRecord:
    resolution = row["resolution"]
    return ConflictRecord(
        id=ConflictId(str(row["id"])),
        workspace_id=WorkspaceId(str(row["workspace_id"])),
        object_id=SyncId(str(row["object_id"])),
        object_type=str(row["object_type"]),
        local_revision=int(row["local_revision"]),
        remote_revision=int(row["remote_revision"]),
        created_at=parse_timestamp(str(row["created_at"])),
        local_payload=_blob(row["local_payload_json"]),
        remote_payload=_blob(row["remote_payload_json"]),
        resolved_at=_optional_time(row["resolved_at"]),
        resolution=ConflictResolution(str(resolution)) if resolution else None,
    )


def _blob(value: object) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    return str(value).encode("utf-8")


def _optional_time(value: object) -> datetime | None:
    return parse_timestamp(str(value)) if value else None


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


__all__ = ["SqliteOutboxStore"]
