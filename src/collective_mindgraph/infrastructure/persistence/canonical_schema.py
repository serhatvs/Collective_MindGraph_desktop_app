"""Canonical normalized SQLite schema."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from .sqlite_database import SqliteDatabase
from .sync_schema import upgrade_to_workspace_schema

SCHEMA_VERSION = 3

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS migration_sources (
    source_hash TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('draft', 'recording', 'processing', 'ready', 'failed', 'archived')
    ),
    input_device TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recordings (
    id TEXT PRIMARY KEY,
    meeting_id INTEGER NOT NULL,
    source_uri TEXT NOT NULL,
    duration_seconds REAL,
    input_device TEXT,
    storage_status TEXT NOT NULL DEFAULT 'managed' CHECK (
        storage_status IN ('managed', 'retained', 'deleted', 'missing')
    ),
    keep_audio INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT,
    captured_at TEXT NOT NULL,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL,
    conversation_id TEXT,
    provider TEXT NOT NULL,
    language TEXT,
    raw_text TEXT NOT NULL,
    corrected_text TEXT NOT NULL,
    confidence REAL,
    diagnostics_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_transcripts_conversation
ON transcripts(conversation_id) WHERE conversation_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS transcript_segments (
    id TEXT PRIMARY KEY,
    transcript_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    start_seconds REAL NOT NULL,
    end_seconds REAL NOT NULL,
    speaker_label TEXT,
    raw_text TEXT NOT NULL,
    corrected_text TEXT NOT NULL,
    confidence REAL,
    speaker_confidence REAL,
    overlaps_speech INTEGER NOT NULL DEFAULT 0,
    notes_json TEXT NOT NULL DEFAULT '[]',
    diagnostics_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE,
    UNIQUE (transcript_id, position)
);

CREATE TABLE IF NOT EXISTS evidence_references (
    id TEXT PRIMARY KEY,
    meeting_id INTEGER NOT NULL,
    segment_id TEXT,
    start_seconds REAL,
    end_seconds REAL,
    text_preview TEXT,
    confidence REAL,
    extractor TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE,
    FOREIGN KEY (segment_id) REFERENCES transcript_segments(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS insights (
    id TEXT PRIMARY KEY,
    meeting_id INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (
        kind IN ('task', 'decision', 'topic', 'person', 'entity', 'risk', 'open_question', 'follow_up')
    ),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    review TEXT NOT NULL CHECK (review IN ('pending', 'accepted', 'rejected')),
    evidence_id TEXT,
    confidence REAL,
    edited_by_user INTEGER NOT NULL DEFAULT 0,
    needs_review INTEGER NOT NULL DEFAULT 0,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE,
    FOREIGN KEY (evidence_id) REFERENCES evidence_references(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id TEXT PRIMARY KEY,
    meeting_id INTEGER,
    kind TEXT NOT NULL CHECK (
        kind IN (
            'meeting', 'segment', 'note', 'task', 'decision', 'topic', 'person',
            'document', 'project', 'entity', 'risk', 'open_question', 'follow_up'
        )
    ),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    evidence_id TEXT,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE,
    FOREIGN KEY (evidence_id) REFERENCES evidence_references(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS knowledge_edges (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (
        kind IN (
            'contains', 'mentions', 'creates', 'supports', 'assigned_to',
            'related_to', 'derived_from', 'merged_into'
        )
    ),
    evidence_id TEXT,
    confidence REAL NOT NULL DEFAULT 1.0,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (evidence_id) REFERENCES evidence_references(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS embeddings (
    id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    evidence_id TEXT,
    vector_json TEXT NOT NULL,
    text_chunk TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (node_id) REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (evidence_id) REFERENCES evidence_references(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS processing_jobs (
    id TEXT PRIMARY KEY,
    meeting_id INTEGER,
    recording_id TEXT,
    parent_job_id TEXT,
    result_transcript_id INTEGER,
    kind TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')
    ),
    progress INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    message TEXT NOT NULL DEFAULT '',
    error TEXT,
    retryable INTEGER NOT NULL DEFAULT 0,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE,
    FOREIGN KEY (recording_id) REFERENCES recordings(id) ON DELETE SET NULL,
    FOREIGN KEY (parent_job_id) REFERENCES processing_jobs(id) ON DELETE SET NULL,
    FOREIGN KEY (result_transcript_id) REFERENCES transcripts(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_meetings_updated ON meetings(updated_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_transcripts_meeting ON transcripts(meeting_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_segments_transcript ON transcript_segments(transcript_id, position);
CREATE INDEX IF NOT EXISTS idx_insights_meeting ON insights(meeting_id, kind, review);
CREATE INDEX IF NOT EXISTS idx_insights_review ON insights(review, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_meeting ON knowledge_nodes(meeting_id, kind);
CREATE INDEX IF NOT EXISTS idx_knowledge_edges_source ON knowledge_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_edges_target ON knowledge_edges(target_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON processing_jobs(status, updated_at DESC);
"""


def initialize_schema(database: SqliteDatabase) -> None:
    """Create or advance the canonical schema."""

    database.prepare_directory()
    applied_at = datetime.now(tz=UTC).isoformat()
    with database.connect() as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(SCHEMA_SQL)
        _upgrade_to_version_2(connection)
        upgrade_to_workspace_schema(connection)
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, applied_at),
        )


def _upgrade_to_version_2(connection: sqlite3.Connection) -> None:
    recording_columns = _column_names(connection, "recordings")
    for definition in (
        "storage_status TEXT NOT NULL DEFAULT 'managed'",
        "keep_audio INTEGER NOT NULL DEFAULT 0",
        "deleted_at TEXT",
    ):
        name = definition.split(maxsplit=1)[0]
        if name not in recording_columns:
            connection.execute(f"ALTER TABLE recordings ADD COLUMN {definition}")

    job_columns = _column_names(connection, "processing_jobs")
    for definition in (
        "recording_id TEXT REFERENCES recordings(id) ON DELETE SET NULL",
        "parent_job_id TEXT REFERENCES processing_jobs(id) ON DELETE SET NULL",
        "result_transcript_id INTEGER REFERENCES transcripts(id) ON DELETE SET NULL",
        "retryable INTEGER NOT NULL DEFAULT 0",
    ):
        name = definition.split(maxsplit=1)[0]
        if name not in job_columns:
            connection.execute(f"ALTER TABLE processing_jobs ADD COLUMN {definition}")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_recording "
        "ON processing_jobs(recording_id, created_at DESC)"
    )


def _column_names(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
