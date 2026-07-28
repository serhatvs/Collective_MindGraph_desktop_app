"""Import the former desktop SQLite schema into the canonical store."""

from __future__ import annotations

import sqlite3

from .legacy_desktop_support import INSIGHT_KINDS as _INSIGHT_KINDS
from .legacy_desktop_support import exists as _exists
from .legacy_desktop_support import float_value as _float
from .legacy_desktop_support import import_embeddings as _import_legacy_embeddings
from .legacy_desktop_support import import_jobs as _import_legacy_jobs
from .legacy_desktop_support import matching_insight_exists as _matching_insight_exists
from .legacy_desktop_support import meeting_for_evidence as _meeting_for_evidence
from .legacy_desktop_support import object_value as _object
from .legacy_desktop_support import resolve_meeting as _resolve_meeting
from .legacy_desktop_support import value as _value
from .migration_support import (
    map_edge_kind,
    map_meeting_status,
    map_node_kind,
    map_review,
    normalized_timestamp,
    safe_json,
    stable_id,
    table_exists,
)
from .row_mapping import dump_json


def import_legacy_desktop(
    source: sqlite3.Connection,
    destination: sqlite3.Connection,
) -> dict[str, int]:
    counts = {
        "meetings": 0,
        "transcripts": 0,
        "segments": 0,
        "insights": 0,
        "knowledge_nodes": 0,
        "knowledge_edges": 0,
    }
    if not table_exists(source, "sessions"):
        return counts

    transcript_counts = (
        {
            int(row["session_id"]): int(row["count"])
            for row in source.execute(
                "SELECT session_id, COUNT(*) AS count FROM transcripts GROUP BY session_id"
            ).fetchall()
        }
        if table_exists(source, "transcripts")
        else {}
    )

    for row in source.execute("SELECT * FROM sessions ORDER BY id").fetchall():
        meeting_id = int(row["id"])
        created_at = normalized_timestamp(row["created_at"])
        updated_at = normalized_timestamp(row["updated_at"])
        destination.execute(
            """
            INSERT OR IGNORE INTO meetings(
                id, title, status, input_device, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                meeting_id,
                str(row["title"]).strip() or f"Meeting {meeting_id}",
                map_meeting_status(
                    row["status"],
                    has_transcript=transcript_counts.get(meeting_id, 0) > 0,
                ),
                str(row["device_id"]).strip() or None,
                created_at,
                updated_at,
            ),
        )
        counts["meetings"] += 1

    analyses = _analysis_rows(source)
    if table_exists(source, "transcripts"):
        for row in source.execute("SELECT * FROM transcripts ORDER BY id").fetchall():
            transcript_id = int(row["id"])
            analysis = analyses.get(transcript_id)
            metadata = _object(analysis, "metadata_json")
            raw_text = (
                str(analysis["raw_text_output"]) if analysis is not None else str(row["text"])
            )
            corrected_text = (
                str(analysis["corrected_text_output"]) if analysis is not None else str(row["text"])
            )
            destination.execute(
                """
                INSERT OR IGNORE INTO transcripts(
                    id, meeting_id, conversation_id, provider, language,
                    raw_text, corrected_text, confidence, diagnostics_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transcript_id,
                    int(row["session_id"]),
                    _value(analysis, "backend_conversation_id"),
                    _value(analysis, "source_provider") or "legacy_desktop",
                    metadata.get("language"),
                    raw_text,
                    corrected_text,
                    float(row["confidence"]) if row["confidence"] is not None else None,
                    dump_json(metadata),
                    normalized_timestamp(row["created_at"]),
                    normalized_timestamp(_value(analysis, "updated_at") or row["created_at"]),
                ),
            )
            counts["transcripts"] += 1
            if analysis is not None:
                counts["segments"] += _import_segments(
                    destination,
                    transcript_id,
                    int(row["session_id"]),
                    analysis,
                )

    _import_v2_evidence(source, destination)
    counts["knowledge_nodes"], counts["knowledge_edges"], graph_insights = _import_v2_graph(
        source,
        destination,
    )
    counts["insights"] += graph_insights
    counts["insights"] += _import_analysis_insights(source, destination, analyses)
    note_nodes, note_edges = _import_legacy_notes(source, destination)
    counts["knowledge_nodes"] += note_nodes
    counts["knowledge_edges"] += note_edges
    _import_legacy_embeddings(source, destination)
    _import_legacy_jobs(source, destination)
    return counts


