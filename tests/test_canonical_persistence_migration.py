from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from collective_mindgraph.application import GetDashboard, PageRequest
from collective_mindgraph.infrastructure.persistence import (
    LegacyDataMigrator,
    SqliteDatabase,
    SqliteInsightStore,
    SqliteKnowledgeGraphStore,
    SqliteMeetingStore,
    SqliteTranscriptStore,
    discover_legacy_sources,
    initialize_schema,
)


def _legacy_desktop_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.executescript(
            """
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                device_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE transcripts (
                id INTEGER PRIMARY KEY,
                session_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                confidence REAL NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE transcript_analyses (
                transcript_id INTEGER PRIMARY KEY,
                source_provider TEXT NOT NULL,
                backend_conversation_id TEXT,
                raw_text_output TEXT NOT NULL,
                corrected_text_output TEXT NOT NULL,
                summary TEXT,
                topics_json TEXT NOT NULL,
                action_items_json TEXT NOT NULL,
                decisions_json TEXT NOT NULL,
                people_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                speaker_stats_json TEXT NOT NULL,
                segments_json TEXT NOT NULL,
                quality_report_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            """
            INSERT INTO sessions VALUES
            (7, 'Legacy Meeting', 'MIC-1', 'active', '2026-07-20 12:00:00', '2026-07-20 12:05:00')
            """
        )
        connection.execute(
            """
            INSERT INTO transcripts VALUES
            (11, 7, 'Desktop corrected text', 0.91, '2026-07-20 12:05:00')
            """
        )
        connection.execute(
            """
            INSERT INTO transcript_analyses VALUES (
                11, 'faster_whisper', 'conversation-7',
                'Desktop raw text', 'Desktop corrected text', 'Summary',
                ?, ?, ?, ?, ?, '[]', ?, NULL,
                '2026-07-20 12:05:00', '2026-07-20 12:06:00'
            )
            """,
            (
                json.dumps([{"label": "Architecture", "start": 0.0, "end": 2.0}]),
                json.dumps([{"title": "Migrate database", "source_segment_id": "seg-1"}]),
                json.dumps([{"decision": "Keep local data", "source_segment_id": "seg-1"}]),
                json.dumps(["Aylin"]),
                json.dumps({"language": "tr"}),
                json.dumps(
                    [
                        {
                            "segment_id": "seg-1",
                            "start": 0.0,
                            "end": 2.0,
                            "speaker": "Aylin",
                            "raw_text": "Desktop raw text",
                            "corrected_text": "Desktop corrected text",
                            "confidence": 0.91,
                        }
                    ]
                ),
            ),
        )


def _backend_archive(path: Path) -> None:
    path.mkdir(parents=True)
    payload = {
        "conversation_id": "conversation-7",
        "created_at": "2026-07-20T12:00:00+00:00",
        "updated_at": "2026-07-20T12:07:00+00:00",
        "source": "backend.wav",
        "language": "tr",
        "status": "completed",
        "segments": [
            {
                "segment_id": "seg-backend",
                "start": 0.0,
                "end": 2.0,
                "speaker": "SPEAKER_00",
                "raw_text": "Backend raw should not win",
                "corrected_text": "Backend corrected should not win",
            }
        ],
    }
    (path / "conversation-7.json").write_text(json.dumps(payload), encoding="utf-8")


def _backend_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.executescript(
            """
            CREATE TABLE v2_jobs (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL,
                message TEXT,
                error TEXT,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO v2_jobs VALUES (
                'legacy-job', 'transcription', 'succeeded', 100,
                'Imported diagnostic', NULL, '{}',
                '2026-07-20T12:00:00+00:00',
                '2026-07-20T12:05:00+00:00'
            );
            """
        )


def test_empty_store_initializes_canonical_schema(tmp_path):
    database_path = tmp_path / "collective_mindgraph.sqlite3"
    report = LegacyDataMigrator(database_path).run()

    assert report.migrated
    assert report.backup_path is None
    with closing(sqlite3.connect(database_path)) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {
        "meetings",
        "transcripts",
        "transcript_segments",
        "insights",
        "knowledge_nodes",
        "processing_jobs",
        "schema_migrations",
    } <= tables


def test_legacy_desktop_migration_is_backed_up_and_preserves_corrections(tmp_path):
    database_path = tmp_path / "collective_mindgraph.sqlite3"
    transcript_directory = tmp_path / "legacy_transcripts"
    _legacy_desktop_database(database_path)
    _backend_archive(transcript_directory)

    report = LegacyDataMigrator(
        database_path,
        transcript_directory=transcript_directory,
    ).run()

    assert report.migrated
    assert report.backup_path is not None and report.backup_path.exists()
    database = SqliteDatabase(database_path)
    meetings = SqliteMeetingStore(database)
    transcripts = SqliteTranscriptStore(database)
    meeting = meetings.get(7)
    transcript = transcripts.latest_for_meeting(7)

    assert meeting is not None
    assert meeting.title == "Legacy Meeting"
    assert meeting.status.value == "ready"
    assert transcript is not None
    assert transcript.conversation_id == "conversation-7"
    assert transcript.raw_text == "Desktop raw text"
    assert transcript.corrected_text == "Desktop corrected text"
    assert transcript.segments[0].id == "seg-1"

    dashboard = GetDashboard(
        meetings,
        transcripts,
        SqliteInsightStore(database),
        SqliteKnowledgeGraphStore(database),
    )()
    assert dashboard.total_meetings == 1
    assert dashboard.total_transcripts == 1
    assert dashboard.pending_reviews == 4


def test_migration_is_idempotent(tmp_path):
    database_path = tmp_path / "collective_mindgraph.sqlite3"
    _legacy_desktop_database(database_path)
    first = LegacyDataMigrator(database_path).run()
    second = LegacyDataMigrator(database_path).run()

    assert first.backup_path is not None
    assert not second.migrated
    assert second.backup_path is None
    database = SqliteDatabase(database_path)
    assert SqliteMeetingStore(database).list(PageRequest()).total == 1
    assert SqliteTranscriptStore(database).count() == 1


def test_backend_only_database_imports_diagnostics_without_desktop_data(tmp_path):
    database_path = tmp_path / "collective_mindgraph.sqlite3"
    backend_path = tmp_path / "legacy-engine.sqlite3"
    _backend_database(backend_path)

    report = LegacyDataMigrator(
        database_path,
        backend_database_path=backend_path,
    ).run()

    assert report.migrated
    assert report.imported_sources == (backend_path.resolve(),)
    assert report.counts["jobs"] == 1
    with closing(sqlite3.connect(database_path)) as connection:
        job = connection.execute("SELECT id, status, progress FROM processing_jobs").fetchone()
        source_count = connection.execute("SELECT COUNT(*) FROM migration_sources").fetchone()[0]
    assert job == ("legacy-job", "succeeded", 100)
    assert source_count == 1


def test_corrupt_secondary_source_leaves_legacy_database_untouched(tmp_path):
    database_path = tmp_path / "collective_mindgraph.sqlite3"
    backend_path = tmp_path / "corrupt-engine.sqlite3"
    _legacy_desktop_database(database_path)
    backend_path.write_bytes(b"not-a-sqlite-database")
    original_hash = hashlib.sha256(database_path.read_bytes()).hexdigest()

    try:
        LegacyDataMigrator(
            database_path,
            backend_database_path=backend_path,
        ).run()
    except sqlite3.DatabaseError:
        pass
    else:
        raise AssertionError("A corrupt secondary database should abort migration.")

    assert hashlib.sha256(database_path.read_bytes()).hexdigest() == original_hash
    assert not database_path.with_suffix(".sqlite3.migrating").exists()


def test_interrupted_activation_restores_original_database(tmp_path, monkeypatch):
    database_path = tmp_path / "collective_mindgraph.sqlite3"
    _legacy_desktop_database(database_path)
    original_hash = hashlib.sha256(database_path.read_bytes()).hexdigest()
    migrator = LegacyDataMigrator(database_path)

    def interrupt(_target_path: Path) -> None:
        raise RuntimeError("simulated activation interruption")

    monkeypatch.setattr(migrator, "_activate_target", interrupt)

    try:
        migrator.run()
    except RuntimeError as error:
        assert "simulated activation interruption" in str(error)
    else:
        raise AssertionError("The simulated activation interruption should propagate.")

    assert hashlib.sha256(database_path.read_bytes()).hexdigest() == original_hash
    assert not database_path.with_suffix(".sqlite3.migrating").exists()


def test_existing_database_activation_never_retires_live_path_before_replace(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "collective_mindgraph.sqlite3"
    _legacy_desktop_database(database_path)
    original_hash = hashlib.sha256(database_path.read_bytes()).hexdigest()
    migrator = LegacyDataMigrator(database_path)
    calls: list[tuple[Path, Path]] = []

    def interrupt(source: Path, target: Path) -> None:
        calls.append((source, target))
        raise RuntimeError("simulated atomic replace failure")

    monkeypatch.setattr(migrator, "_replace_with_retry", interrupt)

    with pytest.raises(RuntimeError, match="simulated atomic replace failure"):
        migrator.run()

    assert calls == [
        (database_path.with_suffix(".sqlite3.migrating"), database_path),
    ]
    assert hashlib.sha256(database_path.read_bytes()).hexdigest() == original_hash
    assert not database_path.with_suffix(".sqlite3.legacy-source").exists()


def test_corrupt_existing_file_is_not_overwritten(tmp_path):
    database_path = tmp_path / "collective_mindgraph.sqlite3"
    database_path.write_bytes(b"not-a-sqlite-database")
    original_hash = hashlib.sha256(database_path.read_bytes()).hexdigest()

    try:
        LegacyDataMigrator(database_path).run()
    except sqlite3.DatabaseError:
        pass
    else:
        raise AssertionError("Corrupt SQLite input should fail migration.")

    assert hashlib.sha256(database_path.read_bytes()).hexdigest() == original_hash


def test_existing_canonical_database_is_supplemented_through_migrating_copy(tmp_path):
    database_path = tmp_path / "collective_mindgraph.sqlite3"
    backend_path = tmp_path / "legacy-engine.sqlite3"
    database = SqliteDatabase(database_path)
    initialize_schema(database)
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO meetings(title, status, created_at, updated_at)
            VALUES ('Canonical meeting', 'ready', '2026-07-20T12:00:00+00:00',
                    '2026-07-20T12:00:00+00:00')
            """
        )
    _backend_database(backend_path)

    report = LegacyDataMigrator(
        database_path,
        backend_database_paths=(backend_path,),
    ).run()

    assert report.migrated
    assert report.backup_path is not None and report.backup_path.exists()
    assert not database_path.with_suffix(".sqlite3.migrating").exists()
    with closing(sqlite3.connect(database_path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM meetings").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM processing_jobs").fetchone()[0] == 1
        assert connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 2
        recording_columns = {row[1] for row in connection.execute("PRAGMA table_info(recordings)")}
        job_columns = {row[1] for row in connection.execute("PRAGMA table_info(processing_jobs)")}
    assert {"storage_status", "keep_audio", "deleted_at"} <= recording_columns
    assert {
        "recording_id",
        "parent_job_id",
        "result_transcript_id",
        "retryable",
    } <= job_columns


def test_fresh_install_never_activates_before_validation(tmp_path, monkeypatch):
    database_path = tmp_path / "collective_mindgraph.sqlite3"
    migrator = LegacyDataMigrator(database_path)

    def interrupt(target_path: Path) -> None:
        assert target_path.name.endswith(".migrating")
        assert target_path.exists()
        assert not database_path.exists()
        raise RuntimeError("activation blocked")

    monkeypatch.setattr(migrator, "_activate_target", interrupt)
    with pytest.raises(RuntimeError, match="activation blocked"):
        migrator.run()

    assert not database_path.exists()
    assert not database_path.with_suffix(".sqlite3.migrating").exists()


def test_legacy_source_discovery_is_deterministic_and_honors_overrides(
    tmp_path,
    monkeypatch,
):
    canonical = tmp_path / "canonical" / "collective_mindgraph.sqlite3"
    data_dir = canonical.parent
    cwd = tmp_path / "source"
    executable = tmp_path / "installed" / "CollectiveMindGraph.exe"
    configured_db = tmp_path / "override" / "engine.sqlite3"
    configured_archive = tmp_path / "override" / "transcripts"
    monkeypatch.setenv("CMG_LEGACY_BACKEND_DATABASE", str(configured_db))
    monkeypatch.setenv("CMG_LEGACY_TRANSCRIPT_DIRECTORY", str(configured_archive))

    candidates = discover_legacy_sources(
        canonical_path=canonical,
        data_directory=data_dir,
        working_directory=cwd,
        executable_path=executable,
    )

    assert candidates.backend_databases[:3] == (
        configured_db.resolve(),
        (cwd / "realtime_backend_data" / "collective_mindgraph.sqlite3").resolve(),
        (executable.parent / "realtime_backend_data" / "collective_mindgraph.sqlite3").resolve(),
    )
    assert candidates.transcript_directories == (
        configured_archive.resolve(),
        (cwd / "realtime_backend_data" / "transcripts").resolve(),
        (executable.parent / "realtime_backend_data" / "transcripts").resolve(),
        (canonical.parent / "transcripts").resolve(),
    )
