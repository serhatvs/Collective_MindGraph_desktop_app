from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from collective_mindgraph.domain import (
    DeviceId,
    MeetingId,
    MeetingStatus,
    OperationId,
    SyncId,
    SyncIdentity,
    SyncOperation,
    Workspace,
    WorkspaceId,
    WorkspaceKind,
)
from collective_mindgraph.infrastructure.persistence import (
    BACKUP_FORMAT,
    InvalidBackupError,
    LegacyDataMigrator,
    SqliteDatabase,
    SqliteDataExchange,
    SqliteMeetingStore,
    SqliteWorkspaceStore,
    initialize_schema,
)
from collective_mindgraph.infrastructure.persistence.canonical_schema import SCHEMA_SQL
from collective_mindgraph.infrastructure.persistence.data_exchange_schema import (
    columns_for_import,
)
from collective_mindgraph.infrastructure.persistence.sync_identity import (
    SYNC_ENTITY_KEYS,
    sync_identity_violations,
)
from collective_mindgraph.infrastructure.persistence.sync_schema import (
    current_local_workspace,
)


def test_schema_v3_bootstraps_local_workspace_and_sync_tables(tmp_path):
    database = SqliteDatabase(tmp_path / "collective_mindgraph.sqlite3")
    initialize_schema(database)
    workspaces = SqliteWorkspaceStore(database)

    workspace = workspaces.local_workspace()

    assert workspace.name == "Local Workspace"
    assert str(workspace.id) == str(workspace.sync_id)
    assert UUID(str(workspace.id)).version == 4
    assert workspace.local_revision == 1
    assert workspace.sync_revision == 0
    assert workspace.updated_by_device is not None
    with database.connect() as connection:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        current_devices = int(
            connection.execute("SELECT COUNT(*) FROM devices WHERE is_current = 1").fetchone()[0]
        )
        schema_version = int(
            connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        )
    assert schema_version == 3
    assert current_devices == 1
    assert {
        "workspaces",
        "devices",
        "sync_outbox",
        "sync_state",
        "sync_tombstones",
        "conflict_versions",
        "key_envelopes",
        "comments",
        "activity_events",
        "model_registry",
    } <= tables


def test_new_and_updated_entities_receive_stable_sync_identity(tmp_path):
    database = SqliteDatabase(tmp_path / "collective_mindgraph.sqlite3")
    initialize_schema(database)
    meetings = SqliteMeetingStore(database)
    workspaces = SqliteWorkspaceStore(database)
    now = datetime.now(tz=UTC)
    meeting = meetings.create(
        title="Identity test",
        status=MeetingStatus.DRAFT,
        input_device=None,
        now=now,
    )

    original = workspaces.get_identity("meetings", int(meeting.id))
    meetings.rename(meeting.id, title="Renamed", now=now)
    updated = workspaces.get_identity("meetings", int(meeting.id))

    assert original is not None
    assert updated is not None
    assert UUID(str(original.sync_id)).version == 4
    assert original.workspace_id == workspaces.local_workspace().id
    assert original.local_revision == 1
    assert updated.sync_id == original.sync_id
    assert updated.local_revision == 2
    assert updated.updated_by_device == workspaces.local_workspace().updated_by_device


def test_v2_database_upgrade_uses_backup_and_preserves_local_ids(tmp_path):
    database_path = tmp_path / "collective_mindgraph.sqlite3"
    with closing(sqlite3.connect(database_path)) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (2, ?)",
            (datetime.now(tz=UTC).isoformat(),),
        )
        connection.execute(
            """
            INSERT INTO meetings(
                id, title, status, input_device, created_at, updated_at
            ) VALUES (41, 'Existing v2 meeting', 'ready', NULL, ?, ?)
            """,
            (
                datetime.now(tz=UTC).isoformat(),
                datetime.now(tz=UTC).isoformat(),
            ),
        )
        connection.commit()

    report = LegacyDataMigrator(database_path).run()

    assert report.migrated
    assert report.backup_path is not None and report.backup_path.exists()
    with closing(sqlite3.connect(report.backup_path)) as backup:
        backup_columns = {str(row[1]) for row in backup.execute("PRAGMA table_info(meetings)")}
        assert "workspace_id" not in backup_columns
        assert backup.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 2
    database = SqliteDatabase(database_path)
    meeting = SqliteMeetingStore(database).get(MeetingId(41))
    identity = SqliteWorkspaceStore(database).get_identity("meetings", 41)
    assert meeting is not None and meeting.title == "Existing v2 meeting"
    assert identity is not None
    assert UUID(str(identity.sync_id)).version == 4
    with database.connect() as connection:
        assert sync_identity_violations(connection) == {}
    second = LegacyDataMigrator(database_path).run()
    assert not second.migrated
    assert second.backup_path is None


