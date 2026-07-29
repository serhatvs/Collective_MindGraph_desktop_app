"""Import the historical graph export without mutating existing identifiers."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from collective_mindgraph.domain import MeetingStatus

from .data_exchange_mapping import (
    node_kind,
    object_value,
    relationship_kind,
    review_value,
)
from .sqlite_database import SqliteDatabase


def import_legacy_graph_export(
    database: SqliteDatabase,
    payload: dict[str, object],
) -> dict[str, int]:
    session = payload.get("session")
    session_data = session if isinstance(session, dict) else {}
    graph = payload.get("v2_production_graph")
    graph_data = graph if isinstance(graph, dict) else {}
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    references = graph_data.get("source_references", [])
    now = datetime.now(tz=UTC).isoformat()
    with database.connect() as connection:
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
        meeting_row_id = cursor.lastrowid
        if meeting_row_id is None:
            raise RuntimeError("Legacy meeting import did not create a row.")
        meeting_id = int(meeting_row_id)
        evidence_ids, evidence_id_map = _import_evidence(
            connection,
            meeting_id,
            references,
            now,
        )
        node_ids, node_id_map = _import_nodes(
            connection,
            meeting_id,
            nodes,
            evidence_id_map,
            now,
        )
        imported_edges = _import_edges(
            connection,
            edges,
            node_id_map,
            evidence_id_map,
            now,
        )
    return {
        "meetings": 1,
        "evidence_references": len(evidence_ids),
        "knowledge_nodes": len(node_ids),
        "knowledge_edges": imported_edges,
    }


def _import_evidence(
    connection: sqlite3.Connection,
    meeting_id: int,
    references: object,
    now: str,
) -> tuple[set[str], dict[str, str]]:
    evidence_ids: set[str] = set()
    identifier_map: dict[str, str] = {}
    for item in references if isinstance(references, list) else []:
        if not isinstance(item, dict):
            continue
        external_id = str(item.get("id") or uuid4())
        if external_id in identifier_map:
            continue
        evidence_id = _available_identifier(
            connection,
            "evidence_references",
            external_id,
            evidence_ids,
        )
        identifier_map[external_id] = evidence_id
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
    return evidence_ids, identifier_map


def _import_nodes(
    connection: sqlite3.Connection,
    meeting_id: int,
    nodes: object,
    evidence_id_map: dict[str, str],
    now: str,
) -> tuple[set[str], dict[str, str]]:
    node_ids: set[str] = set()
    identifier_map: dict[str, str] = {}
    for item in nodes if isinstance(nodes, list) else []:
        if not isinstance(item, dict):
            continue
        external_id = str(item.get("id") or uuid4())
        if external_id in identifier_map:
            continue
        node_id = _available_identifier(
            connection,
            "knowledge_nodes",
            external_id,
            node_ids,
        )
        identifier_map[external_id] = node_id
        node_ids.add(node_id)
        attributes = object_value(item.get("metadata_json"))
        evidence_id = evidence_id_map.get(str(item.get("source_reference_id") or ""))
        title = str(item.get("title") or attributes.get("title") or "")
        body = str(
            item.get("text_content")
            or attributes.get("text")
            or attributes.get("decision")
            or title
        )
        attributes["review"] = review_value(attributes)
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
                node_kind(item.get("type")),
                title or body,
                body,
                evidence_id,
                json.dumps(attributes, ensure_ascii=False),
                item.get("created_at") or now,
                item.get("updated_at") or item.get("created_at") or now,
            ),
        )
    return node_ids, identifier_map


def _import_edges(
    connection: sqlite3.Connection,
    edges: object,
    node_id_map: dict[str, str],
    evidence_id_map: dict[str, str],
    now: str,
) -> int:
    imported = 0
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
                relationship_kind(item.get("edge_type")),
                evidence_id_map.get(str(item.get("source_reference_id") or "")),
                float(item.get("confidence") or 1.0),
                json.dumps(object_value(item.get("metadata_json")), ensure_ascii=False),
                item.get("created_at") or now,
            ),
        )
        imported += 1
    return imported


def _available_identifier(
    connection: sqlite3.Connection,
    table: str,
    preferred: str,
    reserved: set[str],
) -> str:
    allowed_tables = {"evidence_references", "knowledge_nodes", "knowledge_edges"}
    if table not in allowed_tables:
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
