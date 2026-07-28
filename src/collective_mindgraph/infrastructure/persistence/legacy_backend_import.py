"""Import the former engine transcript archive and graph database."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .migration_support import (
    map_edge_kind,
    map_node_kind,
    map_review,
    normalized_timestamp,
    safe_json,
    stable_id,
    table_exists,
)
from .row_mapping import dump_json


def import_transcript_archive(
    transcript_directory: Path,
    destination: sqlite3.Connection,
) -> dict[str, int]:
    counts = {"meetings": 0, "transcripts": 0, "segments": 0, "insights": 0}
    if not transcript_directory.is_dir():
        return counts
    for path in sorted(transcript_directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            continue
        if not isinstance(payload, dict):
            continue
        conversation_id = str(payload.get("conversation_id") or path.stem).strip()
        if not conversation_id or _conversation_exists(destination, conversation_id):
            continue
        created_at = normalized_timestamp(payload.get("created_at"))
        updated_at = normalized_timestamp(payload.get("updated_at") or created_at)
        meeting_id = _create_backend_meeting(
            destination, payload, conversation_id, created_at, updated_at
        )
        counts["meetings"] += 1
        segments = payload.get("segments") if isinstance(payload.get("segments"), list) else []
        raw_text = _join_segments(segments, "raw_text")
        corrected_text = _join_segments(segments, "corrected_text") or raw_text
        diagnostics = payload.get("diagnostics")
        diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
        cursor = destination.execute(
            """
            INSERT INTO transcripts(
                meeting_id, conversation_id, provider, language,
                raw_text, corrected_text, confidence, diagnostics_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                meeting_id,
                conversation_id,
                str(diagnostics.get("provider") or "legacy_engine"),
                str(payload.get("language")) if payload.get("language") else None,
                raw_text,
                corrected_text,
                _float(diagnostics.get("transcription_confidence_estimate")),
                dump_json(diagnostics),
                created_at,
                updated_at,
            ),
        )
        transcript_id = int(cursor.lastrowid)
        counts["transcripts"] += 1
        counts["segments"] += _import_archive_segments(
            destination,
            meeting_id,
            transcript_id,
            segments,
            created_at,
        )
        counts["insights"] += _import_archive_insights(
            destination,
            meeting_id,
            transcript_id,
            payload,
            created_at,
            updated_at,
        )
        source = str(payload.get("source") or "").strip()
        if source:
            destination.execute(
                """
                INSERT OR IGNORE INTO recordings(
                    id, meeting_id, source_uri, duration_seconds, captured_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    stable_id("recording", conversation_id, source),
                    meeting_id,
                    source,
                    _float(diagnostics.get("audio_duration")),
                    created_at,
                ),
            )
    return counts


def import_backend_database(
    source: sqlite3.Connection,
    destination: sqlite3.Connection,
) -> dict[str, int]:
    counts = {"knowledge_nodes": 0, "knowledge_edges": 0, "jobs": 0}
    if table_exists(source, "v2_source_references"):
        for row in source.execute("SELECT * FROM v2_source_references").fetchall():
            meeting_id = _meeting_for_external_id(destination, row["session_id"])
            if meeting_id is None:
                continue
            segment_id = str(row["segment_id"]) if row["segment_id"] else None
            if segment_id and not _row_exists(destination, "transcript_segments", segment_id):
                segment_id = None
            destination.execute(
                """
                INSERT OR IGNORE INTO evidence_references(
                    id, meeting_id, segment_id, start_seconds, end_seconds,
                    text_preview, extractor, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'legacy_engine', ?)
                """,
                (
                    str(row["id"]),
                    meeting_id,
                    segment_id,
                    _float(row["timestamp_start"]),
                    _float(row["timestamp_end"]),
                    str(row["text_preview"]) if row["text_preview"] else None,
                    normalized_timestamp(row["created_at"]),
                ),
            )
    if table_exists(source, "v2_graph_nodes"):
        for row in source.execute("SELECT * FROM v2_graph_nodes").fetchall():
            evidence_id = str(row["source_reference_id"]) if row["source_reference_id"] else None
            meeting_id = _meeting_for_evidence(destination, evidence_id)
            kind = map_node_kind(row["type"])
            metadata = safe_json(row["metadata_json"], {})
            metadata = metadata if isinstance(metadata, dict) else {}
            destination.execute(
                """
                INSERT OR IGNORE INTO knowledge_nodes(
                    id, meeting_id, kind, title, body, evidence_id,
                    attributes_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(row["id"]),
                    meeting_id,
                    kind,
                    str(row["title"] or ""),
                    str(row["text_content"] or ""),
                    evidence_id
                    if evidence_id and _row_exists(destination, "evidence_references", evidence_id)
                    else None,
                    dump_json(metadata),
                    normalized_timestamp(row["created_at"]),
                    normalized_timestamp(row["updated_at"]),
                ),
            )
            counts["knowledge_nodes"] += 1
            if meeting_id is not None and kind in _INSIGHT_KINDS:
                review, edited = map_review(metadata)
                destination.execute(
                    """
                    INSERT OR IGNORE INTO insights(
                        id, meeting_id, kind, title, body, review, evidence_id,
                        edited_by_user, attributes_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(row["id"]),
                        meeting_id,
                        kind,
                        str(row["title"] or ""),
                        str(row["text_content"] or ""),
                        review,
                        evidence_id
                        if evidence_id
                        and _row_exists(destination, "evidence_references", evidence_id)
                        else None,
                        int(edited),
                        dump_json(metadata),
                        normalized_timestamp(row["created_at"]),
                        normalized_timestamp(row["updated_at"]),
                    ),
                )
    if table_exists(source, "v2_graph_edges"):
        for row in source.execute("SELECT * FROM v2_graph_edges").fetchall():
            source_id = str(row["source_node_id"])
            target_id = str(row["target_node_id"])
            if not (
                _row_exists(destination, "knowledge_nodes", source_id)
                and _row_exists(destination, "knowledge_nodes", target_id)
            ):
                continue
            evidence_id = str(row["source_reference_id"]) if row["source_reference_id"] else None
            destination.execute(
                """
                INSERT OR IGNORE INTO knowledge_edges(
                    id, source_id, target_id, kind, evidence_id,
                    confidence, attributes_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(row["id"]),
                    source_id,
                    target_id,
                    map_edge_kind(row["edge_type"]),
                    evidence_id
                    if evidence_id and _row_exists(destination, "evidence_references", evidence_id)
                    else None,
                    float(row["confidence"] or 1.0),
                    str(row["metadata_json"] or "{}"),
                    normalized_timestamp(row["created_at"]),
                ),
            )
            counts["knowledge_edges"] += 1
    _import_backend_embeddings(source, destination)
    if table_exists(source, "v2_jobs"):
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
            counts["jobs"] += 1
    return counts


