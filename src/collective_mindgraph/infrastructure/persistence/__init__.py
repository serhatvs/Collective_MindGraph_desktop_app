"""Persistence adapters owned by the local engine."""

from .canonical_schema import SCHEMA_VERSION, initialize_schema
from .data_exchange import FORMAT_VERSION, SqliteDataExchange
from .embedding_store import SqliteEmbeddingStore
from .insight_store import SqliteInsightStore
from .job_store import SqliteJobStore
from .knowledge_store import SqliteKnowledgeGraphStore
from .legacy_migration import LegacyDataMigrator, MigrationReport
from .legacy_source_discovery import LegacySourceCandidates, discover_legacy_sources
from .meeting_store import SqliteMeetingStore
from .recording_store import SqliteRecordingStore
from .sqlite_database import SqliteDatabase
from .transcript_store import SqliteTranscriptStore
from .transcription_result_archive import CanonicalTranscriptionResultArchive

__all__ = [
    "CanonicalTranscriptionResultArchive",
    "FORMAT_VERSION",
    "LegacyDataMigrator",
    "LegacySourceCandidates",
    "MigrationReport",
    "SCHEMA_VERSION",
    "SqliteDatabase",
    "SqliteDataExchange",
    "SqliteEmbeddingStore",
    "SqliteInsightStore",
    "SqliteJobStore",
    "SqliteKnowledgeGraphStore",
    "SqliteMeetingStore",
    "SqliteRecordingStore",
    "SqliteTranscriptStore",
    "initialize_schema",
    "discover_legacy_sources",
]
