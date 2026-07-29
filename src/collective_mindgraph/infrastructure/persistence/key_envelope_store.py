"""SQLite persistence for device identities and wrapped workspace keys."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from collective_mindgraph.domain import DeviceKey, DeviceTrust, KeyEnvelope
from collective_mindgraph.domain.identifiers import DeviceId, EnvelopeId, WorkspaceId

from .row_mapping import parse_timestamp
from .sqlite_database import SqliteDatabase


class SqliteKeyEnvelopeStore:
    """Stores only wrapped key material; private keys never reach SQLite."""

    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    # Devices -------------------------------------------------------------

    def register_device(self, device: DeviceKey) -> None:
        """Insert or update one device identity without touching current-ness."""

        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO devices(
                    id, workspace_id, name, public_key, trust,
                    is_current, revoked_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    workspace_id = excluded.workspace_id,
                    name = excluded.name,
                    public_key = excluded.public_key,
                    trust = excluded.trust,
                    revoked_at = excluded.revoked_at,
                    updated_at = excluded.updated_at
                """,
                (
                    str(device.device_id),
                    str(device.workspace_id),
                    device.name,
                    device.public_key,
                    device.trust.value,
                    device.revoked_at.isoformat() if device.revoked_at else None,
                    device.created_at.isoformat(),
                    device.created_at.isoformat(),
                ),
            )

    def get_device(self, device_id: DeviceId) -> DeviceKey | None:
        """Return one enrolled device, or ``None`` when it has no public key."""

        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM devices WHERE id = ?",
                (str(device_id),),
            ).fetchone()
        if row is None or row["public_key"] is None:
            return None
        return _map_device(row)

    def current_device_id(self) -> DeviceId | None:
        """Return the identifier this installation uses for itself."""

        with self._database.connect() as connection:
            row = connection.execute("SELECT id FROM devices WHERE is_current = 1").fetchone()
        return DeviceId(str(row[0])) if row is not None else None

    def list_devices(self, workspace_id: WorkspaceId) -> tuple[DeviceKey, ...]:
        """Return every enrolled device holding a public key."""

        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM devices
                WHERE workspace_id = ? AND public_key IS NOT NULL
                ORDER BY created_at, id
                """,
                (str(workspace_id),),
            ).fetchall()
        return tuple(_map_device(row) for row in rows)

    def revoke_device(self, device_id: DeviceId, revoked_at: datetime) -> None:
        """Mark one device revoked so it can no longer receive key versions."""

        with self._database.connect() as connection:
            connection.execute(
                """
                UPDATE devices
                SET trust = 'revoked', revoked_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (revoked_at.isoformat(), revoked_at.isoformat(), str(device_id)),
            )

    # Envelopes -----------------------------------------------------------

    def save_envelope(self, envelope: KeyEnvelope) -> None:
        """Replace any prior envelope for the same recipient and key version."""

        recipient = (
            str(envelope.recipient_device_id) if envelope.recipient_device_id is not None else None
        )
        with self._database.connect() as connection:
            connection.execute(
                """
                DELETE FROM key_envelopes
                WHERE workspace_id = ? AND key_version = ?
                  AND recipient_device_id IS ?
                """,
                (str(envelope.workspace_id), envelope.key_version, recipient),
            )
            connection.execute(
                """
                INSERT INTO key_envelopes(
                    id, workspace_id, recipient_device_id, key_version,
                    wrapped_key, ephemeral_public_key, salt, created_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(envelope.id),
                    str(envelope.workspace_id),
                    recipient,
                    envelope.key_version,
                    envelope.wrapped_key,
                    envelope.ephemeral_public_key,
                    envelope.salt,
                    envelope.created_at.isoformat(),
                    envelope.revoked_at.isoformat() if envelope.revoked_at else None,
                ),
            )

    def latest_key_version(self, workspace_id: WorkspaceId) -> int:
        """Return the highest issued key version, or zero when none exists."""

        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT MAX(key_version) FROM key_envelopes WHERE workspace_id = ?",
                (str(workspace_id),),
            ).fetchone()
        return int(row[0]) if row is not None and row[0] is not None else 0

    def active_envelope_for_device(
        self,
        workspace_id: WorkspaceId,
        device_id: DeviceId,
        key_version: int | None = None,
    ) -> KeyEnvelope | None:
        """Return the newest usable envelope wrapped for one device."""

        return self._active_envelope(workspace_id, str(device_id), key_version)

    def active_recovery_envelope(
        self,
        workspace_id: WorkspaceId,
        key_version: int | None = None,
    ) -> KeyEnvelope | None:
        """Return the newest usable recovery envelope."""

        return self._active_envelope(workspace_id, None, key_version)

    def revoke_envelopes_for_device(
        self,
        workspace_id: WorkspaceId,
        device_id: DeviceId,
        revoked_at: datetime,
    ) -> int:
        """Revoke every envelope wrapped for one device and report the count."""

        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE key_envelopes
                SET revoked_at = ?
                WHERE workspace_id = ? AND recipient_device_id = ? AND revoked_at IS NULL
                """,
                (revoked_at.isoformat(), str(workspace_id), str(device_id)),
            )
            return int(cursor.rowcount)

    def _active_envelope(
        self,
        workspace_id: WorkspaceId,
        recipient: str | None,
        key_version: int | None,
    ) -> KeyEnvelope | None:
        clause = "" if key_version is None else " AND key_version = ?"
        parameters: list[object] = [str(workspace_id), recipient]
        if key_version is not None:
            parameters.append(key_version)
        with self._database.connect() as connection:
            row = connection.execute(
                f"""
                SELECT * FROM key_envelopes
                WHERE workspace_id = ? AND recipient_device_id IS ?
                  AND revoked_at IS NULL{clause}
                ORDER BY key_version DESC, created_at DESC
                LIMIT 1
                """,
                parameters,
            ).fetchone()
        return _map_envelope(row) if row is not None else None


def _map_device(row: sqlite3.Row) -> DeviceKey:
    revoked_at = row["revoked_at"]
    return DeviceKey(
        device_id=DeviceId(str(row["id"])),
        workspace_id=WorkspaceId(str(row["workspace_id"])),
        name=str(row["name"]),
        public_key=bytes(row["public_key"]),
        trust=DeviceTrust(str(row["trust"])),
        created_at=parse_timestamp(str(row["created_at"])),
        revoked_at=parse_timestamp(str(revoked_at)) if revoked_at else None,
    )


def _map_envelope(row: sqlite3.Row) -> KeyEnvelope:
    recipient = row["recipient_device_id"]
    ephemeral = row["ephemeral_public_key"]
    salt = row["salt"]
    revoked_at = row["revoked_at"]
    return KeyEnvelope(
        id=EnvelopeId(str(row["id"])),
        workspace_id=WorkspaceId(str(row["workspace_id"])),
        key_version=int(row["key_version"]),
        wrapped_key=bytes(row["wrapped_key"]),
        created_at=parse_timestamp(str(row["created_at"])),
        recipient_device_id=DeviceId(str(recipient)) if recipient else None,
        ephemeral_public_key=bytes(ephemeral) if ephemeral is not None else None,
        salt=bytes(salt) if salt is not None else None,
        revoked_at=parse_timestamp(str(revoked_at)) if revoked_at else None,
    )


__all__ = ["SqliteKeyEnvelopeStore"]