def _create_backend_meeting(
    destination: sqlite3.Connection,
    payload: dict[str, object],
    conversation_id: str,
    created_at: str,
    updated_at: str,
) -> int:
    metadata = payload.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    title = str(metadata.get("meeting_title") or metadata.get("session_title") or "").strip()
    title = title or f"Imported meeting {conversation_id}"
    status = "failed" if str(payload.get("status", "")).lower() == "failed" else "ready"
    cursor = destination.execute(
        """
        INSERT INTO meetings(title, status, input_device, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            title,
            status,
            str(metadata.get("input_device")) if metadata.get("input_device") else None,
            created_at,
            updated_at,
        ),
    )
    return int(cursor.lastrowid)


def _import_archive_segments(
    destination: sqlite3.Connection,
    meeting_id: int,
    transcript_id: int,
    segments: list[object],
    created_at: str,
) -> int:
    imported = 0
    for position, value in enumerate(segments):
        if not isinstance(value, dict):
            continue
        segment_id = str(
            value.get("segment_id") or stable_id("backend-segment", transcript_id, position)
        )
        start = float(value.get("start", 0.0) or 0.0)
        end = float(value.get("end", start) or start)
        destination.execute(
            """
            INSERT OR IGNORE INTO transcript_segments(
                id, transcript_id, position, start_seconds, end_seconds,
                speaker_label, raw_text, corrected_text, confidence,
                speaker_confidence, overlaps_speech, notes_json, diagnostics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                segment_id,
                transcript_id,
                position,
                start,
                end,
                str(value.get("speaker") or "") or None,
                str(value.get("raw_text") or ""),
                str(value.get("corrected_text") or value.get("raw_text") or ""),
                _float(value.get("confidence")),
                _float(value.get("speaker_confidence")),
                int(bool(value.get("overlap"))),
                dump_json(value.get("notes") if isinstance(value.get("notes"), list) else []),
                dump_json(value.get("metadata") if isinstance(value.get("metadata"), dict) else {}),
            ),
        )
        destination.execute(
            """
            INSERT OR IGNORE INTO evidence_references(
                id, meeting_id, segment_id, start_seconds, end_seconds,
                text_preview, confidence, extractor, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'legacy_engine', ?)
            """,
            (
                stable_id("evidence", meeting_id, segment_id),
                meeting_id,
                segment_id,
                start,
                end,
                str(value.get("corrected_text") or value.get("raw_text") or "")[:500] or None,
                _float(value.get("confidence")),
                created_at,
            ),
        )
        imported += 1
    return imported