def _analysis_rows(source: sqlite3.Connection) -> dict[int, sqlite3.Row]:
    if not table_exists(source, "transcript_analyses"):
        return {}
    return {
        int(row["transcript_id"]): row
        for row in source.execute("SELECT * FROM transcript_analyses").fetchall()
    }


def _import_segments(
    destination: sqlite3.Connection,
    transcript_id: int,
    meeting_id: int,
    analysis: sqlite3.Row,
) -> int:
    segments = safe_json(_value(analysis, "segments_json"), [])
    if not isinstance(segments, list):
        return 0
    created_at = normalized_timestamp(_value(analysis, "created_at"))
    imported = 0
    for position, item in enumerate(segments):
        if not isinstance(item, dict):
            continue
        segment_id = str(item.get("segment_id") or stable_id("segment", transcript_id, position))
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
                float(item.get("start", 0.0) or 0.0),
                float(item.get("end", item.get("start", 0.0)) or 0.0),
                str(item.get("speaker") or "") or None,
                str(item.get("raw_text") or ""),
                str(item.get("corrected_text") or item.get("raw_text") or ""),
                _float(item.get("confidence")),
                _float(item.get("speaker_confidence")),
                int(bool(item.get("overlap"))),
                dump_json(item.get("notes") if isinstance(item.get("notes"), list) else []),
                dump_json(item.get("metadata") if isinstance(item.get("metadata"), dict) else {}),
            ),
        )
        evidence_id = stable_id("evidence", meeting_id, segment_id)
        destination.execute(
            """
            INSERT OR IGNORE INTO evidence_references(
                id, meeting_id, segment_id, start_seconds, end_seconds,
                text_preview, confidence, extractor, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                meeting_id,
                segment_id,
                _float(item.get("start")),
                _float(item.get("end")),
                str(item.get("corrected_text") or item.get("raw_text") or "")[:500] or None,
                _float(item.get("confidence")),
                "legacy_desktop",
                created_at,
            ),
        )
        imported += 1
    return imported


def _import_v2_evidence(source: sqlite3.Connection, destination: sqlite3.Connection) -> None:
    if not table_exists(source, "v2_source_references"):
        return
    for row in source.execute("SELECT * FROM v2_source_references").fetchall():
        meeting_id = _resolve_meeting(destination, row["session_id"])
        if meeting_id is None:
            continue
        segment_id = str(row["segment_id"]) if row["segment_id"] else None
        if segment_id and not _exists(destination, "transcript_segments", segment_id):
            segment_id = None
        destination.execute(
            """
            INSERT OR IGNORE INTO evidence_references(
                id, meeting_id, segment_id, start_seconds, end_seconds,
                text_preview, confidence, extractor, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(row["id"]),
                meeting_id,
                segment_id,
                _float(row["timestamp_start"]),
                _float(row["timestamp_end"]),
                str(row["text_preview"]) if row["text_preview"] else None,
                None,
                "legacy_graph",
                normalized_timestamp(row["created_at"]),
            ),
        )


