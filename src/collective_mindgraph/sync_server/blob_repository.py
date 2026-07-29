"""Resumable, integrity-checked uploads for encrypted blobs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from .blob_storage import BlobStore, chunk_storage_key, digest, manifest_prefix
from .contracts import BlobRejectedError
from .settings import SyncServerSettings
from .tables import blob_chunks, blob_manifests, usage_counters, workspaces


@dataclass(frozen=True, slots=True)
class BlobManifest:
    """Upload state a client resumes against."""

    id: str
    workspace_id: str
    object_id: str
    chunk_bytes: int
    total_chunks: int
    declared_sha256: str
    state: str
    received_chunks: tuple[int, ...] = ()

    @property
    def missing_chunks(self) -> tuple[int, ...]:
        received = set(self.received_chunks)
        return tuple(index for index in range(self.total_chunks) if index not in received)


class BlobRepository:
    """Owns the manifest state machine and per-chunk verification."""

    def __init__(self, settings: SyncServerSettings, store: BlobStore) -> None:
        self._settings = settings
        self._store = store

    async def initiate(
        self,
        connection: AsyncConnection,
        *,
        workspace_id: str,
        object_id: str,
        total_chunks: int,
        declared_sha256: str,
    ) -> BlobManifest:
        """Open or resume an upload after checking the workspace opt-in."""

        await self._require_raw_audio_enabled(connection, workspace_id)
        if total_chunks < 1:
            raise BlobRejectedError("A blob upload requires at least one chunk.")
        if not _is_sha256(declared_sha256):
            raise BlobRejectedError("The declared digest must be a SHA-256 hex string.")
        existing = await self._load(connection, workspace_id=workspace_id, object_id=object_id)
        if existing is not None:
            if existing.state == "complete":
                raise BlobRejectedError("The blob has already been completed.")
            if existing.declared_sha256 != declared_sha256:
                raise BlobRejectedError(
                    "A pending upload for this object declares a different digest."
                )
            return existing
        manifest_id = str(uuid4())
        await connection.execute(
            blob_manifests.insert().values(
                id=manifest_id,
                workspace_id=workspace_id,
                object_id=object_id,
                chunk_bytes=self._settings.blob_chunk_bytes,
                total_chunks=total_chunks,
                declared_sha256=declared_sha256,
                state="pending",
                size_bytes=0,
                created_at=_now(),
            )
        )
        return BlobManifest(
            id=manifest_id,
            workspace_id=workspace_id,
            object_id=object_id,
            chunk_bytes=self._settings.blob_chunk_bytes,
            total_chunks=total_chunks,
            declared_sha256=declared_sha256,
            state="pending",
        )

    async def upload_chunk(
        self,
        connection: AsyncConnection,
        *,
        manifest_id: str,
        chunk_index: int,
        payload: bytes,
    ) -> BlobManifest:
        """Store one sealed chunk, rejecting oversized or misplaced parts."""

        manifest = await self._require_pending(connection, manifest_id)
        if not 0 <= chunk_index < manifest.total_chunks:
            raise BlobRejectedError("The chunk index is outside the declared manifest.")
        if len(payload) > manifest.chunk_bytes:
            raise BlobRejectedError("The chunk exceeds the configured chunk size.")
        if chunk_index < manifest.total_chunks - 1 and len(payload) != manifest.chunk_bytes:
            raise BlobRejectedError("Only the final chunk may be shorter than the chunk size.")
        if not payload:
            raise BlobRejectedError("A chunk cannot be empty.")
        storage_key = chunk_storage_key(manifest.workspace_id, manifest.id, chunk_index)
        self._store.put(storage_key, payload)
        await connection.execute(
            delete(blob_chunks).where(
                blob_chunks.c.manifest_id == manifest.id,
                blob_chunks.c.chunk_index == chunk_index,
            )
        )
        await connection.execute(
            blob_chunks.insert().values(
                manifest_id=manifest.id,
                chunk_index=chunk_index,
                sha256=digest(payload),
                size_bytes=len(payload),
                storage_key=storage_key,
                uploaded_at=_now(),
            )
        )
        return await self._require_pending(connection, manifest_id)

    async def complete(
        self,
        connection: AsyncConnection,
        *,
        manifest_id: str,
    ) -> BlobManifest:
        """Verify the reassembled ciphertext digest before accepting a blob."""

        manifest = await self._require_pending(connection, manifest_id)
        missing = manifest.missing_chunks
        if missing:
            raise BlobRejectedError(f"The upload is missing {len(missing)} chunk(s).")
        rows = (
            await connection.execute(
                select(blob_chunks)
                .where(blob_chunks.c.manifest_id == manifest.id)
                .order_by(blob_chunks.c.chunk_index)
            )
        ).fetchall()
        hasher = hashlib.sha256()
        total = 0
        for row in rows:
            payload = self._store.get(str(row.storage_key))
            if digest(payload) != str(row.sha256):
                raise BlobRejectedError("A stored chunk no longer matches its recorded digest.")
            hasher.update(payload)
            total += len(payload)
        if hasher.hexdigest() != manifest.declared_sha256:
            raise BlobRejectedError(
                "The reassembled ciphertext does not match its declared digest."
            )
        await connection.execute(
            update(blob_manifests)
            .where(blob_manifests.c.id == manifest.id)
            .values(state="complete", size_bytes=total, completed_at=_now())
        )
        await self._refresh_blob_usage(connection, manifest.workspace_id)
        return await self._require(connection, manifest_id)

    async def read(self, connection: AsyncConnection, *, manifest_id: str) -> bytes:
        """Return the reassembled ciphertext of a completed blob."""

        manifest = await self._require(connection, manifest_id)
        if manifest.state != "complete":
            raise BlobRejectedError("The blob upload is not complete.")
        rows = (
            await connection.execute(
                select(blob_chunks.c.storage_key)
                .where(blob_chunks.c.manifest_id == manifest.id)
                .order_by(blob_chunks.c.chunk_index)
            )
        ).fetchall()
        return b"".join(self._store.get(str(row.storage_key)) for row in rows)

    async def mark_deleted(self, connection: AsyncConnection, *, manifest_id: str) -> None:
        """Start the retention window for one blob."""

        await connection.execute(
            update(blob_manifests)
            .where(blob_manifests.c.id == manifest_id)
            .values(deleted_at=_now())
        )

    async def purge_expired(self, connection: AsyncConnection, *, now: datetime) -> int:
        """Remove chunks and manifests whose retention window has elapsed."""

        cutoff = now - timedelta(days=self._settings.content_retention_days)
        rows = (
            await connection.execute(
                select(blob_manifests).where(
                    blob_manifests.c.deleted_at.is_not(None),
                    blob_manifests.c.deleted_at < cutoff,
                )
            )
        ).fetchall()
        for row in rows:
            self._store.delete_prefix(manifest_prefix(str(row.workspace_id), str(row.id)))
            await connection.execute(delete(blob_manifests).where(blob_manifests.c.id == row.id))
        return len(rows)

    # Internals -----------------------------------------------------------

    async def _require_raw_audio_enabled(
        self,
        connection: AsyncConnection,
        workspace_id: str,
    ) -> None:
        row = (
            await connection.execute(
                select(workspaces.c.raw_audio_enabled).where(workspaces.c.id == workspace_id)
            )
        ).fetchone()
        if row is None:
            raise BlobRejectedError("The workspace does not exist.")
        if not bool(row.raw_audio_enabled):
            raise BlobRejectedError("Raw audio sync is disabled for this workspace.")

    async def _load(
        self,
        connection: AsyncConnection,
        *,
        workspace_id: str,
        object_id: str,
    ) -> BlobManifest | None:
        row = (
            await connection.execute(
                select(blob_manifests).where(
                    blob_manifests.c.workspace_id == workspace_id,
                    blob_manifests.c.object_id == object_id,
                    blob_manifests.c.deleted_at.is_(None),
                )
            )
        ).fetchone()
        if row is None:
            return None
        return await self._with_chunks(connection, row)

    async def _require(self, connection: AsyncConnection, manifest_id: str) -> BlobManifest:
        row = (
            await connection.execute(
                select(blob_manifests).where(blob_manifests.c.id == manifest_id)
            )
        ).fetchone()
        if row is None:
            raise BlobRejectedError("The blob manifest does not exist.")
        return await self._with_chunks(connection, row)

    async def _require_pending(self, connection: AsyncConnection, manifest_id: str) -> BlobManifest:
        manifest = await self._require(connection, manifest_id)
        if manifest.state != "pending":
            raise BlobRejectedError(f"The blob upload is already {manifest.state}.")
        return manifest

    async def _with_chunks(self, connection: AsyncConnection, row: Any) -> BlobManifest:
        indexes = (
            await connection.execute(
                select(blob_chunks.c.chunk_index)
                .where(blob_chunks.c.manifest_id == row.id)
                .order_by(blob_chunks.c.chunk_index)
            )
        ).fetchall()
        return BlobManifest(
            id=str(row.id),
            workspace_id=str(row.workspace_id),
            object_id=str(row.object_id),
            chunk_bytes=int(row.chunk_bytes),
            total_chunks=int(row.total_chunks),
            declared_sha256=str(row.declared_sha256),
            state=str(row.state),
            received_chunks=tuple(int(entry.chunk_index) for entry in indexes),
        )

    async def _refresh_blob_usage(self, connection: AsyncConnection, workspace_id: str) -> None:
        total = (
            await connection.execute(
                select(func.coalesce(func.sum(blob_manifests.c.size_bytes), 0)).where(
                    blob_manifests.c.workspace_id == workspace_id,
                    blob_manifests.c.state == "complete",
                    blob_manifests.c.deleted_at.is_(None),
                )
            )
        ).scalar()
        now = _now()
        updated = await connection.execute(
            update(usage_counters)
            .where(usage_counters.c.workspace_id == workspace_id)
            .values(blob_bytes=int(total or 0), updated_at=now)
        )
        if updated.rowcount == 0:
            await connection.execute(
                usage_counters.insert().values(
                    workspace_id=workspace_id,
                    object_count=0,
                    ciphertext_bytes=0,
                    blob_bytes=int(total or 0),
                    updated_at=now,
                )
            )


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value.lower())


def _now() -> datetime:
    return datetime.now(tz=UTC)


__all__ = ["BlobManifest", "BlobRepository"]
