"""SQLite workspace and synchronization identity reads."""

from __future__ import annotations

import sqlite3

from collective_mindgraph.domain import (
    DeviceId,
    SyncId,
    SyncIdentity,
    Workspace,
    WorkspaceId,
    WorkspaceKind,
)

from .row_mapping import parse_timestamp
from .sqlite_database import SqliteDatabase
from .sync_identity import SYNC_ENTITY_KEYS


class SqliteWorkspaceStore:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def local_workspace(self) -> Workspace:
        with self._database.connect() as connection:
            row = connection.execute("SELECT * FROM workspaces WHERE is_local = 1").fetchone()
        if row is None:
            raise RuntimeError("Local workspace is not initialized.")
        return self._map_workspace(row)

    def get(self, workspace_id: WorkspaceId) -> Workspace | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM workspaces WHERE id = ?",
                (str(workspace_id),),
            ).fetchone()
        return self._map_workspace(row) if row is not None else None

    def list(self) -> tuple[Workspace, ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM workspaces ORDER BY is_local DESC, created_at, id"
            ).fetchall()
        return tuple(self._map_workspace(row) for row in rows)

    def get_identity(self, table: str, local_id: int | str) -> SyncIdentity | None:
        key_column = SYNC_ENTITY_KEYS.get(table)
        if key_column is None:
            raise ValueError("Unsupported synchronized entity table.")
        with self._database.connect() as connection:
            row = connection.execute(
                f"""
                SELECT workspace_id, sync_id, local_revision,
                       sync_revision, updated_by_device
                FROM {table}
                WHERE {key_column} = ?
                """,
                (local_id,),
            ).fetchone()
        if row is None:
            return None
        return SyncIdentity(
            workspace_id=WorkspaceId(str(row["workspace_id"])),
            sync_id=SyncId(str(row["sync_id"])),
            local_revision=int(row["local_revision"]),
            sync_revision=int(row["sync_revision"]),
            updated_by_device=(
                DeviceId(str(row["updated_by_device"])) if row["updated_by_device"] else None
            ),
        )

    @staticmethod
    def _map_workspace(row: sqlite3.Row) -> Workspace:
        return Workspace(
            id=WorkspaceId(str(row["id"])),
            sync_id=SyncId(str(row["sync_id"])),
            name=str(row["name"]),
            kind=WorkspaceKind(str(row["kind"])),
            local_revision=int(row["local_revision"]),
            sync_revision=int(row["sync_revision"]),
            updated_by_device=(
                DeviceId(str(row["updated_by_device"])) if row["updated_by_device"] else None
            ),
            created_at=parse_timestamp(str(row["created_at"])),
            updated_at=parse_timestamp(str(row["updated_at"])),
        )