@pytest.mark.parametrize("legacy_version", [3, 4])
def test_v3_and_v4_exports_remain_importable(tmp_path, legacy_version):
    source_database = SqliteDatabase(tmp_path / "source.sqlite3")
    initialize_schema(source_database)
    source_meetings = SqliteMeetingStore(source_database)
    meeting = source_meetings.create(
        title="Legacy compatible",
        status=MeetingStatus.READY,
        input_device=None,
        now=datetime.now(tz=UTC),
    )
    exported = SqliteDataExchange(source_database).export()
    exported["format_version"] = legacy_version
    tables = exported["tables"]
    assert isinstance(tables, dict)
    for table in ("workspaces", "comments", "activity_events"):
        tables.pop(table)
    for rows in tables.values():
        assert isinstance(rows, list)
        for row in rows:
            if isinstance(row, dict):
                for column in (
                    "workspace_id",
                    "sync_id",
                    "local_revision",
                    "sync_revision",
                    "updated_by_device",
                ):
                    row.pop(column, None)

    target_database = SqliteDatabase(tmp_path / f"target-{legacy_version}.sqlite3")
    initialize_schema(target_database)
    imported = SqliteDataExchange(target_database).import_payload(exported)
    target_identity = SqliteWorkspaceStore(target_database).get_identity(
        "meetings",
        int(meeting.id),
    )

    assert imported["meetings"] == 1
    assert target_identity is not None
    assert UUID(str(target_identity.sync_id)).version == 4


def test_legacy_graph_import_preserves_evidence_edges_and_ignores_invalid_rows(tmp_path):
    database = SqliteDatabase(tmp_path / "target.sqlite3")
    initialize_schema(database)
    payload: dict[str, object] = {
        "session": {"title": "Complete legacy graph"},
        "v2_production_graph": {
            "source_references": [
                "invalid",
                {"id": "ref-1", "text_preview": "Evidence"},
                {"id": "ref-1", "text_preview": "Duplicate"},
            ],
            "nodes": [
                "invalid",
                {
                    "id": "node-1",
                    "type": "DECISION",
                    "title": "Decision",
                    "source_reference_id": "ref-1",
                },
                {
                    "id": "node-1",
                    "type": "DECISION",
                    "title": "Duplicate",
                },
                {"id": "node-2", "type": "TOPIC", "title": "Topic"},
            ],
            "edges": [
                "invalid",
                {
                    "id": "missing-edge",
                    "source_node_id": "missing",
                    "target_node_id": "node-2",
                },
                {
                    "id": "edge-1",
                    "source_node_id": "node-1",
                    "target_node_id": "node-2",
                    "edge_type": "RELATED_TO",
                    "source_reference_id": "ref-1",
                },
            ],
        },
    }

    imported = SqliteDataExchange(database).import_payload(payload)

    assert imported == {
        "meetings": 1,
        "evidence_references": 1,
        "knowledge_nodes": 2,
        "knowledge_edges": 1,
    }


def test_v5_roundtrip_preserves_global_identity(tmp_path):
    source_database = SqliteDatabase(tmp_path / "source.sqlite3")
    initialize_schema(source_database)
    meeting = SqliteMeetingStore(source_database).create(
        title="Global identity",
        status=MeetingStatus.READY,
        input_device=None,
        now=datetime.now(tz=UTC),
    )
    source_identity = SqliteWorkspaceStore(source_database).get_identity(
        "meetings",
        int(meeting.id),
    )
    payload = SqliteDataExchange(source_database).export()

    target_database = SqliteDatabase(tmp_path / "target.sqlite3")
    initialize_schema(target_database)
    exchange = SqliteDataExchange(target_database)
    first = exchange.import_payload(json.loads(json.dumps(payload)))
    second = exchange.import_payload(json.loads(json.dumps(payload)))
    target_identity = SqliteWorkspaceStore(target_database).get_identity(
        "meetings",
        int(meeting.id),
    )

    assert first["meetings"] == 1
    assert second["meetings"] == 0
    assert source_identity is not None
    assert target_identity == source_identity


