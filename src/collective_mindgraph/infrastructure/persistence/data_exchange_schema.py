"""Versioned table layout and selection for canonical data exchange."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping

from collective_mindgraph.domain import MeetingId

from .data_exchange_mapping import raw_import_value, safe_import_value
from .sync_identity import validate_export_sync_identity

FORMAT_VERSION = 5
SUPPORTED_CANONICAL_VERSIONS = frozenset({3, 4, FORMAT_VERSION})

SYNC_COLUMNS = (
    "workspace_id",
    "sync_id",
    "local_revision",
    "sync_revision",
    "updated_by_device",
)

LEGACY_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
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

V5_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "workspaces": (
        "id",
        "sync_id",
        "name",
        "kind",
        "local_revision",
        "sync_revision",
        "updated_by_device",
        "created_at",
        "updated_at",
    ),
    **{
        table: (*columns, *SYNC_COLUMNS) if table != "embeddings" else columns
        for table, columns in LEGACY_TABLE_COLUMNS.items()
    },
    "comments": (
        "id",
        "workspace_id",
        "sync_id",
        "meeting_id",
        "parent_id",
        "target_type",
        "target_sync_id",
        "body",
        "author_subject",
        "local_revision",
        "sync_revision",
        "updated_by_device",
        "created_at",
        "updated_at",
    ),
    "activity_events": (
        "id",
        "workspace_id",
        "sync_id",
        "meeting_id",
        "event_kind",
        "object_type",
        "object_sync_id",
        "actor_subject",
        "details_json",
        "local_revision",
        "sync_revision",
        "updated_by_device",
        "created_at",
    ),
}


def columns_for_import(version: int) -> Mapping[str, tuple[str, ...]]:
    if version == FORMAT_VERSION:
        return V5_TABLE_COLUMNS
    if version in {3, 4}:
        return LEGACY_TABLE_COLUMNS
    raise ValueError(f"Unsupported export format_version: {version!r}.")


def select_rows(
    connection: sqlite3.Connection,
    table: str,
    meeting_id: MeetingId | None,
) -> list[sqlite3.Row]:
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
        "comments": "meeting_id",
        "activity_events": "meeting_id",
    }
    if table in direct:
        return connection.execute(
            f"SELECT * FROM {table} WHERE {direct[table]} = ?",
            (int(meeting_id),),
        ).fetchall()
    if table == "workspaces":
        return connection.execute(
            """
            SELECT workspaces.* FROM workspaces
            JOIN meetings ON meetings.workspace_id = workspaces.id
            WHERE meetings.id = ?
            """,
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


def validate_import_rows(
    connection: sqlite3.Connection,
    tables: dict[object, object],
    table_columns: Mapping[str, tuple[str, ...]],
) -> dict[str, set[object]]:
    existing_rows: dict[str, set[object]] = {table: set() for table in table_columns}
    conflicts: list[str] = []
    for table, columns in table_columns.items():
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
            validate_export_sync_identity(table, columns, raw_row)
            seen.add(identifier)
            existing = connection.execute(
                f"SELECT {', '.join(columns)} FROM {table} WHERE id = ?",
                (identifier,),
            ).fetchone()
            if existing is None:
                continue
            incoming = tuple(raw_import_value(table, column, raw_row) for column in columns)
            safe_incoming = tuple(safe_import_value(table, column, raw_row) for column in columns)
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