def _import_v2_graph(
    source: sqlite3.Connection,
    destination: sqlite3.Connection,
) -> tuple[int, int, int]:
    if not table_exists(source, "v2_graph_nodes"):
        return 0, 0, 0
    node_count = 0
    insight_count = 0
    for row in source.execute("SELECT * FROM v2_graph_nodes").fetchall():
        evidence_id = str(row["source_reference_id"]) if row["source_reference_id"] else None
        meeting_id = _meeting_for_evidence(destination, evidence_id)
        kind = map_node_kind(row["type"])
        metadata = safe_json(row["metadata_json"], {})
        metadata = metadata if isinstance(metadata, dict) else {}
        title = str(row["title"] or "").strip()
        body = str(row["text_content"] or "").strip()
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
                title,
                body,
                evidence_id
                if evidence_id and _exists(destination, "evidence_references", evidence_id)
                else None,
                dump_json(metadata),
                normalized_timestamp(row["created_at"]),
                normalized_timestamp(row["updated_at"]),
            ),
        )
        node_count += 1
        if meeting_id is not None and kind in _INSIGHT_KINDS:
            review, edited = map_review(metadata)
            destination.execute(
                """
                INSERT OR IGNORE INTO insights(
                    id, meeting_id, kind, title, body, review, evidence_id,
                    confidence, edited_by_user, needs_review, attributes_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(row["id"]),
                    meeting_id,
                    kind,
                    title,
                    body,
                    review,
                    evidence_id
                    if evidence_id and _exists(destination, "evidence_references", evidence_id)
                    else None,
                    _float(metadata.get("confidence")),
                    int(edited),
                    0,
                    dump_json(metadata),
                    normalized_timestamp(row["created_at"]),
                    normalized_timestamp(row["updated_at"]),
                ),
            )
            insight_count += 1
    edge_count = 0
    if table_exists(source, "v2_graph_edges"):
        for row in source.execute("SELECT * FROM v2_graph_edges").fetchall():
            source_id = str(row["source_node_id"])
            target_id = str(row["target_node_id"])
            if not (
                _exists(destination, "knowledge_nodes", source_id)
                and _exists(destination, "knowledge_nodes", target_id)
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
                    if evidence_id and _exists(destination, "evidence_references", evidence_id)
                    else None,
                    float(row["confidence"] or 1.0),
                    dump_json(safe_json(row["metadata_json"], {})),
                    normalized_timestamp(row["created_at"]),
                ),
            )
            edge_count += 1
    return node_count, edge_count, insight_count


def _import_analysis_insights(
    source: sqlite3.Connection,
    destination: sqlite3.Connection,
    analyses: dict[int, sqlite3.Row],
) -> int:
    if not analyses:
        return 0
    transcript_meetings = {
        int(row["id"]): int(row["session_id"])
        for row in source.execute("SELECT id, session_id FROM transcripts").fetchall()
    }
    imported = 0
    fields = (
        ("topics_json", "topic", "label"),
        ("action_items_json", "task", "title"),
        ("decisions_json", "decision", "decision"),
        ("people_json", "person", None),
    )
    for transcript_id, analysis in analyses.items():
        meeting_id = transcript_meetings.get(transcript_id)
        if meeting_id is None:
            continue
        for field, kind, title_key in fields:
            values = safe_json(_value(analysis, field), [])
            if not isinstance(values, list):
                continue
            for position, value in enumerate(values):
                item = value if isinstance(value, dict) else {"value": value}
                title = str(item.get(title_key) if title_key else item.get("value", "")).strip()
                if not title or _matching_insight_exists(destination, meeting_id, kind, title):
                    continue
                segment_id = str(item.get("source_segment_id") or "") or None
                evidence_id = (
                    stable_id("evidence", meeting_id, segment_id)
                    if segment_id and _exists(destination, "transcript_segments", segment_id)
                    else None
                )
                now = normalized_timestamp(_value(analysis, "updated_at"))
                destination.execute(
                    """
                    INSERT OR IGNORE INTO insights(
                        id, meeting_id, kind, title, body, review, evidence_id,
                        confidence, edited_by_user, needs_review, attributes_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, 0, 0, ?, ?, ?)
                    """,
                    (
                        stable_id("insight", transcript_id, kind, position, title),
                        meeting_id,
                        kind,
                        title,
                        title,
                        evidence_id,
                        _float(item.get("confidence")),
                        dump_json(item),
                        now,
                        now,
                    ),
                )
                imported += 1
    return imported


def _import_legacy_notes(
    source: sqlite3.Connection,
    destination: sqlite3.Connection,
) -> tuple[int, int]:
    if not table_exists(source, "graph_nodes"):
        return 0, 0
    nodes = source.execute("SELECT * FROM graph_nodes").fetchall()
    for row in nodes:
        node_id = stable_id("legacy-note", row["id"])
        now = normalized_timestamp(row["created_at"])
        destination.execute(
            """
            INSERT OR IGNORE INTO knowledge_nodes(
                id, meeting_id, kind, title, body, attributes_json, created_at, updated_at
            ) VALUES (?, ?, 'note', ?, ?, ?, ?, ?)
            """,
            (
                node_id,
                int(row["session_id"]),
                str(row["node_text"])[:120],
                str(row["node_text"]),
                dump_json(
                    {
                        "legacy_branch_type": row["branch_type"],
                        "legacy_branch_slot": row["branch_slot"],
                        "legacy_override_reason": row["override_reason"],
                    }
                ),
                now,
                now,
            ),
        )
    edges = 0
    for row in nodes:
        if row["parent_node_id"] is None:
            continue
        destination.execute(
            """
            INSERT OR IGNORE INTO knowledge_edges(
                id, source_id, target_id, kind, confidence, attributes_json, created_at
            ) VALUES (?, ?, ?, 'contains', 1.0, '{}', ?)
            """,
            (
                stable_id("legacy-edge", row["parent_node_id"], row["id"]),
                stable_id("legacy-note", row["parent_node_id"]),
                stable_id("legacy-note", row["id"]),
                normalized_timestamp(row["created_at"]),
            ),
        )
        edges += 1
    return len(nodes), edges