def _import_archive_insights(
    destination: sqlite3.Connection,
    meeting_id: int,
    transcript_id: int,
    payload: dict[str, object],
    created_at: str,
    updated_at: str,
) -> int:
    imported = 0
    fields = (
        ("topics", "topic", "label"),
        ("action_items", "task", "title"),
        ("decisions", "decision", "decision"),
        ("people", "person", None),
    )
    for field, kind, title_key in fields:
        values = payload.get(field) if isinstance(payload.get(field), list) else []
        for position, raw in enumerate(values):
            value = raw if isinstance(raw, dict) else {"value": raw}
            title = str(value.get(title_key) if title_key else value.get("value", "")).strip()
            if not title:
                continue
            segment_id = str(value.get("source_segment_id") or "") or None
            evidence_id = (
                stable_id("evidence", meeting_id, segment_id)
                if segment_id and _row_exists(destination, "transcript_segments", segment_id)
                else None
            )
            destination.execute(
                """
                INSERT OR IGNORE INTO insights(
                    id, meeting_id, kind, title, body, review, evidence_id,
                    attributes_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
                """,
                (
                    stable_id("backend-insight", transcript_id, kind, position, title),
                    meeting_id,
                    kind,
                    title,
                    title,
                    evidence_id,
                    dump_json(value),
                    created_at,
                    updated_at,
                ),
            )
            imported += 1
    return imported


def _import_backend_embeddings(source: sqlite3.Connection, destination: sqlite3.Connection) -> None:
    if not table_exists(source, "v2_embeddings"):
        return
    for row in source.execute("SELECT * FROM v2_embeddings").fetchall():
        node_id = str(row["node_id"])
        if not _row_exists(destination, "knowledge_nodes", node_id):
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
                evidence_id
                if evidence_id and _row_exists(destination, "evidence_references", evidence_id)
                else None,
                str(row["vector_json"]),
                str(row["text_chunk"]),
                int(row["dimension"]),
                normalized_timestamp(row["created_at"]),
            ),
        )


def _join_segments(segments: Iterable[object], field: str) -> str:
    return "\n".join(
        str(segment.get(field) or "").strip()
        for segment in segments
        if isinstance(segment, dict) and str(segment.get(field) or "").strip()
    )


def _conversation_exists(destination: sqlite3.Connection, conversation_id: str) -> bool:
    return (
        destination.execute(
            "SELECT 1 FROM transcripts WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        is not None
    )


def _meeting_for_external_id(destination: sqlite3.Connection, value: object) -> int | None:
    row = destination.execute(
        "SELECT meeting_id FROM transcripts WHERE conversation_id = ?",
        (str(value),),
    ).fetchone()
    if row is not None:
        return int(row["meeting_id"])
    try:
        meeting_id = int(str(value))
    except (TypeError, ValueError):
        return None
    return meeting_id if _row_exists(destination, "meetings", meeting_id) else None


def _meeting_for_evidence(destination: sqlite3.Connection, evidence_id: str | None) -> int | None:
    if not evidence_id:
        return None
    row = destination.execute(
        "SELECT meeting_id FROM evidence_references WHERE id = ?",
        (evidence_id,),
    ).fetchone()
    return int(row["meeting_id"]) if row is not None else None


def _row_exists(destination: sqlite3.Connection, table: str, identifier: object) -> bool:
    allowed = {"meetings", "transcript_segments", "evidence_references", "knowledge_nodes"}
    if table not in allowed:
        raise ValueError("Unsupported migration lookup.")
    return (
        destination.execute(
            f"SELECT 1 FROM {table} WHERE id = ?",
            (identifier,),
        ).fetchone()
        is not None
    )


def _float(value: object) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_INSIGHT_KINDS = {
    "task",
    "decision",
    "topic",
    "person",
    "entity",
    "risk",
    "open_question",
    "follow_up",
}
