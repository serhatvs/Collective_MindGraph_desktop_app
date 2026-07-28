"""Versioned import and export for canonical local data."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from collective_mindgraph.domain import (
    KnowledgeNodeKind,
    MeetingId,
    MeetingStatus,
    RelationshipKind,
)

from .sqlite_database import SqliteDatabase

FORMAT_VERSION = 4

_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "meetings": ("id", "title", "status", "input_device", "created_at", "updated_at"),
    "recordings": (
        "id",
        "meeting_id",
        "source_uri",
        "duration_seconds",
        "input_device",
        "storage_status",
        "keep_audio",
        "deleted_at",
        "captured_at",
    ),
    "transcripts": (
        "id",
        "meeting_id",
        "conversation_id",
        "provider",
        "language",
        "raw_text",
        "corrected_text",
        "confidence",
        "diagnostics_json",
        "created_at",
        "updated_at",
    ),
    "transcript_segments": (
        "id",
        "transcript_id",
        "position",
        "start_seconds",
        "end_seconds",
        "speaker_label",
        "raw_text",
        "corrected_text",
        "confidence",
        "speaker_confidence",
        "overlaps_speech",
        "notes_json",
        "diagnostics_json",
    ),
    "evidence_references": (
        "id",
        "meeting_id",
        "segment_id",
        "start_seconds",
        "end_seconds",
        "text_preview",
        "confidence",
        "extractor",
        "created_at",
    ),
    "insights": (
        "id",
        "meeting_id",
        "kind",
        "title",
        "body",
        "review",
        "evidence_id",
        "confidence",
        "edited_by_user",
        "needs_review",
        "attributes_json",
        "created_at",
        "updated_at",
    ),
    "knowledge_nodes": (
        "id",
        "meeting_id",
        "kind",
        "title",
        "body",
        "evidence_id",
        "attributes_json",
        "created_at",
        "updated_at",
    ),
    "knowledge_edges": (
        "id",
        "source_id",
        "target_id",
        "kind",
        "evidence_id",
        "confidence",
        "attributes_json",
        "created_at",
    ),
    "embeddings": (
        "id",
        "node_id",
        "evidence_id",
        "vector_json",
        "text_chunk",
        "dimension",
        "created_at",
    ),
    "processing_jobs": (
        "id",
        "meeting_id",
        "recording_id",
        "parent_job_id",
        "result_transcript_id",
        "kind",
        "status",
        "progress",
        "message",
        "error",
        "retryable",
        "attributes_json",
        "created_at",
        "updated_at",
    ),
}


class SqliteDataExchange:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def export(self, meeting_id: MeetingId | None = None) -> dict[str, object]:
        with self._database.connect() as connection:
            tables: dict[str, list[dict[str, object]]] = {}
            for table in _TABLE_COLUMNS:
                rows = _select_rows(connection, table, meeting_id)
                tables[table] = [dict(row) for row in rows]
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
            return self._import_graph_export(payload)
        version = payload.get("format_version")
        if version not in {3, FORMAT_VERSION}:
            raise ValueError(f"Unsupported export format_version: {version!r}.")
        tables = payload.get("tables")
        if not isinstance(tables, dict):
            raise ValueError("Export payload must contain a tables object.")
        counts: dict[str, int] = {}
        with self._database.connect() as connection:
            for table, columns in _TABLE_COLUMNS.items():
                raw_rows = tables.get(table, [])
                if not isinstance(raw_rows, list):
                    raise ValueError(f"Export table {table} must be a list.")
                imported = 0
                for raw_row in raw_rows:
                    if not isinstance(raw_row, dict):
                        raise ValueError(f"Export table {table} contains an invalid row.")
                    values = [_import_value(table, column, raw_row) for column in columns]
                    placeholders = ", ".join("?" for _ in columns)
                    updates = ", ".join(
                        f"{column}=excluded.{column}" for column in columns if column != "id"
                    )
                    connection.execute(
                        f"""
                        INSERT INTO {table} ({", ".join(columns)})
                        VALUES ({placeholders})
                        ON CONFLICT(id) DO UPDATE SET {updates}
                        """,
                        values,
                    )
                    imported += 1
                counts[table] = imported
        return counts

    def _import_graph_export(self, payload: dict[str, object]) -> dict[str, int]:
        session = payload.get("session")
        session_data = session if isinstance(session, dict) else {}
        graph = payload.get("v2_production_graph")
        graph_data = graph if isinstance(graph, dict) else {}
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        references = graph_data.get("source_references", [])
        now = datetime.now(tz=UTC).isoformat()
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO meetings (title, status, input_device, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    f"[Imported] {session_data.get('title') or 'Imported Meeting'}",
                    MeetingStatus.READY.value,
                    session_data.get("device_id"),
                    now,
                    now,
                ),
            )
            meeting_id = int(cursor.lastrowid)
            evidence_ids: set[str] = set()
            for item in references if isinstance(references, list) else []:
                if not isinstance(item, dict):
                    continue
                evidence_id = str(item.get("id") or uuid4())
                evidence_ids.add(evidence_id)
                segment_id = item.get("segment_id") or item.get("source_segment_id")
                if (
                    segment_id
                    and connection.execute(
                        "SELECT 1 FROM transcript_segments WHERE id = ?",
                        (str(segment_id),),
                    ).fetchone()
                    is None
                ):
                    segment_id = None
                connection.execute(
                    """
                    INSERT OR REPLACE INTO evidence_references (
                        id, meeting_id, segment_id, start_seconds, end_seconds,
                        text_preview, confidence, extractor, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evidence_id,
                        meeting_id,
                        segment_id,
                        item.get("timestamp_start", item.get("start_time")),
                        item.get("timestamp_end", item.get("end_time")),
                        item.get("text_preview", item.get("source_text_preview")),
                        item.get("confidence"),
                        item.get("extractor_model", "import"),
                        item.get("created_at") or now,
                    ),
                )
            node_ids: set[str] = set()
            for item in nodes if isinstance(nodes, list) else []:
                if not isinstance(item, dict):
                    continue
                node_id = str(item.get("id") or uuid4())
                node_ids.add(node_id)
                attributes = _object(item.get("metadata_json"))
                evidence_id = _known_id(item.get("source_reference_id"), evidence_ids)
                title = str(item.get("title") or attributes.get("title") or "")
                body = str(
                    item.get("text_content")
                    or attributes.get("text")
                    or attributes.get("decision")
                    or title
                )
                attributes["review"] = _review(attributes)
                connection.execute(
                    """
                    INSERT OR REPLACE INTO knowledge_nodes (
                        id, meeting_id, kind, title, body, evidence_id,
                        attributes_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node_id,
                        meeting_id,
                        _node_kind(item.get("type")),
                        title or body,
                        body,
                        evidence_id,
                        json.dumps(attributes, ensure_ascii=False),
                        item.get("created_at") or now,
                        item.get("updated_at") or item.get("created_at") or now,
                    ),
                )
            imported_edges = 0
            for item in edges if isinstance(edges, list) else []:
                if not isinstance(item, dict):
                    continue
                source_id = str(item.get("source_node_id") or "")
                target_id = str(item.get("target_node_id") or "")
                if source_id not in node_ids or target_id not in node_ids:
                    continue
                connection.execute(
                    """
                    INSERT OR REPLACE INTO knowledge_edges (
                        id, source_id, target_id, kind, evidence_id,
                        confidence, attributes_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(item.get("id") or uuid4()),
                        source_id,
                        target_id,
                        _relationship_kind(item.get("edge_type")),
                        _known_id(item.get("source_reference_id"), evidence_ids),
                        float(item.get("confidence") or 1.0),
                        json.dumps(_object(item.get("metadata_json")), ensure_ascii=False),
                        item.get("created_at") or now,
                    ),
                )
                imported_edges += 1
        return {
            "meetings": 1,
            "evidence_references": len(evidence_ids),
            "knowledge_nodes": len(node_ids),
            "knowledge_edges": imported_edges,
        }


