"""SQLite insight review persistence."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from collective_mindgraph.application.pagination import Page, PageRequest
from collective_mindgraph.domain import (
    EvidenceId,
    Insight,
    InsightId,
    InsightKind,
    MeetingId,
    ReviewDecision,
)

from .row_mapping import dump_json, load_object, parse_timestamp
from .sqlite_database import SqliteDatabase
from .sqlite_pagination import decode_offset, encode_offset


class SqliteInsightStore:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def save(self, insight: Insight) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO insights (
                    id, meeting_id, kind, title, body, review, evidence_id,
                    confidence, edited_by_user, needs_review, attributes_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    meeting_id = excluded.meeting_id,
                    kind = excluded.kind,
                    title = excluded.title,
                    body = excluded.body,
                    review = excluded.review,
                    evidence_id = excluded.evidence_id,
                    confidence = excluded.confidence,
                    edited_by_user = excluded.edited_by_user,
                    needs_review = excluded.needs_review,
                    attributes_json = excluded.attributes_json,
                    updated_at = excluded.updated_at
                """,
                (
                    str(insight.id),
                    int(insight.meeting_id),
                    insight.kind.value,
                    insight.title,
                    insight.body,
                    insight.review.value,
                    str(insight.evidence_id) if insight.evidence_id else None,
                    insight.confidence,
                    int(insight.edited_by_user),
                    int(insight.needs_review),
                    dump_json(insight.attributes),
                    insight.created_at.isoformat(),
                    insight.updated_at.isoformat(),
                ),
            )

    def get(self, insight_id: InsightId) -> Insight | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM insights WHERE id = ?",
                (str(insight_id),),
            ).fetchone()
        return self._map(row) if row is not None else None

    def list(
        self,
        request: PageRequest,
        *,
        meeting_id: MeetingId | None = None,
        review: ReviewDecision | None = None,
        query: str = "",
    ) -> Page[Insight]:
        clauses: list[str] = []
        parameters: list[object] = []
        if meeting_id is not None:
            clauses.append("meeting_id = ?")
            parameters.append(int(meeting_id))
        if review is not None:
            clauses.append(
                "(review = ? OR needs_review = 1)"
                if review is ReviewDecision.PENDING
                else "review = ?"
            )
            parameters.append(review.value)
        if query.strip():
            clauses.append("(title LIKE ? OR body LIKE ?)")
            pattern = f"%{query.strip()}%"
            parameters.extend((pattern, pattern))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        offset = decode_offset(request.cursor)
        with self._database.connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM insights {where}",
                    tuple(parameters),
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"""
                SELECT * FROM insights
                {where}
                ORDER BY updated_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (*parameters, request.limit, offset),
            ).fetchall()
        items = tuple(self._map(row) for row in rows)
        return Page(items, total, encode_offset(offset + len(items), total))

    def review(
        self,
        insight_id: InsightId,
        *,
        decision: ReviewDecision,
        title: str | None,
        body: str | None,
        now: datetime,
    ) -> Insight | None:
        existing = self.get(insight_id)
        if existing is None:
            return None
        next_title = title if title is not None else existing.title
        next_body = body if body is not None else existing.body
        edited = title is not None or body is not None or existing.edited_by_user
        with self._database.connect() as connection:
            connection.execute(
                """
                UPDATE insights
                SET title = ?, body = ?, review = ?, edited_by_user = ?,
                    needs_review = 0, updated_at = ?
                WHERE id = ?
                """,
                (
                    next_title,
                    next_body,
                    decision.value,
                    int(edited),
                    now.isoformat(),
                    str(insight_id),
                ),
            )
        return self.get(insight_id)

    def mark_meeting_insights_for_review(self, meeting_id: MeetingId, *, now: datetime) -> int:
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE insights
                SET needs_review = 1, updated_at = ?
                WHERE meeting_id = ? AND review != 'rejected'
                """,
                (now.isoformat(), int(meeting_id)),
            )
        return cursor.rowcount

    def pending_count(self) -> int:
        with self._database.connect() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM insights WHERE review = 'pending' OR needs_review = 1"
                ).fetchone()[0]
            )

    @staticmethod
    def _map(row: sqlite3.Row) -> Insight:
        return Insight(
            id=InsightId(str(row["id"])),
            meeting_id=MeetingId(int(row["meeting_id"])),
            kind=InsightKind(str(row["kind"])),
            title=str(row["title"]),
            body=str(row["body"]),
            review=ReviewDecision(str(row["review"])),
            evidence_id=EvidenceId(str(row["evidence_id"])) if row["evidence_id"] else None,
            confidence=float(row["confidence"]) if row["confidence"] is not None else None,
            edited_by_user=bool(row["edited_by_user"]),
            needs_review=bool(row["needs_review"]),
            attributes=load_object(row["attributes_json"]),
            created_at=parse_timestamp(str(row["created_at"])),
            updated_at=parse_timestamp(str(row["updated_at"])),
        )
