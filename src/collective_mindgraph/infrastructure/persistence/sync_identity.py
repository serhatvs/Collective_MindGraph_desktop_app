"""Validation for persisted and exchanged synchronization identities."""

from __future__ import annotations

import sqlite3
from collections.abc import Collection, Mapping
from uuid import UUID

SYNC_ENTITY_KEYS: dict[str, str] = {
    "meetings": "id",
    "recordings": "id",
    "transcripts": "id",
    "transcript_segments": "id",
    "evidence_references": "id",
    "insights": "id",
    "knowledge_nodes": "id",
    "knowledge_edges": "id",
    "processing_jobs": "id",
    "comments": "id",
    "activity_events": "id",
}


def sync_identity_violations(connection: sqlite3.Connection) -> dict[str, int]:
    """Count invalid UUID or revision metadata without loading whole tables."""

    violations: dict[str, int] = {}
    for table in SYNC_ENTITY_KEYS:
        invalid = sum(
            1
            for row in connection.execute(
                f"""
                SELECT workspace_id, sync_id, local_revision,
                       sync_revision, updated_by_device
                FROM {table}
                """
            )
            if not _valid_identity_row(row)
        )
        if invalid:
            violations[table] = invalid

    invalid_workspaces = sum(
        1
        for row in connection.execute(
            """
            SELECT id AS workspace_id, sync_id, local_revision,
                   sync_revision, updated_by_device
            FROM workspaces
            """
        )
        if not _valid_identity_row(row)
    )
    if invalid_workspaces:
        violations["workspaces"] = invalid_workspaces
    return violations


def validate_export_sync_identity(
    table: str,
    columns: Collection[str],
    row: Mapping[object, object],
) -> None:
    """Reject invalid sync metadata before canonical rows reach SQLite."""

    uuid_fields = [
        field for field in ("workspace_id", "sync_id", "updated_by_device") if field in columns
    ]
    if table == "workspaces":
        uuid_fields.append("id")
    for field in uuid_fields:
        if not _is_uuid(row.get(field)):
            raise ValueError(f"Export table {table} contains an invalid {field}.")

    if "local_revision" in columns:
        local_revision = row.get("local_revision")
        sync_revision = row.get("sync_revision")
        if type(local_revision) is not int or local_revision < 1:
            raise ValueError(f"Export table {table} contains an invalid local_revision.")
        if type(sync_revision) is not int or sync_revision < 0:
            raise ValueError(f"Export table {table} contains an invalid sync_revision.")


def _valid_identity_row(row: sqlite3.Row) -> bool:
    return (
        _is_uuid(row["workspace_id"])
        and _is_uuid(row["sync_id"])
        and _is_uuid(row["updated_by_device"])
        and type(row["local_revision"]) is int
        and int(row["local_revision"]) >= 1
        and type(row["sync_revision"]) is int
        and int(row["sync_revision"]) >= 0
    )


def _is_uuid(value: object) -> bool:
    try:
        UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return False
    return True


__all__ = [
    "SYNC_ENTITY_KEYS",
    "sync_identity_violations",
    "validate_export_sync_identity",
]
