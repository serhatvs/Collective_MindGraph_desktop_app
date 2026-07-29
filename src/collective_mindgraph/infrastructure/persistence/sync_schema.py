"""Workspace identity and synchronization schema upgrade."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from .sync_identity import SYNC_ENTITY_KEYS

LOCAL_WORKSPACE_NAME = "Local Workspace"

SYNC_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    sync_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('local', 'cloud')),
    is_local INTEGER NOT NULL DEFAULT 0 CHECK (is_local IN (0, 1)),
    local_revision INTEGER NOT NULL DEFAULT 1 CHECK (local_revision >= 1),
    sync_revision INTEGER NOT NULL DEFAULT 0 CHECK (sync_revision >= 0),
    updated_by_device TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_workspaces_single_local
ON workspaces(is_local) WHERE is_local = 1;

CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    name TEXT NOT NULL,
    public_key BLOB,
    trust TEXT NOT NULL DEFAULT 'local' CHECK (
        trust IN ('local', 'pending', 'trusted', 'revoked')
    ),
    is_current INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0, 1)),
    revoked_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_devices_current
ON devices(is_current) WHERE is_current = 1;
CREATE INDEX IF NOT EXISTS idx_devices_workspace ON devices(workspace_id, trust);

CREATE TABLE IF NOT EXISTS sync_outbox (
    operation_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    object_id TEXT NOT NULL,
    object_type TEXT NOT NULL,
    base_revision INTEGER NOT NULL CHECK (base_revision >= 0),
    local_revision INTEGER NOT NULL CHECK (local_revision >= 1),
    payload_json TEXT NOT NULL DEFAULT '{}',
    ciphertext BLOB,
    nonce BLOB,
    key_version INTEGER,
    deleted INTEGER NOT NULL DEFAULT 0 CHECK (deleted IN (0, 1)),
    client_timestamp TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending' CHECK (
        state IN ('pending', 'pushing', 'failed')
    ),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    UNIQUE (workspace_id, object_id, local_revision)
);

CREATE INDEX IF NOT EXISTS idx_sync_outbox_pending
ON sync_outbox(state, created_at, operation_id);

CREATE TABLE IF NOT EXISTS sync_state (
    workspace_id TEXT PRIMARY KEY,
    remote_cursor TEXT,
    last_pushed_revision INTEGER NOT NULL DEFAULT 0,
    last_pull_at TEXT,
    last_push_at TEXT,
    last_error TEXT,
    backoff_until TEXT,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sync_tombstones (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    object_id TEXT NOT NULL,
    object_type TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    deleted_by_device TEXT,
    deleted_at TEXT NOT NULL,
    pushed INTEGER NOT NULL DEFAULT 0 CHECK (pushed IN (0, 1)),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    UNIQUE (workspace_id, object_id, revision)
);

CREATE TABLE IF NOT EXISTS conflict_versions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    object_id TEXT NOT NULL,
    object_type TEXT NOT NULL,
    local_revision INTEGER NOT NULL,
    remote_revision INTEGER NOT NULL,
    local_payload_json TEXT NOT NULL,
    remote_payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    resolution TEXT CHECK (
        resolution IS NULL OR resolution IN ('local', 'remote', 'merged')
    ),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_conflicts_unresolved
ON conflict_versions(workspace_id, resolved_at, created_at);

CREATE TABLE IF NOT EXISTS key_envelopes (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    recipient_device_id TEXT,
    key_version INTEGER NOT NULL CHECK (key_version >= 1),
    wrapped_key BLOB NOT NULL,
    ephemeral_public_key BLOB,
    salt BLOB,
    created_at TEXT NOT NULL,
    revoked_at TEXT,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    sync_id TEXT UNIQUE,
    meeting_id INTEGER,
    parent_id TEXT,
    target_type TEXT NOT NULL,
    target_sync_id TEXT NOT NULL,
    body TEXT NOT NULL,
    author_subject TEXT,
    local_revision INTEGER NOT NULL DEFAULT 1 CHECK (local_revision >= 1),
    sync_revision INTEGER NOT NULL DEFAULT 0 CHECK (sync_revision >= 0),
    updated_by_device TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES comments(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_comments_target
ON comments(workspace_id, target_type, target_sync_id, created_at);

CREATE TABLE IF NOT EXISTS activity_events (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    sync_id TEXT UNIQUE,
    meeting_id INTEGER,
    event_kind TEXT NOT NULL,
    object_type TEXT,
    object_sync_id TEXT,
    actor_subject TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    local_revision INTEGER NOT NULL DEFAULT 1 CHECK (local_revision >= 1),
    sync_revision INTEGER NOT NULL DEFAULT 0 CHECK (sync_revision >= 0),
    updated_by_device TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_activity_workspace
ON activity_events(workspace_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS model_registry (
    model_id TEXT NOT NULL,
    version TEXT NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('available', 'downloading', 'installed', 'failed', 'disabled')
    ),
    path TEXT,
    size_bytes INTEGER,
    sha256 TEXT,
    license TEXT,
    pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1)),
    installed_at TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (model_id, version)
);
"""


