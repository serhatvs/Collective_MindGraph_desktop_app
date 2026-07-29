"""The engine-owned sync agent: push, pull, conflict, and backoff.

The desktop never talks to the service. It asks the engine for status and for
a run; the engine owns the outbox, the cursor, and the conflict inbox.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from collective_mindgraph.application.ports.sync_transport import (
    RemoteOutcome,
    RemotePullPage,
    RetryableTransportError,
    SyncTransport,
    SyncTransportError,
)
from collective_mindgraph.domain import (
    ConflictRecord,
    ConflictResolution,
    OutboxEntry,
    SyncCursor,
    SyncPhase,
    SyncStatus,
)
from collective_mindgraph.domain.identifiers import (
    ConflictId,
    DeviceId,
    OperationId,
    WorkspaceId,
)

FOREGROUND_INTERVAL_SECONDS = 5.0
BACKGROUND_INTERVAL_SECONDS = 30.0
INITIAL_BACKOFF_SECONDS = 5.0
MAX_BACKOFF_SECONDS = 300.0
PUSH_BATCH_LIMIT = 500


class ConflictNotFoundError(LookupError):
    """Raised when a resolution names a conflict that is not open."""


@dataclass(frozen=True, slots=True)
class SyncRunReport:
    """What one synchronization pass did."""

    workspace_id: WorkspaceId
    pushed: int = 0
    duplicates: int = 0
    conflicts: tuple[ConflictRecord, ...] = field(default_factory=tuple)
    pulled: int = 0
    cursor: str = "0"
    has_more: bool = False
    skipped_reason: str | None = None
    error: str | None = None

    @property
    def made_progress(self) -> bool:
        return bool(self.pushed or self.pulled or self.conflicts)


class SyncAgent:
    """Runs one workspace's synchronization without ever blocking on a peer."""

    def __init__(
        self,
        *,
        outbox: Any,
        transport: SyncTransport,
        apply_remote: Callable[[RemotePullPage], int],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._outbox = outbox
        self._transport = transport
        self._apply_remote = apply_remote
        self._clock = clock or (lambda: datetime.now(tz=UTC))

    # Status ---------------------------------------------------------------

    def status(
        self,
        workspace_id: WorkspaceId,
        *,
        device_id: DeviceId | None = None,
    ) -> SyncStatus:
        """Describe this workspace without contacting the service."""

        cursor = self._outbox.cursor(workspace_id)
        now = self._clock()
        pending = self._outbox.pending_count(workspace_id)
        open_conflicts = self._outbox.open_conflict_count(workspace_id)
        return SyncStatus(
            workspace_id=workspace_id,
            phase=self._phase(cursor, now=now, pending=pending),
            pending_operations=pending,
            open_conflicts=open_conflicts,
            cursor=cursor.remote_cursor,
            last_pull_at=cursor.last_pull_at,
            last_push_at=cursor.last_push_at,
            last_error=cursor.last_error,
            device_id=device_id,
        )

    def next_interval_seconds(self, workspace_id: WorkspaceId, *, foreground: bool) -> float:
        """How long to wait before the next pass.

        Active use polls every five seconds on top of invalidation hints;
        background work waits thirty. A backing-off workspace waits out its
        deadline instead.
        """

        cursor = self._outbox.cursor(workspace_id)
        now = self._clock()
        if cursor.backoff_until is not None and now < cursor.backoff_until:
            remaining: float = (cursor.backoff_until - now).total_seconds()
            return max(1.0, remaining)
        return FOREGROUND_INTERVAL_SECONDS if foreground else BACKGROUND_INTERVAL_SECONDS

    # One pass -------------------------------------------------------------

    def run_once(self, workspace_id: WorkspaceId, *, device_id: DeviceId) -> SyncRunReport:
        """Push everything queued, then pull one page of remote changes."""

        cursor = self._outbox.cursor(workspace_id)
        now = self._clock()
        if cursor.is_backing_off(now=now):
            return SyncRunReport(
                workspace_id=workspace_id,
                cursor=cursor.remote_cursor,
                skipped_reason="backing off after a previous failure",
            )
        try:
            pushed, duplicates, conflicts = self._push(workspace_id, device_id=device_id)
            page = self._pull(workspace_id, cursor.remote_cursor)
        except RetryableTransportError as error:
            self._record_failure(cursor, error)
            return SyncRunReport(
                workspace_id=workspace_id,
                cursor=cursor.remote_cursor,
                error=str(error),
            )
        except SyncTransportError as error:
            # A refusal is not transient; surface it without backing off so the
            # user sees the real reason instead of a silent stall.
            self._outbox.save_cursor(
                SyncCursor(
                    workspace_id=workspace_id,
                    remote_cursor=cursor.remote_cursor,
                    last_pushed_revision=cursor.last_pushed_revision,
                    last_pull_at=cursor.last_pull_at,
                    last_push_at=cursor.last_push_at,
                    last_error=str(error),
                )
            )
            return SyncRunReport(
                workspace_id=workspace_id,
                cursor=cursor.remote_cursor,
                error=str(error),
            )

        applied = int(self._apply_remote(page))
        self._outbox.save_cursor(
            SyncCursor(
                workspace_id=workspace_id,
                remote_cursor=page.cursor,
                last_pushed_revision=cursor.last_pushed_revision,
                last_pull_at=self._clock(),
                last_push_at=self._clock() if pushed else cursor.last_push_at,
                last_error=None,
            )
        )
        return SyncRunReport(
            workspace_id=workspace_id,
            pushed=pushed,
            duplicates=duplicates,
            conflicts=conflicts,
            pulled=applied,
            cursor=page.cursor,
            has_more=page.has_more,
        )

    # Conflicts ------------------------------------------------------------

    def resolve(
        self,
        conflict_id: ConflictId,
        resolution: ConflictResolution,
        *,
        merged_payload: bytes | None = None,
    ) -> OutboxEntry | None:
        """Settle a conflict, re-queueing the chosen version as a new revision.

        Choosing the remote version simply closes the conflict; the pulled
        revision is already applied. Choosing local or merged re-pushes on top
        of the revision the service reported.
        """

        conflict = self._outbox.get_conflict(conflict_id)
        if conflict is None or not conflict.is_open:
            raise ConflictNotFoundError("No open conflict with that identifier.")
        if resolution is ConflictResolution.MERGED and not merged_payload:
            raise ValueError("A merged resolution requires the merged payload.")
        self._outbox.resolve_conflict(conflict_id, resolution)
        if resolution is ConflictResolution.REMOTE:
            return None
        payload = (
            merged_payload
            if resolution is ConflictResolution.MERGED and merged_payload
            else conflict.local_payload
        )
        entry = OutboxEntry(
            operation_id=self._operation_id(),
            workspace_id=conflict.workspace_id,
            object_id=conflict.object_id,
            object_type=conflict.object_type,
            base_revision=conflict.remote_revision,
            local_revision=conflict.remote_revision + 1,
            client_timestamp=self._clock(),
            payload=payload,
        )
        self._outbox.enqueue(entry)
        return entry

    # Internals ------------------------------------------------------------

    def _push(
        self,
        workspace_id: WorkspaceId,
        *,
        device_id: DeviceId,
    ) -> tuple[int, int, tuple[ConflictRecord, ...]]:
        entries = self._outbox.pending(workspace_id, limit=PUSH_BATCH_LIMIT)
        if not entries:
            return 0, 0, ()
        result = self._transport.push(
            workspace_id=str(workspace_id),
            device_id=str(device_id),
            operations=entries,
        )
        by_operation = {entry.operation_id: entry for entry in entries}
        settled: list[str] = []
        conflicts: list[ConflictRecord] = []
        pushed = duplicates = 0
        for outcome in result.results:
            entry = by_operation.get(outcome.operation_id)
            if entry is None:
                continue
            if outcome.outcome is RemoteOutcome.APPLIED:
                pushed += 1
                settled.append(outcome.operation_id)
            elif outcome.outcome is RemoteOutcome.DUPLICATE:
                duplicates += 1
                settled.append(outcome.operation_id)
            else:
                conflicts.append(
                    self._outbox.record_conflict(
                        workspace_id=workspace_id,
                        object_id=entry.object_id,
                        object_type=entry.object_type,
                        local_revision=entry.local_revision,
                        remote_revision=outcome.server_revision or 0,
                        local_payload=entry.payload,
                    )
                )
                settled.append(outcome.operation_id)
        self._outbox.mark_pushed(tuple(settled))
        return pushed, duplicates, tuple(conflicts)

    def _pull(self, workspace_id: WorkspaceId, cursor: str) -> RemotePullPage:
        return self._transport.pull(workspace_id=str(workspace_id), cursor=cursor)

    @staticmethod
    def _operation_id() -> OperationId:
        return OperationId(str(uuid4()))

    def _record_failure(self, cursor: SyncCursor, error: Exception) -> None:
        attempt_backoff = INITIAL_BACKOFF_SECONDS
        if cursor.backoff_until is not None and cursor.last_error:
            attempt_backoff = min(MAX_BACKOFF_SECONDS, INITIAL_BACKOFF_SECONDS * 2)
        self._outbox.save_cursor(
            SyncCursor(
                workspace_id=cursor.workspace_id,
                remote_cursor=cursor.remote_cursor,
                last_pushed_revision=cursor.last_pushed_revision,
                last_pull_at=cursor.last_pull_at,
                last_push_at=cursor.last_push_at,
                last_error=str(error),
                backoff_until=self._clock() + timedelta(seconds=attempt_backoff),
            )
        )

    def _phase(self, cursor: SyncCursor, *, now: datetime, pending: int) -> SyncPhase:
        if cursor.is_backing_off(now=now):
            return SyncPhase.BACKING_OFF
        if cursor.last_error:
            return SyncPhase.OFFLINE
        if pending:
            return SyncPhase.PUSHING
        return SyncPhase.IDLE


__all__ = [
    "BACKGROUND_INTERVAL_SECONDS",
    "FOREGROUND_INTERVAL_SECONDS",
    "INITIAL_BACKOFF_SECONDS",
    "MAX_BACKOFF_SECONDS",
    "PUSH_BATCH_LIMIT",
    "ConflictNotFoundError",
    "SyncAgent",
    "SyncRunReport",
]