def _select_rows(connection, table: str, meeting_id: MeetingId | None):
    if meeting_id is None:
        return connection.execute(f"SELECT * FROM {table}").fetchall()
    direct = {
        "meetings": "id",
        "recordings": "meeting_id",
        "transcripts": "meeting_id",
        "evidence_references": "meeting_id",
        "insights": "meeting_id",
        "knowledge_nodes": "meeting_id",
        "processing_jobs": "meeting_id",
    }
    if table in direct:
        return connection.execute(
            f"SELECT * FROM {table} WHERE {direct[table]} = ?",
            (int(meeting_id),),
        ).fetchall()
    if table == "transcript_segments":
        return connection.execute(
            """
            SELECT transcript_segments.* FROM transcript_segments
            JOIN transcripts ON transcripts.id = transcript_segments.transcript_id
            WHERE transcripts.meeting_id = ?
            """,
            (int(meeting_id),),
        ).fetchall()
    if table == "knowledge_edges":
        return connection.execute(
            """
            SELECT knowledge_edges.* FROM knowledge_edges
            JOIN knowledge_nodes ON knowledge_nodes.id = knowledge_edges.source_id
            WHERE knowledge_nodes.meeting_id = ?
            """,
            (int(meeting_id),),
        ).fetchall()
    return connection.execute(
        """
        SELECT embeddings.* FROM embeddings
        JOIN knowledge_nodes ON knowledge_nodes.id = embeddings.node_id
        WHERE knowledge_nodes.meeting_id = ?
        """,
        (int(meeting_id),),
    ).fetchall()


def _object(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _import_value(
    table: str,
    column: str,
    row: dict[str, object],
) -> object:
    if column in row:
        return row[column]
    defaults: dict[tuple[str, str], object] = {
        ("recordings", "storage_status"): "managed",
        ("recordings", "keep_audio"): 0,
        ("processing_jobs", "retryable"): 0,
    }
    return defaults.get((table, column))


def _known_id(value: object, known: set[str]) -> str | None:
    candidate = str(value) if value else None
    return candidate if candidate in known else None


def _review(attributes: dict[str, object]) -> str:
    current = str(attributes.get("review") or attributes.get("review_status") or "pending")
    return {"approved": "accepted", "completed": "accepted", "edited": "accepted"}.get(
        current.casefold(),
        current.casefold()
        if current.casefold() in {"pending", "accepted", "rejected"}
        else "pending",
    )


def _node_kind(value: object) -> str:
    normalized = str(value or "entity").casefold()
    if normalized == "session":
        normalized = "meeting"
    allowed = {item.value for item in KnowledgeNodeKind}
    return normalized if normalized in allowed else KnowledgeNodeKind.ENTITY.value


def _relationship_kind(value: object) -> str:
    normalized = str(value or "related_to").casefold()
    mapping = {
        "session_has_segment": "contains",
        "segment_mentions_topic": "mentions",
        "segment_creates_task": "creates",
        "segment_supports_decision": "supports",
        "task_assigned_to_person": "assigned_to",
        "node_merged_into": "merged_into",
    }
    normalized = mapping.get(normalized, normalized)
    allowed = {item.value for item in RelationshipKind}
    return normalized if normalized in allowed else RelationshipKind.RELATED_TO.value
