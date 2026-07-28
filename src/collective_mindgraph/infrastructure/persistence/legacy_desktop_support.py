"""Lookup and auxiliary table helpers for legacy desktop migration."""

from __future__ import annotations

import sqlite3

from .migration_support import normalized_timestamp, safe_json, table_exists

INSIGHT_KINDS = {
    "task",
    "decision",
    "topic",
    "person",
    "entity",
    "risk",
    "open_question",
    "follow_up",
}


def import_embeddings(
    source: sqlite3.Connection,
    destination: sqlite3.Connection,
) -> None:
    if not table_exists(source, "v2_embeddings"):
        return
    for row in source.execute("SELECT * FROM v2_embeddings").fetchall():
        node_id = str(row["node_id"])
        if not exists(destination, "knowledge_nodes", node_id):
            continue
        evidence_id = str(row["source_reference_id"]) if row["source_reference_id"] else None
        destination.execute(
            """
            INSERT OR IGNORE INTO embeddings(
                id, node_id, evidence_id, vector_json, text_chunk, dimension, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(row["id"]),
                node_id,
                (
                    evidence_id
                    if evidence_id and exists(destination, "evidence_references", evidence_id)
                    else None
                ),
                str(row["vector_json"]),
                str(row["text_chunk"]),
                int(row["dimension"]),
                normalized_timestamp(row["created_at"]),
            ),
        )


def import_jobs(
    source: sqlite3.Connection,
    destination: sqlite3.Connection,
) -> None:
    if not table_exists(source, "v2_jobs"):
        return
    for row in source.execute("SELECT * FROM v2_jobs").fetchall():
        destination.execute(
            """
            INSERT OR IGNORE INTO processing_jobs(
                id, kind, status, progress, message, error,
                attributes_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(row["id"]),
                str(row["type"]),
                str(row["status"]),
                int(row["progress"]),
                str(row["message"] or ""),
                str(row["error"]) if row["error"] else None,
                str(row["metadata_json"] or "{}"),
                normalized_timestamp(row["created_at"]),
                normalized_timestamp(row["updated_at"]),
            ),
        )


def resolve_meeting(
    destination: sqlite3.Connection,
    value: object,
) -> int | None:
    try:
        meeting_id = int(str(value))
    except (TypeError, ValueError):
        row = destination.execute(
            "SELECT meeting_id FROM transcripts WHERE conversation_id = ?",
            (str(value),),
        ).fetchone()
        return int(row["meeting_id"]) if row is not None else None
    return meeting_id if exists(destination, "meetings", meeting_id) else None


def meeting_for_evidence(
    destination: sqlite3.Connection,
    evidence_id: str | None,
) -> int | None:
    if not evidence_id:
        return None
    row = destination.execute(
        "SELECT meeting_id FROM evidence_references WHERE id = ?",
        (evidence_id,),
    ).fetchone()
    return int(row["meeting_id"]) if row is not None else None


def exists(
    destination: sqlite3.Connection,
    table: str,
    identifier: object,
) -> bool:
    allowed = {
        "meetings",
        "transcript_segments",
        "evidence_references",
        "knowledge_nodes",
    }
    if table not in allowed:
        raise ValueError("Unsupported migration lookup.")
    return (
        destination.execute(
            f"SELECT 1 FROM {table} WHERE id = ?",
            (identifier,),
        ).fetchone()
        is not None
    )


def matching_insight_exists(
    destination: sqlite3.Connection,
    meeting_id: int,
    kind: str,
    title: str,
) -> bool:
    return (
        destination.execute(
            """
            SELECT 1 FROM insights
            WHERE meeting_id = ? AND kind = ? AND (title = ? OR body = ?)
            LIMIT 1
            """,
            (meeting_id, kind, title, title),
        ).fetchone()
        is not None
    )


def object_value(row: sqlite3.Row | None, key: str) -> dict[str, object]:
    loaded = safe_json(value(row, key), {})
    return dict(loaded) if isinstance(loaded, dict) else {}


def value(row: sqlite3.Row | None, key: str) -> object | None:
    if row is None or key not in row.keys():
        return None
    return row[key]


def float_value(value: object) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