def test_meeting_scoped_v5_export_filters_every_table_path(tmp_path):
    database = SqliteDatabase(tmp_path / "source.sqlite3")
    initialize_schema(database)
    meetings = SqliteMeetingStore(database)
    selected = meetings.create(
        title="Selected",
        status=MeetingStatus.READY,
        input_device=None,
        now=datetime.now(tz=UTC),
    )
    meetings.create(
        title="Excluded",
        status=MeetingStatus.DRAFT,
        input_device=None,
        now=datetime.now(tz=UTC),
    )

    payload = SqliteDataExchange(database).export(selected.id)
    tables = payload["tables"]

    assert isinstance(tables, dict)
    assert [row["id"] for row in tables["meetings"]] == [int(selected.id)]
    assert len(tables["workspaces"]) == 1
    assert set(tables) >= {
        "transcript_segments",
        "knowledge_edges",
        "embeddings",
        "comments",
        "activity_events",
    }


def test_canonical_import_rejects_malformed_rows_duplicates_and_constraints(tmp_path):
    database = SqliteDatabase(tmp_path / "target.sqlite3")
    initialize_schema(database)
    exchange = SqliteDataExchange(database)

    with pytest.raises(ValueError, match="must be a list"):
        exchange.import_payload({"format_version": 5, "tables": {"meetings": {"id": 1}}})
    with pytest.raises(ValueError, match="invalid row"):
        exchange.import_payload({"format_version": 5, "tables": {"meetings": [1]}})
    with pytest.raises(ValueError, match="without an id"):
        exchange.import_payload({"format_version": 5, "tables": {"meetings": [{}]}})

    source = SqliteDatabase(tmp_path / "source.sqlite3")
    initialize_schema(source)
    SqliteMeetingStore(source).create(
        title="Import validation",
        status=MeetingStatus.READY,
        input_device=None,
        now=datetime.now(tz=UTC),
    )
    payload = SqliteDataExchange(source).export()
    duplicate_payload = json.loads(json.dumps(payload))
    duplicate_payload["tables"]["meetings"].append(dict(duplicate_payload["tables"]["meetings"][0]))
    with pytest.raises(ValueError, match="duplicate id"):
        exchange.import_payload(duplicate_payload)

    invalid_status_payload = json.loads(json.dumps(payload))
    invalid_status_payload["tables"]["meetings"][0]["status"] = "invalid"
    with pytest.raises(ValueError, match="canonical data constraints"):
        exchange.import_payload(invalid_status_payload)

    with pytest.raises(ValueError, match="Unsupported"):
        columns_for_import(99)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("sync_id", "not-a-uuid", "invalid sync_id"),
        ("workspace_id", None, "invalid workspace_id"),
        ("updated_by_device", "not-a-uuid", "invalid updated_by_device"),
        ("local_revision", 0, "invalid local_revision"),
        ("sync_revision", -1, "invalid sync_revision"),
    ],
)
def test_v5_import_rejects_invalid_sync_metadata(tmp_path, field, value, message):
    source = SqliteDatabase(tmp_path / "source.sqlite3")
    initialize_schema(source)
    SqliteMeetingStore(source).create(
        title="Sync validation",
        status=MeetingStatus.READY,
        input_device=None,
        now=datetime.now(tz=UTC),
    )
    payload = SqliteDataExchange(source).export()
    payload["tables"]["meetings"][0][field] = value
    target = SqliteDatabase(tmp_path / "target.sqlite3")
    initialize_schema(target)

    with pytest.raises(ValueError, match=message):
        SqliteDataExchange(target).import_payload(payload)


def test_default_backup_is_authenticated_encrypted_cmgbackup(tmp_path):
    database = SqliteDatabase(tmp_path / "source.sqlite3")
    initialize_schema(database)
    meeting = SqliteMeetingStore(database).create(
        title="Encrypted private title",
        status=MeetingStatus.DRAFT,
        input_device=None,
        now=datetime.now(tz=UTC),
    )
    exchange = SqliteDataExchange(database)
    backup_path = tmp_path / "workspace.cmgbackup"

    written = exchange.export_backup(
        backup_path,
        passphrase="correct horse battery staple",
    )

    assert written == backup_path.resolve()
    archive = json.loads(backup_path.read_text(encoding="utf-8"))
    assert archive["format"] == BACKUP_FORMAT
    assert "Encrypted private title" not in backup_path.read_text(encoding="utf-8")

    target = SqliteDatabase(tmp_path / "target.sqlite3")
    initialize_schema(target)
    imported = SqliteDataExchange(target).import_backup(
        backup_path,
        passphrase="correct horse battery staple",
    )
    restored = SqliteMeetingStore(target).get(meeting.id)
    assert imported["meetings"] == 1
    assert restored is not None and restored.title == "Encrypted private title"


