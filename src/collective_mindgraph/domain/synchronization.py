"""Client-side synchronization state and conflict contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .identifiers import ConflictId, DeviceId, OperationId, SyncId, WorkspaceId


class ConflictResolution(StrEnum):
    """How a user chose to settle one conflicting entity revision."""

    LOCAL = "local"
    REMOTE = "remote"
    MERGED = "merged"


class SyncPhase(StrEnum):
    """What the agent is doing right now."""

    IDLE = "idle"
    PUSHING = "pushing"
    PULLING = "pulling"
    BACKING_OFF = "backing_off"
    OFFLINE = "offline"


@dataclass(frozen=True, slots=True)
class SyncCursor:
    """Where this device has read up to in one workspace."""

    workspace_id: WorkspaceId
    remote_cursor: str = "0"
    last_pushed_revision: int = 0
    last_pull_at: datetime | None = None
    last_push_at: datetime | None = None
    last_error: str | None = None
    backoff_until: datetime | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.workspace_id, "Workspace id")
        if self.last_pushed_revision < 0:
            raise ValueError("The last pushed revision cannot be negative.")
        for label, moment in (
            ("Last pull", self.last_pull_at),
            ("Last push", self.last_push_at),
            ("Backoff deadline", self.backoff_until),
        ):
            if moment is not None and moment.tzinfo is None:
                raise ValueError(f"{label} must be timezone-aware.")

    def is_backing_off(self, *, now: datetime) -> bool:
        """Whether the agent must wait before contacting the service again."""

        return self.backoff_until is not None and now < self.backoff_until


@dataclass(frozen=True, slots=True)
class OutboxEntry:
    """One local change waiting to be pushed."""

    operation_id: OperationId
    workspace_id: WorkspaceId
    object_id: SyncId
    object_type: str
    base_revision: int
    local_revision: int
    client_timestamp: datetime
    payload: bytes = b""
    deleted: bool = False
    attempt_count: int = 0
    last_error: str | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.operation_id, "Operation id")
        _require_uuid(self.workspace_id, "Workspace id")
        _require_uuid(self.object_id, "Object id")
        if not self.object_type.strip():
            raise ValueError("Object type is required.")
        if self.base_revision < 0:
            raise ValueError("Base revision cannot be negative.")
        if self.local_revision < 1:
            raise ValueError("Local revision must be at least one.")
        if self.client_timestamp.tzinfo is None:
            raise ValueError("Client timestamp must be timezone-aware.")
        if self.deleted and self.payload:
            raise ValueError("Deletions carry no payload.")
        if not self.deleted and not self.payload:
            raise ValueError("Content operations require a payload.")


@dataclass(frozen=True, slots=True)
class ConflictRecord:
    """A change the service refused because the entity moved on."""

    id: ConflictId
    workspace_id: WorkspaceId
    object_id: SyncId
    object_type: str
    local_revision: int
    remote_revision: int
    created_at: datetime
    local_payload: bytes = b""
    remote_payload: bytes = b""
    resolved_at: datetime | None = None
    resolution: ConflictResolution | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.id, "Conflict id")
        _require_uuid(self.workspace_id, "Workspace id")
        _require_uuid(self.object_id, "Object id")
        if self.created_at.tzinfo is None:
            raise ValueError("Conflict timestamp must be timezone-aware.")
        if (self.resolution is None) != (self.resolved_at is None):
            raise ValueError("A resolved conflict carries exactly one resolution and time.")

    @property
    def is_open(self) -> bool:
        return self.resolution is None


@dataclass(frozen=True, slots=True)
class SyncStatus:
    """What the desktop shows about one workspace's synchronization."""

    workspace_id: WorkspaceId
    phase: SyncPhase
    pending_operations: int
    open_conflicts: int
    cursor: str = "0"
    last_pull_at: datetime | None = None
    last_push_at: datetime | None = None
    last_error: str | None = None
    device_id: DeviceId | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.workspace_id, "Workspace id")
        if self.pending_operations < 0 or self.open_conflicts < 0:
            raise ValueError("Counters cannot be negative.")

    @property
    def is_settled(self) -> bool:
        """Whether nothing is queued and nothing needs a decision."""

        return self.pending_operations == 0 and self.open_conflicts == 0


def _require_uuid(value: object, label: str) -> None:
    try:
        UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"{label} must be a UUID.") from error


__all__ = [
    "ConflictRecord",
    "ConflictResolution",
    "OutboxEntry",
    "SyncCursor",
    "SyncPhase",
    "SyncStatus",
]
