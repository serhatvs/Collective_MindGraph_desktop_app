"""Tenant, workspace, membership, device, and envelope persistence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from .contracts import (
    AccessDeniedError,
    Principal,
    Role,
    WorkspaceNotFoundError,
)
from .tables import (
    audit_events,
    devices,
    key_envelopes,
    memberships,
    tenants,
    user_subjects,
    workspace_cursors,
    workspaces,
)


class MembershipRepository:
    """Owns who may act on a workspace and which devices hold key envelopes."""

    async def ensure_tenant(self, connection: AsyncConnection, *, name: str) -> str:
        tenant_id = str(uuid4())
        await connection.execute(
            tenants.insert().values(id=tenant_id, name=name, created_at=_now())
        )
        return tenant_id

    async def ensure_user(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: str,
        issuer: str,
        subject: str,
    ) -> Principal:
        """Return the principal for an identity, creating it on first sight."""

        row = (
            await connection.execute(
                select(user_subjects).where(
                    user_subjects.c.issuer == issuer,
                    user_subjects.c.subject == subject,
                )
            )
        ).fetchone()
        if row is not None:
            return Principal(
                user_id=str(row.id),
                tenant_id=str(row.tenant_id),
                issuer=issuer,
                subject=subject,
            )
        user_id = str(uuid4())
        await connection.execute(
            user_subjects.insert().values(
                id=user_id,
                tenant_id=tenant_id,
                issuer=issuer,
                subject=subject,
                created_at=_now(),
            )
        )
        return Principal(user_id=user_id, tenant_id=tenant_id, issuer=issuer, subject=subject)

    async def create_workspace(
        self,
        connection: AsyncConnection,
        *,
        tenant_id: str,
        name: str,
        owner: Principal,
        workspace_id: str | None = None,
    ) -> str:
        """Create a workspace and seat its owner."""

        identifier = workspace_id or str(uuid4())
        await connection.execute(
            workspaces.insert().values(
                id=identifier,
                tenant_id=tenant_id,
                name=name,
                raw_audio_enabled=False,
                created_at=_now(),
            )
        )
        await connection.execute(
            workspace_cursors.insert().values(workspace_id=identifier, next_sequence=1)
        )
        await self.upsert_membership(
            connection,
            workspace_id=identifier,
            user_id=owner.user_id,
            role=Role.OWNER,
        )
        return identifier

    async def upsert_membership(
        self,
        connection: AsyncConnection,
        *,
        workspace_id: str,
        user_id: str,
        role: Role,
    ) -> None:
        """Seat or re-seat one member, clearing any earlier removal."""

        updated = await connection.execute(
            update(memberships)
            .where(
                memberships.c.workspace_id == workspace_id,
                memberships.c.user_id == user_id,
            )
            .values(role=role.value, removed_at=None)
        )
        if updated.rowcount == 0:
            await connection.execute(
                memberships.insert().values(
                    id=str(uuid4()),
                    workspace_id=workspace_id,
                    user_id=user_id,
                    role=role.value,
                    created_at=_now(),
                )
            )

    async def remove_membership(
        self,
        connection: AsyncConnection,
        *,
        workspace_id: str,
        user_id: str,
    ) -> None:
        """Mark a member removed without deleting the audit trail."""

        await connection.execute(
            update(memberships)
            .where(
                memberships.c.workspace_id == workspace_id,
                memberships.c.user_id == user_id,
            )
            .values(removed_at=_now())
        )

    async def require_role(
        self,
        connection: AsyncConnection,
        *,
        workspace_id: str,
        principal: Principal,
        minimum: Role,
    ) -> Role:
        """Resolve and authorize the caller's role for one workspace."""

        workspace = (
            await connection.execute(
                select(workspaces).where(
                    workspaces.c.id == workspace_id,
                    workspaces.c.deleted_at.is_(None),
                )
            )
        ).fetchone()
        if workspace is None:
            raise WorkspaceNotFoundError("The workspace does not exist.")
        row = (
            await connection.execute(
                select(memberships.c.role).where(
                    memberships.c.workspace_id == workspace_id,
                    memberships.c.user_id == principal.user_id,
                    memberships.c.removed_at.is_(None),
                )
            )
        ).fetchone()
        if row is None:
            raise AccessDeniedError("The caller is not a member of this workspace.")
        role = Role(str(row.role))
        if not _satisfies(role, minimum):
            raise AccessDeniedError(f"This action requires at least the {minimum.value} role.")
        return role

    # Devices -------------------------------------------------------------

    async def register_device(
        self,
        connection: AsyncConnection,
        *,
        workspace_id: str,
        principal: Principal,
        device_id: str,
        name: str,
        public_key: bytes,
        trust: str = "pending",
    ) -> None:
        """Record a device public key; the server never sees its private key."""

        updated = await connection.execute(
            update(devices)
            .where(devices.c.id == device_id)
            .values(name=name, public_key=public_key, trust=trust)
        )
        if updated.rowcount == 0:
            await connection.execute(
                devices.insert().values(
                    id=device_id,
                    workspace_id=workspace_id,
                    user_id=principal.user_id,
                    name=name,
                    public_key=public_key,
                    trust=trust,
                    created_at=_now(),
                )
            )

    async def authorize_device(
        self,
        connection: AsyncConnection,
        *,
        workspace_id: str,
        principal: Principal,
        device_id: str,
    ) -> None:
        """Reject pushes from unknown, foreign, or revoked devices."""

        row = (
            await connection.execute(select(devices).where(devices.c.id == device_id))
        ).fetchone()
        if row is None:
            raise AccessDeniedError("The device is not registered for this workspace.")
        if str(row.workspace_id) != workspace_id or str(row.user_id) != principal.user_id:
            raise AccessDeniedError("The device belongs to another workspace or user.")
        if str(row.trust) == "revoked":
            raise AccessDeniedError("The device has been revoked.")

    async def revoke_device(
        self,
        connection: AsyncConnection,
        *,
        workspace_id: str,
        device_id: str,
    ) -> None:
        """Revoke a device and every envelope wrapped for it."""

        now = _now()
        await connection.execute(
            update(devices)
            .where(devices.c.id == device_id, devices.c.workspace_id == workspace_id)
            .values(trust="revoked", revoked_at=now)
        )
        await connection.execute(
            update(key_envelopes)
            .where(
                key_envelopes.c.workspace_id == workspace_id,
                key_envelopes.c.recipient_device_id == device_id,
                key_envelopes.c.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

    async def store_envelope(
        self,
        connection: AsyncConnection,
        *,
        workspace_id: str,
        key_version: int,
        wrapped_key: bytes,
        recipient_device_id: str | None,
        ephemeral_public_key: bytes | None = None,
        salt: bytes | None = None,
    ) -> str:
        """Store one wrapped key. The service cannot unwrap what it stores."""

        recipient_matches = (
            key_envelopes.c.recipient_device_id.is_(None)
            if recipient_device_id is None
            else key_envelopes.c.recipient_device_id == recipient_device_id
        )
        await connection.execute(
            delete(key_envelopes).where(
                key_envelopes.c.workspace_id == workspace_id,
                key_envelopes.c.key_version == key_version,
                recipient_matches,
            )
        )
        envelope_id = str(uuid4())
        await connection.execute(
            key_envelopes.insert().values(
                id=envelope_id,
                workspace_id=workspace_id,
                recipient_device_id=recipient_device_id,
                key_version=key_version,
                wrapped_key=wrapped_key,
                ephemeral_public_key=ephemeral_public_key,
                salt=salt,
                created_at=_now(),
            )
        )
        return envelope_id

    async def envelopes_for_device(
        self,
        connection: AsyncConnection,
        *,
        workspace_id: str,
        device_id: str,
    ) -> tuple[Any, ...]:
        """Return every active envelope a device may still use."""

        rows = (
            await connection.execute(
                select(key_envelopes)
                .where(
                    key_envelopes.c.workspace_id == workspace_id,
                    key_envelopes.c.recipient_device_id == device_id,
                    key_envelopes.c.revoked_at.is_(None),
                )
                .order_by(key_envelopes.c.key_version)
            )
        ).fetchall()
        return tuple(rows)

    # Audit ---------------------------------------------------------------

    async def record_audit(
        self,
        connection: AsyncConnection,
        *,
        workspace_id: str,
        kind: str,
        principal: Principal | None = None,
        device_id: str | None = None,
        object_type: str | None = None,
        object_id: str | None = None,
        detail: str | None = None,
    ) -> None:
        """Append one content-free audit record."""

        await connection.execute(
            audit_events.insert().values(
                id=str(uuid4()),
                workspace_id=workspace_id,
                actor_user_id=principal.user_id if principal else None,
                actor_device_id=device_id,
                kind=kind,
                object_type=object_type,
                object_id=object_id,
                detail=detail,
                created_at=_now(),
            )
        )

    async def purge_expired_audit(
        self,
        connection: AsyncConnection,
        *,
        now: datetime,
        retention_days: int,
    ) -> int:
        """Delete audit records older than the configured window."""

        cutoff = now - timedelta(days=retention_days)
        removed = await connection.execute(
            delete(audit_events).where(audit_events.c.created_at < cutoff)
        )
        return int(removed.rowcount)


_ROLE_RANK = {
    Role.VIEWER: 0,
    Role.REVIEWER: 1,
    Role.EDITOR: 2,
    Role.ADMIN: 3,
    Role.OWNER: 4,
}


def _satisfies(role: Role, minimum: Role) -> bool:
    return _ROLE_RANK[role] >= _ROLE_RANK[minimum]


def _now() -> datetime:
    return datetime.now(tz=UTC)


__all__ = ["MembershipRepository"]