def test_encrypted_backup_rejects_wrong_password_tampering_and_wrong_suffix(tmp_path):
    database = SqliteDatabase(tmp_path / "source.sqlite3")
    initialize_schema(database)
    exchange = SqliteDataExchange(database)
    backup_path = exchange.export_backup(
        tmp_path / "workspace.cmgbackup",
        passphrase="correct horse battery staple",
    )

    with pytest.raises(InvalidBackupError):
        exchange.import_backup(
            backup_path,
            passphrase="incorrect horse battery staple",
        )

    archive = json.loads(backup_path.read_text(encoding="utf-8"))
    replacement = "B" if archive["ciphertext"].startswith("A") else "A"
    archive["ciphertext"] = f"{replacement}{archive['ciphertext'][1:]}"
    backup_path.write_text(json.dumps(archive), encoding="utf-8")
    with pytest.raises(InvalidBackupError):
        exchange.import_backup(
            backup_path,
            passphrase="correct horse battery staple",
        )

    with pytest.raises(ValueError, match=r"\.cmgbackup"):
        exchange.export_backup(
            tmp_path / "workspace.json",
            passphrase="correct horse battery staple",
        )
    with pytest.raises(ValueError, match="at least 12"):
        exchange.export_backup(
            tmp_path / "short.cmgbackup",
            passphrase="too short",
        )


def test_encrypted_backup_rejects_malformed_cryptographic_metadata(tmp_path):
    database = SqliteDatabase(tmp_path / "source.sqlite3")
    initialize_schema(database)
    exchange = SqliteDataExchange(database)
    backup_path = exchange.export_backup(
        tmp_path / "workspace.cmgbackup",
        passphrase="correct horse battery staple",
    )
    valid = json.loads(backup_path.read_text(encoding="utf-8"))
    malformed: list[object] = [
        [],
        {**valid, "format": "unknown"},
        {**valid, "kdf": None},
        {**valid, "kdf": {**valid["kdf"], "name": "unknown"}},
        {**valid, "kdf": {**valid["kdf"], "salt": "AA=="}},
        {**valid, "ciphertext": 42},
    ]

    for index, archive in enumerate(malformed):
        candidate = tmp_path / f"malformed-{index}.cmgbackup"
        candidate.write_text(json.dumps(archive), encoding="utf-8")
        with pytest.raises(InvalidBackupError):
            exchange.import_backup(
                candidate,
                passphrase="correct horse battery staple",
            )


