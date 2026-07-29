"""The engine's view of the remote synchronization service."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class RemoteOutcome(StrEnum):
    """What the service did with one pushed operation."""

    APPLIED = "applied"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class RemoteOperationResult:
    operation_id: str
    object_id: str
    outcome: RemoteOutcome
    revision: int | None = None
    server_revision: int | None = None


@dataclass(frozen=True, slots=True)
class RemotePushResult:
    cursor: str
    results: tuple[RemoteOperationResult, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class RemoteRecord:
    """One sealed revision the service returned."""

    object_id: str
    object_type: str
    revision: int
    key_version: int
    deleted: bool
    server_timestamp: datetime
    ciphertext: bytes | None = None
    nonce: bytes | None = None


@dataclass(frozen=True, slots=True)
class RemotePullPage:
    cursor: str
    has_more: bool = False
    records: tuple[RemoteRecord, ...] = field(default_factory=tuple)


class SyncTransportError(RuntimeError):
    """Raised when the service could not be reached or refused the call."""


class RetryableTransportError(SyncTransportError):
    """A failure the agent should back off from rather than surface."""


class SyncTransport(Protocol):
    """Push and pull against `/sync/v1` for one workspace."""

    def push(
        self,
        *,
        workspace_id: str,
        device_id: str,
        operations: Sequence[object],
    ) -> RemotePushResult: ...

    def pull(
        self,
        *,
        workspace_id: str,
        cursor: str,
        limit: int | None = None,
    ) -> RemotePullPage: ...


class OutboxRepository(Protocol):
    """Durable local queue, cursor, and conflict inbox."""

    def enqueue(self, entry: object) -> None: ...

    def pending(self, workspace_id: str, *, limit: int) -> tuple[object, ...]: ...

    def mark_pushed(self, operation_ids: tuple[str, ...]) -> int: ...

    def pending_count(self, workspace_id: str) -> int: ...

    def cursor(self, workspace_id: str) -> object: ...

    def save_cursor(self, cursor: object) -> None: ...

    def record_conflict(self, **fields: object) -> object: ...

    def get_conflict(self, conflict_id: str) -> object: ...

    def resolve_conflict(self, conflict_id: str, resolution: object) -> None: ...

    def open_conflict_count(self, workspace_id: str) -> int: ...


__all__ = [
    "OutboxRepository",
    "RemoteOperationResult",
    "RemoteOutcome",
    "RemotePullPage",
    "RemotePushResult",
    "RemoteRecord",
    "RetryableTransportError",
    "SyncTransport",
    "SyncTransportError",
]
