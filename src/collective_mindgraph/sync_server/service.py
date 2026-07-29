"""Composition of the repositories behind one authorized service facade."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from .authorization import AuthorizedOperations
from .blob_repository import BlobRepository
from .blob_service import BlobService
from .blob_storage import BlobStore, FilesystemBlobStore
from .contracts import Principal, PullPage, PushResult, Role, SyncOperationInput
from .database import SyncDatabase
from .device_service import DeviceService
from .membership_repository import MembershipRepository
from .notifications import CursorBroadcaster
from .principals import PrincipalResolver
from .settings import SyncServerSettings
from .sync_repository import SyncRepository
from .tables import memberships, tenants, usage_counters, workspaces


@dataclass(frozen=True, slots=True)
class WorkspaceSummary:
    """One workspace as the calling member sees it."""

    workspace_id: str
    name: str
    role: Role
    raw_audio_enabled: bool


class SyncService:
    """Every entry point authorizes before it touches sealed bytes."""

    def __init__(
        self,
        *,
        settings: SyncServerSettings,
        database: SyncDatabase,
        identities: PrincipalResolver,
        blob_store: BlobStore | None = None,
        broadcaster: CursorBroadcaster | None = None,
    ) -> None:
        self.settings = settings
        self.database = database
        self.identities = identities
        self.members = MembershipRepository()
        self.sync = SyncRepository(settings)
        self.operations = AuthorizedOperations(database, self.members)
        self.devices = DeviceService(self.operations)
        self.blobs = BlobService(
            self.operations,
            BlobRepository(settings, blob_store or FilesystemBlobStore(settings.blob_root)),
        )
        self.broadcaster = broadcaster or CursorBroadcaster()

    # Identity ------------------------------------------------------------

    async def principal(self, authorization: str | None) -> Principal:
        """Authenticate a caller and seat them in the default tenant."""

        identity = self.identities.resolve(authorization)
        async with self.database.begin() as connection:
            tenant_id = await self._default_tenant(connection)
            return await self.members.ensure_user(
                connection,
                tenant_id=tenant_id,
                issuer=identity.issuer,
                subject=identity.subject,
            )

    # Workspaces ----------------------------------------------------------

    async def create_workspace(
        self,
        principal: Principal,
        *,
        name: str,
        workspace_id: str | None = None,
    ) -> WorkspaceSummary:
        async with self.database.begin() as connection:
            identifier = await self.members.create_workspace(
                connection,
                tenant_id=principal.tenant_id,
                name=name,
                owner=principal,
                workspace_id=workspace_id,
            )
            await self.members.record_audit(
                connection,
                workspace_id=identifier,
                kind="workspace.created",
                principal=principal,
            )
        return WorkspaceSummary(
            workspace_id=identifier,
            name=name,
            role=Role.OWNER,
            raw_audio_enabled=False,
        )

    async def list_workspaces(self, principal: Principal) -> tuple[WorkspaceSummary, ...]:
        async with self.database.begin() as connection:
            rows = (
                await connection.execute(
                    select(
                        workspaces.c.id,
                        workspaces.c.name,
                        workspaces.c.raw_audio_enabled,
                        memberships.c.role,
                    )
                    .select_from(
                        workspaces.join(
                            memberships,
                            memberships.c.workspace_id == workspaces.c.id,
                        )
                    )
                    .where(
                        memberships.c.user_id == principal.user_id,
                        memberships.c.removed_at.is_(None),
                        workspaces.c.deleted_at.is_(None),
                    )
                    .order_by(workspaces.c.created_at, workspaces.c.id)
                )
            ).fetchall()
        return tuple(
            WorkspaceSummary(
                workspace_id=str(row.id),
                name=str(row.name),
                role=Role(str(row.role)),
                raw_audio_enabled=bool(row.raw_audio_enabled),
            )
            for row in rows
        )

    async def set_raw_audio(
        self,
        principal: Principal,
        *,
        workspace_id: str,
        enabled: bool,
    ) -> None:
        """Raw-audio sync is workspace opt-in and defaults to off."""

        async with self.operations.authorized(
            workspace_id=workspace_id,
            principal=principal,
            minimum=Role.ADMIN,
        ) as connection:
            await connection.execute(
                update(workspaces)
                .where(workspaces.c.id == workspace_id)
                .values(raw_audio_enabled=enabled)
            )
            await self.members.record_audit(
                connection,
                workspace_id=workspace_id,
                kind="workspace.raw_audio_enabled" if enabled else "workspace.raw_audio_disabled",
                principal=principal,
            )

    # Synchronization -----------------------------------------------------

    async def push(
        self,
        principal: Principal,
        *,
        workspace_id: str,
        device_id: str,
        operations: Sequence[SyncOperationInput],
    ) -> PushResult:
        async with self.operations.authorized(
            workspace_id=workspace_id,
            principal=principal,
            minimum=Role.EDITOR,
        ) as connection:
            await self.members.authorize_device(
                connection,
                workspace_id=workspace_id,
                principal=principal,
                device_id=device_id,
            )
            result = await self.sync.push(
                connection,
                workspace_id=workspace_id,
                device_id=device_id,
                operations=operations,
            )
            await self.members.record_audit(
                connection,
                workspace_id=workspace_id,
                kind="sync.push",
                principal=principal,
                device_id=device_id,
                detail=f"{len(operations)} operation(s)",
            )
        await self.broadcaster.publish(workspace_id, result.cursor)
        return result

    async def pull(
        self,
        principal: Principal,
        *,
        workspace_id: str,
        cursor: str,
        limit: int | None = None,
    ) -> PullPage:
        async with self.operations.authorized(
            workspace_id=workspace_id,
            principal=principal,
            minimum=Role.VIEWER,
        ) as connection:
            return await self.sync.pull(
                connection,
                workspace_id=workspace_id,
                cursor=cursor,
                limit=limit,
            )

    # Accounting ----------------------------------------------------------

    async def usage(self, principal: Principal, *, workspace_id: str) -> dict[str, int]:
        """Report content-free quota counters."""

        async with self.operations.authorized(
            workspace_id=workspace_id,
            principal=principal,
            minimum=Role.VIEWER,
        ) as connection:
            row = (
                await connection.execute(
                    select(usage_counters).where(usage_counters.c.workspace_id == workspace_id)
                )
            ).fetchone()
        if row is None:
            return {"object_count": 0, "ciphertext_bytes": 0, "blob_bytes": 0}
        return {
            "object_count": int(row.object_count),
            "ciphertext_bytes": int(row.ciphertext_bytes),
            "blob_bytes": int(row.blob_bytes),
        }

    async def purge_expired(self, *, now: datetime | None = None) -> dict[str, int]:
        """Apply every retention window in one pass."""

        moment = now or datetime.now(tz=UTC)
        async with self.database.begin() as connection:
            objects = await self.sync.purge_expired(connection, now=moment)
            blobs = await self.blobs.purge_expired(connection, now=moment)
            audit = await self.members.purge_expired_audit(
                connection,
                now=moment,
                retention_days=self.settings.audit_retention_days,
            )
        return {"objects": objects, "blobs": blobs, "audit_events": audit}

    async def _default_tenant(self, connection: AsyncConnection) -> str:
        row = (
            await connection.execute(select(tenants.c.id).order_by(tenants.c.created_at).limit(1))
        ).fetchone()
        if row is not None:
            return str(row.id)
        return await self.members.ensure_tenant(connection, name="default")


__all__ = ["SyncService", "WorkspaceSummary"]
