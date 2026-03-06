"""Repository layer for SQLite persistence."""

from __future__ import annotations

import sqlite3

from .database import Database
from .models import AppSummary, GraphNode, GraphNodeDraft, Session, Snapshot, Transcript, TranscriptDraft


def _session_from_row(row: sqlite3.Row) -> Session:
    return Session(
        id=row["id"],
        title=row["title"],
        device_id=row["device_id"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _transcript_from_row(row: sqlite3.Row) -> Transcript:
    return Transcript(
        id=row["id"],
        session_id=row["session_id"],
        text=row["text"],
        confidence=row["confidence"],
        created_at=row["created_at"],
    )


def _graph_node_from_row(row: sqlite3.Row) -> GraphNode:
    return GraphNode(
        id=row["id"],
        session_id=row["session_id"],
        transcript_id=row["transcript_id"],
        parent_node_id=row["parent_node_id"],
        branch_type=row["branch_type"],
        branch_slot=row["branch_slot"],
        node_text=row["node_text"],
        override_reason=row["override_reason"],
        created_at=row["created_at"],
    )


def _snapshot_from_row(row: sqlite3.Row) -> Snapshot:
    return Snapshot(
        id=row["id"],
        session_id=row["session_id"],
        node_count=row["node_count"],
        hash_sha256=row["hash_sha256"],
        created_at=row["created_at"],
    )


class SessionRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, title: str, device_id: str, status: str, timestamp: str) -> Session:
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO sessions (title, device_id, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, device_id, status, timestamp, timestamp),
            )
            session_id = int(cursor.lastrowid)
            row = connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise RuntimeError("Failed to create session.")
        return _session_from_row(row)

    def get(self, session_id: int) -> Session | None:
        with self._database.connect() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return _session_from_row(row) if row else None

    def list(self, query: str = "") -> list[Session]:
        sql = "SELECT * FROM sessions"
        parameters: tuple[str, ...] = ()
        normalized = query.strip()
        if normalized:
            like_query = f"%{normalized}%"
            sql += " WHERE title LIKE ? OR device_id LIKE ?"
            parameters = (like_query, like_query)
        sql += " ORDER BY updated_at DESC, created_at DESC, id DESC"
        with self._database.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [_session_from_row(row) for row in rows]

    def delete(self, session_id: int) -> bool:
        with self._database.connect() as connection:
            cursor = connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0

    def touch(self, session_id: int, updated_at: str) -> Session | None:
        with self._database.connect() as connection:
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (updated_at, session_id),
            )
            row = connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return _session_from_row(row) if row else None

    def summary_counts(self) -> AppSummary:
        with self._database.connect() as connection:
            counts = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM sessions) AS total_sessions,
                    (SELECT COUNT(*) FROM sessions WHERE status = 'active') AS active_sessions,
                    (SELECT COUNT(*) FROM transcripts) AS total_transcripts,
                    (SELECT COUNT(*) FROM graph_nodes) AS total_nodes,
                    (SELECT COUNT(*) FROM snapshots) AS total_snapshots
                """
            ).fetchone()
        if counts is None:
            raise RuntimeError("Failed to load summary counts.")
        return AppSummary(
            total_sessions=counts["total_sessions"],
            active_sessions=counts["active_sessions"],
            total_transcripts=counts["total_transcripts"],
            total_nodes=counts["total_nodes"],
            total_snapshots=counts["total_snapshots"],
        )


class TranscriptRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create_many(self, session_id: int, drafts: list[TranscriptDraft]) -> list[Transcript]:
        created: list[Transcript] = []
        with self._database.connect() as connection:
            for draft in drafts:
                cursor = connection.execute(
                    """
                    INSERT INTO transcripts (session_id, text, confidence, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session_id, draft.text, draft.confidence, draft.created_at),
                )
                created.append(
                    Transcript(
                        id=int(cursor.lastrowid),
                        session_id=session_id,
                        text=draft.text,
                        confidence=draft.confidence,
                        created_at=draft.created_at,
                    )
                )
        return created

    def list_by_session(self, session_id: int) -> list[Transcript]:
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM transcripts WHERE session_id = ? ORDER BY created_at ASC, id ASC",
                (session_id,),
            ).fetchall()
        return [_transcript_from_row(row) for row in rows]


class GraphNodeRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create_many(self, session_id: int, drafts: list[GraphNodeDraft]) -> list[GraphNode]:
        created: list[GraphNode] = []
        with self._database.connect() as connection:
            for draft in drafts:
                cursor = connection.execute(
                    """
                    INSERT INTO graph_nodes (
                        session_id,
                        transcript_id,
                        parent_node_id,
                        branch_type,
                        branch_slot,
                        node_text,
                        override_reason,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        draft.transcript_id,
                        draft.parent_node_id,
                        draft.branch_type,
                        draft.branch_slot,
                        draft.node_text,
                        draft.override_reason,
                        draft.created_at,
                    ),
                )
                created.append(
                    GraphNode(
                        id=int(cursor.lastrowid),
                        session_id=session_id,
                        transcript_id=draft.transcript_id,
                        parent_node_id=draft.parent_node_id,
                        branch_type=draft.branch_type,
                        branch_slot=draft.branch_slot,
                        node_text=draft.node_text,
                        override_reason=draft.override_reason,
                        created_at=draft.created_at,
                    )
                )
        return created

    def list_by_session(self, session_id: int) -> list[GraphNode]:
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM graph_nodes WHERE session_id = ? ORDER BY created_at ASC, id ASC",
                (session_id,),
            ).fetchall()
        return [_graph_node_from_row(row) for row in rows]


class SnapshotRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, session_id: int, node_count: int, hash_sha256: str, created_at: str) -> Snapshot:
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO snapshots (session_id, node_count, hash_sha256, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, node_count, hash_sha256, created_at),
            )
            snapshot_id = int(cursor.lastrowid)
            row = connection.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        if row is None:
            raise RuntimeError("Failed to create snapshot.")
        return _snapshot_from_row(row)

    def list_by_session(self, session_id: int) -> list[Snapshot]:
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM snapshots WHERE session_id = ? ORDER BY created_at DESC, id DESC",
                (session_id,),
            ).fetchall()
        return [_snapshot_from_row(row) for row in rows]

    def replace_for_session(
        self,
        session_id: int,
        node_count: int,
        hash_sha256: str,
        created_at: str,
    ) -> list[Snapshot]:
        with self._database.connect() as connection:
            connection.execute("DELETE FROM snapshots WHERE session_id = ?", (session_id,))
            connection.execute(
                """
                INSERT INTO snapshots (session_id, node_count, hash_sha256, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, node_count, hash_sha256, created_at),
            )
        return self.list_by_session(session_id)
