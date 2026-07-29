"""Persistence adapters owned by the local engine."""

from .canonical_schema import SCHEMA_VERSION, initialize_schema
from .data_exchange import FORMAT_VERSION, SqliteDataExchange
from .embedding_store import SqliteEmbeddingStore
from .encrypted_backup import (
    BACKUP_EXTENSION,
    BACKUP_FORMAT,
    BACKUP_FORMAT_VERSION,
    InvalidBackupError,
)
from .insight_store import SqliteInsightStore
from .job_store import SqliteJobStore
from .key_envelope_store import SqliteKeyEnvelopeStore
from .knowledge_store import SqliteKnowledgeGraphStore
from .legacy_migration import LegacyDataMigrator, MigrationReport
from .legacy_source_discovery import LegacySourceCandidates, discover_legacy_sources
from .meeting_store import SqliteMeetingStore
from .outbox_store import SqliteOutboxStore
from .recording_store import SqliteRecordingStore
from .sqlite_database import SqliteDatabase
from .transcript_store import SqliteTranscriptStore
from .transcription_result_archive import CanonicalTranscriptionResultArchive
from .workspace_store import SqliteWorkspaceStore

__all__ = [
    "BACKUP_EXTENSION",
    "BACKUP_FORMAT",
    "BACKUP_FORMAT_VERSION",
    "CanonicalTranscriptionResultArchive",
    "FORMAT_VERSION",
    "LegacyDataMigrator",
    "LegacySourceCandidates",
    "MigrationReport",
    "InvalidBackupError",
    "SCHEMA_VERSION",
    "SqliteDatabase",
    "SqliteDataExchange",
    "SqliteEmbeddingStore",
    "SqliteInsightStore",
    "SqliteJobStore",
    "SqliteKeyEnvelopeStore",
    "SqliteKnowledgeGraphStore",
    "SqliteMeetingStore",
    "SqliteOutboxStore",
    "SqliteRecordingStore",
    "SqliteTranscriptStore",
    "SqliteWorkspaceStore",
    "initialize_schema",
    "discover_legacy_sources",
]
