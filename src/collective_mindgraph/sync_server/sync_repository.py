"""Optimistic, idempotent push and cursor-ordered pull over sealed objects."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from .contracts import (
    OperationOutcome,
    OperationResult,
    PullPage,
    PushLimitExceededError,
    PushResult,
    SyncObjectRecord,
    SyncOperationInput,
    WorkspaceNotFoundError,
)
from .settings import SyncServerSettings
from .tables import sync_objects, sync_operations, usage_counters, workspace_cursors


class SyncRepository:
    """Applies opaque operations without ever inspecting their plaintext."""

    def __init__(self, settings: SyncServerSettings) -> None:
        self._settings = settings

    async def push(
        self,
        connection: AsyncConnection,
        *,
        workspace_id: str,
        device_id: str,
        operations: Sequence[SyncOperationInput],
    ) -> PushResult:
        """Apply a batch atomically and report a per-operation outcome."""

        self._validate_batch(operations)
        results: list[OperationResult] = []
        for operation in operations:
            results.append(
                await self._apply(
                    connection,
                    workspace_id=workspace_id,
                    device_id=device_id,
                    operation=operation,
                )
            )
        cursor = await self._current_cursor(connection, workspace_id)
        return PushResult(results=tuple(results), cursor=cursor)

    async def pull(
        self,
        connection: AsyncConnection,
        *,
        workspace_id: str,
        cursor: str,
        limit: int | None = None,
    ) -> PullPage:
        """Return changes strictly after ``cursor`` in server order."""

        since = _decode_cursor(cursor)
        page_size = min(limit or self._settings.pull_limit, self._settings.pull_limit)
        rows = (
            await connection.execute(
                select(sync_objects)
                .where(
                    sync_objects.c.workspace_id == workspace_id,
                    sync_objects.c.cursor_sequence > since,
                )
                .order_by(sync_objects.c.cursor_sequence)
                .limit(page_size + 1)
            )
        ).fetchall()
        has_more = len(rows) > page_size
        visible = rows[:page_size]
        records = tuple(_map_record(row) for row in visible)
        next_cursor = str(visible[-1].cursor_sequence) if visible else str(since)
        return PullPage(records=records, cursor=next_cursor, has_more=has_more)

    # Internals -----------------------------------------------------------

    def _validate_batch(self, operations: Sequence[SyncOperationInput]) -> None:
        if not operations:
            raise PushLimitExceededError("A push batch must contain at least one operation.")
        if len(operations) > self._settings.push_operation_limit:
            raise PushLimitExceededError(
                f"A push batch may carry at most {self._settings.push_operation_limit} operations."
            )
        total = sum(operation.payload_bytes for operation in operations)
        if total > self._settings.push_byte_limit:
            raise PushLimitExceededError(
                f"A push batch may carry at most {self._settings.push_byte_limit} ciphertext bytes."
            )
        seen = {operation.operation_id for operation in operations}
        if len(seen) != len(operations):
            raise PushLimitExceededError("Operation identifiers must be unique within a batch.")

    async def _apply(
        self,
        connection: AsyncConnection,
        *,
        workspace_id: str,
        device_id: str,
        operation: SyncOperationInput,
    ) -> OperationResult:
        recorded = (
            await connection.execute(
                select(sync_operations).where(
                    sync_operations.c.operation_id == operation.operation_id
                )
            )
        ).fetchone()
        if recorded is not None:
            return _replay(operation, recorded)

        current = (
            await connection.execute(
                select(sync_objects).where(
                    sync_objects.c.workspace_id == workspace_id,
                    sync_objects.c.object_id == operation.object_id,
                )
            )
        ).fetchone()
        server_revision = int(current.revision) if current is not None else 0
        if server_revision != operation.base_revision:
            return await self._record_conflict(
                connection,
                workspace_id=workspace_id,
                operation=operation,
                server_revision=server_revision,
            )
        return await self._record_applied(
            connection,
            workspace_id=workspace_id,
            device_id=device_id,
            operation=operation,
            existing=current is not None,
        )

    async def _record_conflict(
        self,
        connection: AsyncConnection,
        *,
        workspace_id: str,
        operation: SyncOperationInput,
        server_revision: int,
    ) -> OperationResult:
        await connection.execute(
            sync_operations.insert().values(
                operation_id=operation.operation_id,
                workspace_id=workspace_id,
                object_id=operation.object_id,
                accepted=False,
                applied_revision=None,
                conflict_revision=server_revision,
                cursor_sequence=None,
                created_at=datetime.now(tz=UTC),
            )
        )
        return OperationResult(
            operation_id=operation.operation_id,
            object_id=operation.object_id,
            outcome=OperationOutcome.CONFLICT,
            server_revision=server_revision,
        )

    async def _record_applied(
        self,
        connection: AsyncConnection,
        *,
        workspace_id: str,
        device_id: str,
        operation: SyncOperationInput,
        existing: bool,
    ) -> OperationResult:
        sequence = await self._next_sequence(connection, workspace_id)
        now = datetime.now(tz=UTC)
        revision = operation.base_revision + 1
        ciphertext = None if operation.deleted else operation.ciphertext
        values = {
            "object_type": operation.object_type,
            "revision": revision,
            "cursor_sequence": sequence,
            "deleted": operation.deleted,
            "ciphertext": ciphertext,
            "nonce": None if operation.deleted else operation.nonce,
            "key_version": operation.key_version,
            "ciphertext_sha256": _digest(ciphertext),
            "size_bytes": len(ciphertext or b""),
            "updated_by_device": device_id,
            "client_timestamp": operation.client_timestamp,
            "server_timestamp": now,
            "deleted_at": now if operation.deleted else None,
        }
        if existing:
            await connection.execute(
                update(sync_objects)
                .where(
                    sync_objects.c.workspace_id == workspace_id,
                    sync_objects.c.object_id == operation.object_id,
                )
                .values(**values)
            )
        else:
            await connection.execute(
                sync_objects.insert().values(
                    workspace_id=workspace_id,
                    object_id=operation.object_id,
                    **values,
                )
            )
        await connection.execute(
            sync_operations.insert().values(
                operation_id=operation.operation_id,
                workspace_id=workspace_id,
                object_id=operation.object_id,
                accepted=True,
                applied_revision=revision,
                conflict_revision=None,
                cursor_sequence=sequence,
                created_at=now,
            )
        )
        await self._refresh_usage(connection, workspace_id)
        return OperationResult(
            operation_id=operation.operation_id,
            object_id=operation.object_id,
            outcome=OperationOutcome.APPLIED,
            revision=revision,
        )

    async def _next_sequence(self, connection: AsyncConnection, workspace_id: str) -> int:
        """Claim the next cursor value under a row lock.

        The counter row is created with the workspace, so concurrent pushes
        serialize on an existing row instead of racing to insert one.
        """

        row = (
            await connection.execute(
                select(workspace_cursors.c.next_sequence)
                .where(workspace_cursors.c.workspace_id == workspace_id)
                .with_for_update()
            )
        ).fetchone()
        if row is None:
            raise WorkspaceNotFoundError("The workspace has no cursor sequence.")
        sequence = int(row.next_sequence)
        await connection.execute(
            update(workspace_cursors)
            .where(workspace_cursors.c.workspace_id == workspace_id)
            .values(next_sequence=sequence + 1)
        )
        return sequence

    async def _current_cursor(self, connection: AsyncConnection, workspace_id: str) -> str:
        row = (
            await connection.execute(
                select(workspace_cursors.c.next_sequence).where(
                    workspace_cursors.c.workspace_id == workspace_id
                )
            )
        ).fetchone()
        return str(int(row.next_sequence) - 1) if row is not None else "0"

    async def _refresh_usage(self, connection: AsyncConnection, workspace_id: str) -> None:
        totals = (
            await connection.execute(
                select(
                    func.count(sync_objects.c.object_id),
                    func.coalesce(func.sum(sync_objects.c.size_bytes), 0),
                ).where(
                    sync_objects.c.workspace_id == workspace_id,
                    sync_objects.c.deleted.is_(False),
                )
            )
        ).fetchone()
        object_count = int(totals[0] or 0) if totals is not None else 0
        ciphertext_bytes = int(totals[1] or 0) if totals is not None else 0
        now = datetime.now(tz=UTC)
        updated = await connection.execute(
            update(usage_counters)
            .where(usage_counters.c.workspace_id == workspace_id)
            .values(object_count=object_count, ciphertext_bytes=ciphertext_bytes, updated_at=now)
        )
        if updated.rowcount == 0:
            await connection.execute(
                usage_counters.insert().values(
                    workspace_id=workspace_id,
                    object_count=object_count,
                    ciphertext_bytes=ciphertext_bytes,
                    blob_bytes=0,
                    updated_at=now,
                )
            )

    async def purge_expired(
        self,
        connection: AsyncConnection,
        *,
        now: datetime,
    ) -> int:
        """Remove deleted objects whose retention window has elapsed."""

        cutoff = now - timedelta(days=self._settings.content_retention_days)
        removed = await connection.execute(
            delete(sync_objects).where(
                sync_objects.c.deleted.is_(True),
                sync_objects.c.deleted_at.is_not(None),
                sync_objects.c.deleted_at < cutoff,
            )
        )
        return int(removed.rowcount)


def _replay(operation: SyncOperationInput, recorded: Any) -> OperationResult:
    if bool(recorded.accepted):
        return OperationResult(
            operation_id=operation.operation_id,
            object_id=operation.object_id,
            outcome=OperationOutcome.DUPLICATE,
            revision=int(recorded.applied_revision),
        )
    return OperationResult(
        operation_id=operation.operation_id,
        object_id=operation.object_id,
        outcome=OperationOutcome.CONFLICT,
        server_revision=int(recorded.conflict_revision),
    )


def _map_record(row: Any) -> SyncObjectRecord:
    return SyncObjectRecord(
        object_id=str(row.object_id),
        object_type=str(row.object_type),
        revision=int(row.revision),
        key_version=int(row.key_version),
        deleted=bool(row.deleted),
        client_timestamp=_aware(row.client_timestamp),
        server_timestamp=_aware(row.server_timestamp),
        ciphertext=bytes(row.ciphertext) if row.ciphertext is not None else None,
        nonce=bytes(row.nonce) if row.nonce is not None else None,
        ciphertext_sha256=(
            str(row.ciphertext_sha256) if row.ciphertext_sha256 is not None else None
        ),
        updated_by_device=(
            str(row.updated_by_device) if row.updated_by_device is not None else None
        ),
    )


def _decode_cursor(cursor: str) -> int:
    try:
        value = int(cursor)
    except (TypeError, ValueError) as error:
        raise ValueError("The pull cursor is not a valid server cursor.") from error
    if value < 0:
        raise ValueError("The pull cursor cannot be negative.")
    return value


def _digest(ciphertext: bytes | None) -> str | None:
    return hashlib.sha256(ciphertext).hexdigest() if ciphertext else None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


__all__ = ["SyncRepository"]