def test_sync_domain_rejects_invalid_ids_and_revisions():
    workspace_id = WorkspaceId(str(uuid4()))
    identity = SyncIdentity(
        workspace_id=workspace_id,
        sync_id=SyncId(str(uuid4())),
        local_revision=1,
        sync_revision=0,
    )
    assert identity.local_revision == 1

    with pytest.raises(ValueError, match="UUID"):
        SyncOperation(
            operation_id="not-a-uuid",  # type: ignore[arg-type]
            workspace_id=workspace_id,
            object_id=SyncId(str(uuid4())),
            object_type="meeting",
            base_revision=0,
            local_revision=1,
            client_timestamp=datetime.now(tz=UTC),
        )
    with pytest.raises(ValueError, match="Local revision"):
        SyncIdentity(
            workspace_id=workspace_id,
            sync_id=SyncId(str(uuid4())),
            local_revision=0,
            sync_revision=0,
        )

    now = datetime.now(tz=UTC)
    with pytest.raises(ValueError, match="name"):
        Workspace(
            id=workspace_id,
            sync_id=SyncId(str(uuid4())),
            name=" ",
            kind=WorkspaceKind.LOCAL,
            created_at=now,
            updated_at=now,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        Workspace(
            id=workspace_id,
            sync_id=SyncId(str(uuid4())),
            name="Workspace",
            kind=WorkspaceKind.LOCAL,
            created_at=datetime.now(),
            updated_at=now,
        )
    with pytest.raises(ValueError, match="Updated-by"):
        SyncIdentity(
            workspace_id=workspace_id,
            sync_id=SyncId(str(uuid4())),
            local_revision=1,
            sync_revision=0,
            updated_by_device=DeviceId("invalid"),
        )
    with pytest.raises(ValueError, match="object type"):
        SyncOperation(
            operation_id=OperationId(str(uuid4())),
            workspace_id=workspace_id,
            object_id=SyncId(str(uuid4())),
            object_type=" ",
            base_revision=0,
            local_revision=1,
            client_timestamp=now,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        SyncOperation(
            operation_id=OperationId(str(uuid4())),
            workspace_id=workspace_id,
            object_id=SyncId(str(uuid4())),
            object_type="meeting",
            base_revision=0,
            local_revision=1,
            client_timestamp=datetime.now(),
        )
    with pytest.raises(ValueError, match="cannot be negative"):
        SyncIdentity(
            workspace_id=workspace_id,
            sync_id=SyncId(str(uuid4())),
            local_revision=1,
            sync_revision=-1,
        )


def test_workspace_store_reads_lists_and_reports_missing_identities(tmp_path):
    database = SqliteDatabase(tmp_path / "collective_mindgraph.sqlite3")
    initialize_schema(database)
    store = SqliteWorkspaceStore(database)
    local = store.local_workspace()

    assert store.get(local.id) == local
    assert store.list() == (local,)
    assert store.get(WorkspaceId(str(uuid4()))) is None
    assert store.get_identity("meetings", 999) is None
    with pytest.raises(ValueError, match="Unsupported"):
        store.get_identity("unknown", 1)


def test_identity_validation_and_missing_local_workspace_are_detected(tmp_path):
    database = SqliteDatabase(tmp_path / "collective_mindgraph.sqlite3")
    initialize_schema(database)
    meeting = SqliteMeetingStore(database).create(
        title="Invalid identity",
        status=MeetingStatus.READY,
        input_device=None,
        now=datetime.now(tz=UTC),
    )
    with database.connect() as connection:
        connection.execute(
            "UPDATE meetings SET updated_by_device = NULL WHERE id = ?",
            (int(meeting.id),),
        )
        connection.execute("UPDATE workspaces SET sync_id = 'invalid' WHERE is_local = 1")
        assert sync_identity_violations(connection) == {
            "meetings": 1,
            "workspaces": 1,
        }
    with pytest.raises(RuntimeError, match="invalid sync identities"):
        LegacyDataMigrator._validate_database(database, [], {})

    with database.connect() as connection:
        connection.execute("DELETE FROM devices WHERE is_current = 1")
        with pytest.raises(RuntimeError, match="not initialized"):
            current_local_workspace(connection)
        connection.execute("DELETE FROM workspaces WHERE is_local = 1")
    with pytest.raises(RuntimeError, match="not initialized"):
        SqliteWorkspaceStore(database).local_workspace()


def test_every_synchronized_table_declares_identity_columns(tmp_path):
    database = SqliteDatabase(tmp_path / "collective_mindgraph.sqlite3")
    initialize_schema(database)
    with database.connect() as connection:
        for table in SYNC_ENTITY_KEYS:
            columns = {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
            assert {
                "workspace_id",
                "sync_id",
                "local_revision",
                "sync_revision",
                "updated_by_device",
            } <= columns


def test_comment_activity_and_outbox_foundations_enforce_sync_invariants(tmp_path):
    database = SqliteDatabase(tmp_path / "collective_mindgraph.sqlite3")
    initialize_schema(database)
    workspace = SqliteWorkspaceStore(database).local_workspace()
    meeting = SqliteMeetingStore(database).create(
        title="Collaboration foundation",
        status=MeetingStatus.READY,
        input_device=None,
        now=datetime.now(tz=UTC),
    )
    now = datetime.now(tz=UTC).isoformat()
    meeting_identity = SqliteWorkspaceStore(database).get_identity(
        "meetings",
        int(meeting.id),
    )
    assert meeting_identity is not None
    object_sync_id = str(meeting_identity.sync_id)
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO comments(
                id, workspace_id, sync_id, meeting_id, target_type,
                target_sync_id, body, created_at, updated_at
            ) VALUES (?, ?, NULL, ?, 'meeting', ?, 'Comment', ?, ?)
            """,
            (str(uuid4()), str(workspace.id), int(meeting.id), object_sync_id, now, now),
        )
        connection.execute(
            """
            INSERT INTO activity_events(
                id, workspace_id, sync_id, meeting_id, event_kind, created_at
            ) VALUES (?, ?, NULL, ?, 'meeting_created', ?)
            """,
            (str(uuid4()), str(workspace.id), int(meeting.id), now),
        )
        identities = connection.execute(
            """
            SELECT sync_id, updated_by_device FROM comments
            UNION ALL
            SELECT sync_id, updated_by_device FROM activity_events
            """
        ).fetchall()
        assert all(row["sync_id"] and row["updated_by_device"] for row in identities)

        operation = (
            str(uuid4()),
            str(workspace.id),
            object_sync_id,
            "meeting",
            0,
            1,
            now,
            now,
        )
        connection.execute(
            """
            INSERT INTO sync_outbox(
                operation_id, workspace_id, object_id, object_type,
                base_revision, local_revision, client_timestamp, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            operation,
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO sync_outbox(
                    operation_id, workspace_id, object_id, object_type,
                    base_revision, local_revision, client_timestamp, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (str(uuid4()), *operation[1:]),
            )