def upgrade_to_workspace_schema(connection: sqlite3.Connection) -> tuple[str, str]:
    """Install v3 tables and backfill every synchronized row."""

    connection.executescript(SYNC_SCHEMA_SQL)
    workspace_id, device_id = _ensure_local_workspace(connection)
    for table, key_column in SYNC_ENTITY_KEYS.items():
        _add_sync_columns(connection, table)
        _backfill_sync_identity(connection, table, key_column, workspace_id, device_id)
        _install_identity_indexes(connection, table)
        _install_identity_triggers(connection, table, key_column, workspace_id, device_id)
    connection.execute(
        "UPDATE workspaces SET updated_by_device = ? WHERE id = ?",
        (device_id, workspace_id),
    )
    connection.execute(
        "INSERT OR IGNORE INTO sync_state(workspace_id) VALUES (?)",
        (workspace_id,),
    )
    return workspace_id, device_id


def current_local_workspace(connection: sqlite3.Connection) -> tuple[str, str]:
    workspace = connection.execute("SELECT id FROM workspaces WHERE is_local = 1").fetchone()
    device = connection.execute("SELECT id FROM devices WHERE is_current = 1").fetchone()
    if workspace is None or device is None:
        raise RuntimeError("Local workspace identity is not initialized.")
    return str(workspace[0]), str(device[0])


def _ensure_local_workspace(connection: sqlite3.Connection) -> tuple[str, str]:
    now = datetime.now(tz=UTC).isoformat()
    workspace = connection.execute("SELECT id FROM workspaces WHERE is_local = 1").fetchone()
    if workspace is None:
        workspace_id = str(uuid4())
        connection.execute(
            """
            INSERT INTO workspaces(
                id, sync_id, name, kind, is_local, created_at, updated_at
            ) VALUES (?, ?, ?, 'local', 1, ?, ?)
            """,
            (workspace_id, workspace_id, LOCAL_WORKSPACE_NAME, now, now),
        )
    else:
        workspace_id = str(workspace[0])
    device = connection.execute("SELECT id FROM devices WHERE is_current = 1").fetchone()
    if device is None:
        device_id = str(uuid4())
        connection.execute(
            """
            INSERT INTO devices(
                id, workspace_id, name, trust, is_current, created_at, updated_at
            ) VALUES (?, ?, 'Local Device', 'local', 1, ?, ?)
            """,
            (device_id, workspace_id, now, now),
        )
    else:
        device_id = str(device[0])
    return workspace_id, device_id


def _add_sync_columns(connection: sqlite3.Connection, table: str) -> None:
    columns = _column_names(connection, table)
    definitions = (
        "workspace_id TEXT",
        "sync_id TEXT",
        "local_revision INTEGER NOT NULL DEFAULT 1",
        "sync_revision INTEGER NOT NULL DEFAULT 0",
        "updated_by_device TEXT",
    )
    for definition in definitions:
        column = definition.split(maxsplit=1)[0]
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def _backfill_sync_identity(
    connection: sqlite3.Connection,
    table: str,
    key_column: str,
    workspace_id: str,
    device_id: str,
) -> None:
    rows = connection.execute(
        f"""
        SELECT {key_column} FROM {table}
        WHERE workspace_id IS NULL OR sync_id IS NULL OR updated_by_device IS NULL
        """
    ).fetchall()
    for row in rows:
        connection.execute(
            f"""
            UPDATE {table}
            SET workspace_id = COALESCE(workspace_id, ?),
                sync_id = COALESCE(sync_id, ?),
                updated_by_device = COALESCE(updated_by_device, ?)
            WHERE {key_column} = ?
            """,
            (workspace_id, str(uuid4()), device_id, row[0]),
        )


def _install_identity_indexes(connection: sqlite3.Connection, table: str) -> None:
    connection.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{table}_sync_id ON {table}(sync_id)")
    connection.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{table}_workspace_revision
        ON {table}(workspace_id, local_revision)
        """
    )


def _install_identity_triggers(
    connection: sqlite3.Connection,
    table: str,
    key_column: str,
    workspace_id: str,
    device_id: str,
) -> None:
    uuid_expression = _uuid_expression()
    data_columns = [
        column
        for column in _column_names(connection, table)
        if column
        not in {
            key_column,
            "workspace_id",
            "sync_id",
            "local_revision",
            "sync_revision",
            "updated_by_device",
        }
    ]
    connection.executescript(
        f"""
        CREATE TRIGGER IF NOT EXISTS trg_{table}_sync_identity_insert
        AFTER INSERT ON {table}
        WHEN NEW.workspace_id IS NULL
          OR NEW.sync_id IS NULL
          OR NEW.updated_by_device IS NULL
        BEGIN
            UPDATE {table}
            SET workspace_id = COALESCE(NEW.workspace_id, '{workspace_id}'),
                sync_id = COALESCE(NEW.sync_id, {uuid_expression}),
                updated_by_device = COALESCE(NEW.updated_by_device, '{device_id}')
            WHERE {key_column} = NEW.{key_column};
        END;

        CREATE TRIGGER IF NOT EXISTS trg_{table}_local_revision_update
        AFTER UPDATE OF {", ".join(data_columns)} ON {table}
        WHEN NEW.local_revision <= OLD.local_revision
        BEGIN
            UPDATE {table}
            SET local_revision = OLD.local_revision + 1,
                updated_by_device = '{device_id}'
            WHERE {key_column} = NEW.{key_column};
        END;
        """
    )


def _uuid_expression() -> str:
    return """
    (
        lower(hex(randomblob(4))) || '-' ||
        lower(hex(randomblob(2))) || '-4' ||
        substr(lower(hex(randomblob(2))), 2) || '-' ||
        substr('89ab', abs(random()) % 4 + 1, 1) ||
        substr(lower(hex(randomblob(2))), 2) || '-' ||
        lower(hex(randomblob(6)))
    )
    """


def _column_names(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
