"""Versioned import and export for canonical local data."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from collective_mindgraph.domain import (
    MeetingId,
    MeetingStatus,
)

from .data_exchange_mapping import (
    node_kind as _node_kind,
)
from .data_exchange_mapping import (
    object_value as _object,
)
from .data_exchange_mapping import (
    raw_import_value as _raw_import_value,
)
from .data_exchange_mapping import (
    relationship_kind as _relationship_kind,
)
from .data_exchange_mapping import (
    review_value as _review,
)
from .data_exchange_mapping import (
    safe_import_value as _import_value,
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
        try:
            with self._database.connect() as connection:
                connection.execute("PRAGMA defer_foreign_keys = ON")
                existing_rows = _validate_canonical_import(connection, tables)
                for table, columns in _TABLE_COLUMNS.items():
                    raw_rows = tables.get(table, [])
                    imported = 0
                    for raw_row in raw_rows:
                        if raw_row["id"] in existing_rows[table]:
                            continue
                        values = [_import_value(table, column, raw_row) for column in columns]
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
        except sqlite3.IntegrityError as exc:
            raise ValueError("Export payload violates canonical data constraints.") from exc
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
            evidence_id_map: dict[str, str] = {}
            for item in references if isinstance(references, list) else []:
                if not isinstance(item, dict):
                    continue
                external_id = str(item.get("id") or uuid4())
                if external_id in evidence_id_map:
                    continue
                evidence_id = _available_identifier(
                    connection,
                    "evidence_references",
                    external_id,
                    evidence_ids,
                )
                evidence_id_map[external_id] = evidence_id
                evidence_ids.add(evidence_id)
                connection.execute(
                    """
                    INSERT INTO evidence_references (
                        id, meeting_id, segment_id, start_seconds, end_seconds,
                        text_preview, confidence, extractor, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evidence_id,
                        meeting_id,
                        None,
                        item.get("timestamp_start", item.get("start_time")),
                        item.get("timestamp_end", item.get("end_time")),
                        item.get("text_preview", item.get("source_text_preview")),
                        item.get("confidence"),
                        item.get("extractor_model", "import"),
                        item.get("created_at") or now,
                    ),
                )
            node_ids: set[str] = set()
            node_id_map: dict[str, str] = {}
            for item in nodes if isinstance(nodes, list) else []:
                if not isinstance(item, dict):
                    continue
                external_id = str(item.get("id") or uuid4())
                if external_id in node_id_map:
                    continue
                node_id = _available_identifier(
                    connection,
                    "knowledge_nodes",
                    external_id,
                    node_ids,
                )
                node_id_map[external_id] = node_id
                node_ids.add(node_id)
                attributes = _object(item.get("metadata_json"))
                evidence_id = evidence_id_map.get(str(item.get("source_reference_id") or ""))
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
                    INSERT INTO knowledge_nodes (
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
            edge_ids: set[str] = set()
            for item in edges if isinstance(edges, list) else []:
                if not isinstance(item, dict):
                    continue
                source_id = node_id_map.get(str(item.get("source_node_id") or ""))
                target_id = node_id_map.get(str(item.get("target_node_id") or ""))
                if source_id is None or target_id is None:
                    continue
                edge_id = _available_identifier(
                    connection,
                    "knowledge_edges",
                    str(item.get("id") or uuid4()),
                    edge_ids,
                )
                edge_ids.add(edge_id)
                connection.execute(
                    """
                    INSERT INTO knowledge_edges (
                        id, source_id, target_id, kind, evidence_id,
                        confidence, attributes_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        edge_id,
                        source_id,
                        target_id,
                        _relationship_kind(item.get("edge_type")),
                        evidence_id_map.get(str(item.get("source_reference_id") or "")),
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


def _validate_canonical_import(
    connection: sqlite3.Connection,
    tables: dict[object, object],
) -> dict[str, set[object]]:
    existing_rows: dict[str, set[object]] = {table: set() for table in _TABLE_COLUMNS}
    conflicts: list[str] = []
    for table, columns in _TABLE_COLUMNS.items():
        raw_rows = tables.get(table, [])
        if not isinstance(raw_rows, list):
            raise ValueError(f"Export table {table} must be a list.")
        seen: set[object] = set()
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                raise ValueError(f"Export table {table} contains an invalid row.")
            identifier = raw_row.get("id")
            if identifier is None:
                raise ValueError(f"Export table {table} contains a row without an id.")
            if identifier in seen:
                raise ValueError(f"Export table {table} contains duplicate id {identifier!r}.")
            seen.add(identifier)
            existing = connection.execute(
                f"SELECT {', '.join(columns)} FROM {table} WHERE id = ?",
                (identifier,),
            ).fetchone()
            if existing is None:
                continue
            incoming = tuple(_raw_import_value(table, column, raw_row) for column in columns)
            safe_incoming = tuple(_import_value(table, column, raw_row) for column in columns)
            current = tuple(existing[column] for column in columns)
            if current != incoming and current != safe_incoming:
                conflicts.append(f"{table}:{identifier}")
            else:
                existing_rows[table].add(identifier)
    if conflicts:
        preview = ", ".join(conflicts[:5])
        raise ValueError(
            f"Export conflicts with existing canonical records{': ' + preview if preview else ''}."
        )
    return existing_rows


def _available_identifier(
    connection: sqlite3.Connection,
    table: str,
    preferred: str,
    reserved: set[str],
) -> str:
    if table not in {"evidence_references", "knowledge_nodes", "knowledge_edges"}:
        raise ValueError("Unsupported legacy import identifier table.")
    candidate = preferred
    while (
        candidate in reserved
        or connection.execute(
            f"SELECT 1 FROM {table} WHERE id = ?",
            (candidate,),
        ).fetchone()
    ):
        candidate = str(uuid4())
    return candidate
