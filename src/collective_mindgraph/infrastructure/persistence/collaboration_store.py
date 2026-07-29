"""SQLite persistence for comments and workspace activity."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from collective_mindgraph.domain import ActivityEvent, ActivityKind, Comment
from collective_mindgraph.domain.identifiers import (
    ActivityEventId,
    CommentId,
    DeviceId,
    SyncId,
    WorkspaceId,
)

from .row_mapping import parse_timestamp
from .sqlite_database import SqliteDatabase

DEFAULT_ACTIVITY_LIMIT = 100


class SqliteCollaborationStore:
    """Append-only comment and activity storage for one local database."""

    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    # Comments ------------------------------------------------------------

    def add_comment(
        self,
        *,
        workspace_id: WorkspaceId,
        target_type: str,
        target_sync_id: SyncId,
        body: str,
        author_subject: str,
        parent_id: CommentId | None = None,
        meeting_id: int | None = None,
    ) -> Comment:
        """Append one comment and record the matching activity."""

        now = datetime.now(tz=UTC)
        comment = Comment(
            id=CommentId(str(uuid4())),
            workspace_id=workspace_id,
            target_type=target_type,
            target_sync_id=target_sync_id,
            body=body,
            author_subject=author_subject,
            created_at=now,
            updated_at=now,
            parent_id=parent_id,
        )
        with self._database.connect() as connection:
            if parent_id is not None and not _comment_exists(connection, parent_id):
                raise ValueError("The parent comment does not exist.")
            connection.execute(
                """
                INSERT INTO comments(
                    id, workspace_id, meeting_id, parent_id, target_type,
                    target_sync_id, body, author_subject, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(comment.id),
                    str(workspace_id),
                    meeting_id,
                    str(parent_id) if parent_id else None,
                    target_type,
                    str(target_sync_id),
                    body,
                    author_subject,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        self.record_activity(
            workspace_id=workspace_id,
            kind=ActivityKind.COMMENT_ADDED,
            actor_subject=author_subject,
            object_type=target_type,
            object_sync_id=target_sync_id,
        )
        for subject in comment.mentions:
            self.record_activity(
                workspace_id=workspace_id,
                kind=ActivityKind.MEMBER_MENTIONED,
                actor_subject=author_subject,
                object_type=target_type,
                object_sync_id=target_sync_id,
                details={"subject": subject},
            )
        return comment

    def comments_for(
        self,
        workspace_id: WorkspaceId,
        *,
        target_type: str,
        target_sync_id: SyncId,
    ) -> tuple[Comment, ...]:
        """Return one entity's thread in the order it was written."""

        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM comments
                WHERE workspace_id = ? AND target_type = ? AND target_sync_id = ?
                ORDER BY created_at, id
                """,
                (str(workspace_id), target_type, str(target_sync_id)),
            ).fetchall()
        return tuple(_map_comment(row) for row in rows)

    def mentions_of(
        self,
        workspace_id: WorkspaceId,
        subject: str,
        *,
        limit: int = DEFAULT_ACTIVITY_LIMIT,
    ) -> tuple[Comment, ...]:
        """Return comments that mention one member, newest first."""

        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM comments
                WHERE workspace_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (str(workspace_id),),
            ).fetchall()
        wanted = subject.casefold()
        matched = [
            comment for comment in (_map_comment(row) for row in rows) if wanted in comment.mentions
        ]
        return tuple(matched[:limit])

    # Activity ------------------------------------------------------------

    def record_activity(
        self,
        *,
        workspace_id: WorkspaceId,
        kind: ActivityKind,
        actor_subject: str | None = None,
        object_type: str | None = None,
        object_sync_id: SyncId | None = None,
        details: dict[str, str] | None = None,
        meeting_id: int | None = None,
    ) -> ActivityEvent:
        """Append one activity record."""

        now = datetime.now(tz=UTC)
        event = ActivityEvent(
            id=ActivityEventId(str(uuid4())),
            workspace_id=workspace_id,
            kind=kind,
            created_at=now,
            actor_subject=actor_subject,
            object_type=object_type,
            object_sync_id=object_sync_id,
            details=dict(details or {}),
        )
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO activity_events(
                    id, workspace_id, meeting_id, event_kind, object_type,
                    object_sync_id, actor_subject, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.id),
                    str(workspace_id),
                    meeting_id,
                    kind.value,
                    object_type,
                    str(object_sync_id) if object_sync_id else None,
                    actor_subject,
                    json.dumps(event.details, ensure_ascii=False, sort_keys=True),
                    now.isoformat(),
                ),
            )
        return event

    def recent_activity(
        self,
        workspace_id: WorkspaceId,
        *,
        limit: int = DEFAULT_ACTIVITY_LIMIT,
    ) -> tuple[ActivityEvent, ...]:
        """Return the newest activity for one workspace."""

        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM activity_events
                WHERE workspace_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (str(workspace_id), max(1, limit)),
            ).fetchall()
        return tuple(_map_activity(row) for row in rows)


def _comment_exists(connection: sqlite3.Connection, comment_id: CommentId) -> bool:
    row = connection.execute(
        "SELECT 1 FROM comments WHERE id = ?",
        (str(comment_id),),
    ).fetchone()
    return row is not None


def _map_comment(row: sqlite3.Row) -> Comment:
    parent = row["parent_id"]
    sync_id = row["sync_id"]
    device = row["updated_by_device"]
    return Comment(
        id=CommentId(str(row["id"])),
        workspace_id=WorkspaceId(str(row["workspace_id"])),
        target_type=str(row["target_type"]),
        target_sync_id=SyncId(str(row["target_sync_id"])),
        body=str(row["body"]),
        author_subject=str(row["author_subject"] or "unknown"),
        created_at=parse_timestamp(str(row["created_at"])),
        updated_at=parse_timestamp(str(row["updated_at"])),
        sync_id=SyncId(str(sync_id)) if sync_id else None,
        parent_id=CommentId(str(parent)) if parent else None,
        updated_by_device=DeviceId(str(device)) if device else None,
    )


def _map_activity(row: sqlite3.Row) -> ActivityEvent:
    object_sync_id = row["object_sync_id"]
    device = row["updated_by_device"]
    return ActivityEvent(
        id=ActivityEventId(str(row["id"])),
        workspace_id=WorkspaceId(str(row["workspace_id"])),
        kind=ActivityKind(str(row["event_kind"])),
        created_at=parse_timestamp(str(row["created_at"])),
        actor_subject=str(row["actor_subject"]) if row["actor_subject"] else None,
        object_type=str(row["object_type"]) if row["object_type"] else None,
        object_sync_id=SyncId(str(object_sync_id)) if object_sync_id else None,
        details=_details(row["details_json"]),
        updated_by_device=DeviceId(str(device)) if device else None,
    )


def _details(raw: object) -> dict[str, str]:
    try:
        parsed = json.loads(str(raw or "{}"))
    except ValueError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items()}


__all__ = ["DEFAULT_ACTIVITY_LIMIT", "SqliteCollaborationStore"]
