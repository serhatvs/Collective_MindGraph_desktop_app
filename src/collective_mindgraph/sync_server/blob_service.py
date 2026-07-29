"""Authorized entry points for resumable encrypted-blob transfer."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncConnection

from .authorization import AuthorizedOperations
from .blob_repository import BlobManifest, BlobRepository
from .contracts import Principal, Role


class BlobService:
    """Every call proves a role before touching sealed chunks."""

    def __init__(self, operations: AuthorizedOperations, blobs: BlobRepository) -> None:
        self._operations = operations
        self._blobs = blobs

    async def initiate(
        self,
        principal: Principal,
        *,
        workspace_id: str,
        object_id: str,
        total_chunks: int,
        sha256: str,
    ) -> BlobManifest:
        """Open or resume an upload; the repository enforces the opt-in."""

        async with self._operations.authorized(
            workspace_id=workspace_id,
            principal=principal,
            minimum=Role.EDITOR,
        ) as connection:
            return await self._blobs.initiate(
                connection,
                workspace_id=workspace_id,
                object_id=object_id,
                total_chunks=total_chunks,
                declared_sha256=sha256,
            )

    async def upload_chunk(
        self,
        principal: Principal,
        *,
        workspace_id: str,
        manifest_id: str,
        chunk_index: int,
        payload: bytes,
    ) -> BlobManifest:
        async with self._operations.authorized(
            workspace_id=workspace_id,
            principal=principal,
            minimum=Role.EDITOR,
        ) as connection:
            return await self._blobs.upload_chunk(
                connection,
                manifest_id=manifest_id,
                chunk_index=chunk_index,
                payload=payload,
            )

    async def complete(
        self,
        principal: Principal,
        *,
        workspace_id: str,
        manifest_id: str,
    ) -> BlobManifest:
        """Accept a blob only when the reassembled digest matches."""

        async with self._operations.authorized(
            workspace_id=workspace_id,
            principal=principal,
            minimum=Role.EDITOR,
        ) as connection:
            manifest = await self._blobs.complete(connection, manifest_id=manifest_id)
            await self._operations.members.record_audit(
                connection,
                workspace_id=workspace_id,
                kind="blob.completed",
                principal=principal,
                object_id=manifest.object_id,
            )
            return manifest

    async def purge_expired(self, connection: AsyncConnection, *, now: datetime) -> int:
        """Apply the blob retention window.

        This is an operator path driven by ``mindgraph-admin``; it carries no
        principal because it acts on the deployment rather than for a caller.
        """

        return await self._blobs.purge_expired(connection, now=now)

    async def read(
        self,
        principal: Principal,
        *,
        workspace_id: str,
        manifest_id: str,
    ) -> bytes:
        async with self._operations.authorized(
            workspace_id=workspace_id,
            principal=principal,
            minimum=Role.VIEWER,
        ) as connection:
            return await self._blobs.read(connection, manifest_id=manifest_id)


__all__ = ["BlobService"]
