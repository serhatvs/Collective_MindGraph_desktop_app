"""SQLite knowledge-node and relationship persistence."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from collective_mindgraph.application.pagination import Page, PageRequest
from collective_mindgraph.domain import (
    EdgeId,
    EvidenceId,
    EvidenceReference,
    KnowledgeEdge,
    KnowledgeNode,
    KnowledgeNodeId,
    KnowledgeNodeKind,
    MeetingId,
    RelationshipKind,
    ReviewDecision,
    SegmentId,
)

from .row_mapping import dump_json, load_object, parse_timestamp
from .sqlite_database import SqliteDatabase
from .sqlite_pagination import decode_offset, encode_offset


class SqliteKnowledgeGraphStore:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def list_nodes(
        self,
        request: PageRequest,
        *,
        query: str = "",
        meeting_id: MeetingId | None = None,
        kind: KnowledgeNodeKind | None = None,
        review: ReviewDecision | None = None,
    ) -> Page[KnowledgeNode]:
        clauses: list[str] = []
        parameters: list[object] = []
        normalized = query.strip()
        if normalized:
            clauses.append("(title LIKE ? OR body LIKE ?)")
            parameters.extend((f"%{normalized}%", f"%{normalized}%"))
        if meeting_id is not None:
            clauses.append("meeting_id = ?")
            parameters.append(int(meeting_id))
        if kind is not None:
            clauses.append("kind = ?")
            parameters.append(kind.value)
        if review is not None:
            review_clause = (
                "("
                "COALESCE(json_extract(attributes_json, '$.review'), 'accepted') = ? "
                "OR COALESCE(json_extract(attributes_json, '$.needs_review'), 0) = 1"
                ")"
                if review is ReviewDecision.PENDING
                else "COALESCE(json_extract(attributes_json, '$.review'), 'accepted') = ?"
            )
            clauses.append(review_clause)
            parameters.append(review.value)
        return self._list(
            request,
            table="knowledge_nodes",
            mapper=self._map_node,
            clauses=clauses,
            parameters=parameters,
        )

    def list_edges(self, request: PageRequest, *, query: str = "") -> Page[KnowledgeEdge]:
        clauses: list[str] = []
        parameters: list[object] = []
        normalized = query.strip()
        if normalized:
            pattern = f"%{normalized}%"
            clauses.append("(source_id LIKE ? OR target_id LIKE ? OR kind LIKE ?)")
            parameters.extend((pattern, pattern, pattern))
        return self._list(
            request,
            table="knowledge_edges",
            mapper=self._map_edge,
            clauses=clauses,
            parameters=parameters,
        )

    def get_node(self, node_id: KnowledgeNodeId) -> KnowledgeNode | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_nodes WHERE id = ?",
                (str(node_id),),
            ).fetchone()
        return self._map_node(row) if row is not None else None

    def related_nodes(
        self,
        node_id: KnowledgeNodeId,
        *,
        include_rejected: bool = False,
    ) -> tuple[tuple[KnowledgeEdge, KnowledgeNode], ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM knowledge_edges
                WHERE source_id = ? OR target_id = ?
                ORDER BY created_at, id
                """,
                (str(node_id), str(node_id)),
            ).fetchall()
            result: list[tuple[KnowledgeEdge, KnowledgeNode]] = []
            for row in rows:
                edge = self._map_edge(row)
                related_id = edge.target_id if edge.source_id == node_id else edge.source_id
                node_row = connection.execute(
                    "SELECT * FROM knowledge_nodes WHERE id = ?",
                    (str(related_id),),
                ).fetchone()
                if node_row is None:
                    continue
                node = self._map_node(node_row)
                if not include_rejected and node.attributes.get("review") == "rejected":
                    continue
                result.append((edge, node))
        return tuple(result)

    def get_evidence(self, evidence_id: EvidenceId) -> EvidenceReference | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM evidence_references WHERE id = ?",
                (str(evidence_id),),
            ).fetchone()
        return self._map_evidence(row) if row is not None else None

    def list_evidence(
        self,
        request: PageRequest,
        *,
        meeting_id: MeetingId,
    ) -> Page[EvidenceReference]:
        offset = decode_offset(request.cursor)
        with self._database.connect() as connection:
            total = int(
                connection.execute(
                    "SELECT COUNT(*) FROM evidence_references WHERE meeting_id = ?",
                    (int(meeting_id),),
                ).fetchone()[0]
            )
            rows = connection.execute(
                """
                SELECT * FROM evidence_references
                WHERE meeting_id = ?
                ORDER BY start_seconds, created_at, id
                LIMIT ? OFFSET ?
                """,
                (int(meeting_id), request.limit, offset),
            ).fetchall()
        items = tuple(self._map_evidence(row) for row in rows)
        return Page(items, total, encode_offset(offset + len(items), total))

    @staticmethod
    def _map_evidence(row: sqlite3.Row) -> EvidenceReference:
        return EvidenceReference(
            id=EvidenceId(str(row["id"])),
            meeting_id=MeetingId(int(row["meeting_id"])),
            segment_id=SegmentId(str(row["segment_id"])) if row["segment_id"] else None,
            start_seconds=float(row["start_seconds"]) if row["start_seconds"] is not None else None,
            end_seconds=float(row["end_seconds"]) if row["end_seconds"] is not None else None,
            text_preview=str(row["text_preview"]) if row["text_preview"] else None,
            confidence=float(row["confidence"]) if row["confidence"] is not None else None,
            extractor=str(row["extractor"]) if row["extractor"] else None,
            created_at=parse_timestamp(str(row["created_at"])),
        )

    def save_evidence(self, evidence: EvidenceReference) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO evidence_references (
                    id, meeting_id, segment_id, start_seconds, end_seconds,
                    text_preview, confidence, extractor, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    meeting_id = excluded.meeting_id,
                    segment_id = excluded.segment_id,
                    start_seconds = excluded.start_seconds,
                    end_seconds = excluded.end_seconds,
                    text_preview = excluded.text_preview,
                    confidence = excluded.confidence,
                    extractor = excluded.extractor
                """,
                (
                    str(evidence.id),
                    int(evidence.meeting_id),
                    str(evidence.segment_id) if evidence.segment_id else None,
                    evidence.start_seconds,
                    evidence.end_seconds,
                    evidence.text_preview,
                    evidence.confidence,
                    evidence.extractor,
                    evidence.created_at.isoformat(),
                ),
            )

    def save_node(self, node: KnowledgeNode) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO knowledge_nodes (
                    id, meeting_id, kind, title, body, evidence_id,
                    attributes_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    meeting_id = excluded.meeting_id,
                    kind = excluded.kind,
                    title = excluded.title,
                    body = excluded.body,
                    evidence_id = excluded.evidence_id,
                    attributes_json = excluded.attributes_json,
                    updated_at = excluded.updated_at
                """,
                (
                    str(node.id),
                    int(node.meeting_id) if node.meeting_id is not None else None,
                    node.kind.value,
                    node.title,
                    node.body,
                    str(node.evidence_id) if node.evidence_id else None,
                    dump_json(node.attributes),
                    node.created_at.isoformat(),
                    node.updated_at.isoformat(),
                ),
            )

    def save_edge(self, edge: KnowledgeEdge) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO knowledge_edges (
                    id, source_id, target_id, kind, evidence_id,
                    confidence, attributes_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_id = excluded.source_id,
                    target_id = excluded.target_id,
                    kind = excluded.kind,
                    evidence_id = excluded.evidence_id,
                    confidence = excluded.confidence,
                    attributes_json = excluded.attributes_json
                """,
                (
                    str(edge.id),
                    str(edge.source_id),
                    str(edge.target_id),
                    edge.kind.value,
                    str(edge.evidence_id) if edge.evidence_id else None,
                    edge.confidence,
                    dump_json(edge.attributes),
                    edge.created_at.isoformat(),
                ),
            )

    def review_node(
        self,
        node_id: KnowledgeNodeId,
        *,
        decision: ReviewDecision,
        title: str | None,
        body: str | None,
        now: datetime,
    ) -> KnowledgeNode | None:
        node = self.get_node(node_id)
        if node is None:
            return None
        attributes = {
            **node.attributes,
            "review": decision.value,
            "needs_review": False,
            "edited_by_user": bool(
                title is not None or body is not None or node.attributes.get("edited_by_user")
            ),
        }
        updated = KnowledgeNode(
            id=node.id,
            meeting_id=node.meeting_id,
            kind=node.kind,
            title=title if title is not None else node.title,
            body=body if body is not None else node.body,
            evidence_id=node.evidence_id,
            attributes=attributes,
            created_at=node.created_at,
            updated_at=now,
        )
        self.save_node(updated)
        return updated

    def mark_meeting_nodes_for_review(
        self,
        meeting_id: MeetingId,
        *,
        now: datetime,
    ) -> int:
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_nodes WHERE meeting_id = ?",
                (int(meeting_id),),
            ).fetchall()
        changed = 0
        for row in rows:
            node = self._map_node(row)
            if node.attributes.get("review") == ReviewDecision.REJECTED.value:
                continue
            self.save_node(
                KnowledgeNode(
                    id=node.id,
                    meeting_id=node.meeting_id,
                    kind=node.kind,
                    title=node.title,
                    body=node.body,
                    evidence_id=node.evidence_id,
                    attributes={**node.attributes, "needs_review": True},
                    created_at=node.created_at,
                    updated_at=now,
                )
            )
            changed += 1
        return changed

    def count_nodes(self) -> int:
        with self._database.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM knowledge_nodes").fetchone()[0])

    def _list(
        self,
        request: PageRequest,
        *,
        table: str,
        mapper,
        clauses: list[str],
        parameters: list[object],
    ):
        if table not in {"knowledge_nodes", "knowledge_edges"}:
            raise ValueError("Unsupported knowledge table.")
        offset = decode_offset(request.cursor)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._database.connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {table} {where}",
                    tuple(parameters),
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"""
                SELECT * FROM {table}
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (*parameters, request.limit, offset),
            ).fetchall()
        items = tuple(mapper(row) for row in rows)
        return Page(items, total, encode_offset(offset + len(items), total))

    @staticmethod
    def _map_node(row: sqlite3.Row) -> KnowledgeNode:
        return KnowledgeNode(
            id=KnowledgeNodeId(str(row["id"])),
            meeting_id=MeetingId(int(row["meeting_id"])) if row["meeting_id"] else None,
            kind=KnowledgeNodeKind(str(row["kind"])),
            title=str(row["title"]),
            body=str(row["body"]),
            evidence_id=EvidenceId(str(row["evidence_id"])) if row["evidence_id"] else None,
            attributes=load_object(row["attributes_json"]),
            created_at=parse_timestamp(str(row["created_at"])),
            updated_at=parse_timestamp(str(row["updated_at"])),
        )

    @staticmethod
    def _map_edge(row: sqlite3.Row) -> KnowledgeEdge:
        return KnowledgeEdge(
            id=EdgeId(str(row["id"])),
            source_id=KnowledgeNodeId(str(row["source_id"])),
            target_id=KnowledgeNodeId(str(row["target_id"])),
            kind=RelationshipKind(str(row["kind"])),
            evidence_id=EvidenceId(str(row["evidence_id"])) if row["evidence_id"] else None,
            confidence=float(row["confidence"]),
            attributes=load_object(row["attributes_json"]),
            created_at=parse_timestamp(str(row["created_at"])),
        )
