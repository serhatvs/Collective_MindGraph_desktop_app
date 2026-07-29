"""Workspace and synchronization identity contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .identifiers import DeviceId, OperationId, SyncId, WorkspaceId


class WorkspaceKind(StrEnum):
    LOCAL = "local"
    CLOUD = "cloud"


class SyncOperationState(StrEnum):
    PENDING = "pending"
    PUSHING = "pushing"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Workspace:
    id: WorkspaceId
    sync_id: SyncId
    name: str
    kind: WorkspaceKind
    created_at: datetime
    updated_at: datetime
    local_revision: int = 1
    sync_revision: int = 0
    updated_by_device: DeviceId | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.id, "Workspace id")
        _require_uuid(self.sync_id, "Workspace sync id")
        if not self.name.strip():
            raise ValueError("Workspace name is required.")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("Workspace timestamps must be timezone-aware.")
        _require_revisions(self.local_revision, self.sync_revision)
        if self.updated_by_device is not None:
            _require_uuid(self.updated_by_device, "Updated-by device id")


@dataclass(frozen=True, slots=True)
class SyncIdentity:
    """Stable cloud identity attached to one local entity row."""

    workspace_id: WorkspaceId
    sync_id: SyncId
    local_revision: int
    sync_revision: int
    updated_by_device: DeviceId | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.workspace_id, "Workspace id")
        _require_uuid(self.sync_id, "Sync id")
        _require_revisions(self.local_revision, self.sync_revision)
        if self.updated_by_device is not None:
            _require_uuid(self.updated_by_device, "Updated-by device id")


@dataclass(frozen=True, slots=True)
class SyncOperation:
    operation_id: OperationId
    workspace_id: WorkspaceId
    object_id: SyncId
    object_type: str
    base_revision: int
    local_revision: int
    client_timestamp: datetime
    deleted: bool = False
    state: SyncOperationState = SyncOperationState.PENDING
    payload: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_uuid(self.operation_id, "Operation id")
        _require_uuid(self.workspace_id, "Workspace id")
        _require_uuid(self.object_id, "Object id")
        if not self.object_type.strip():
            raise ValueError("Sync object type is required.")
        _require_revisions(self.local_revision, self.base_revision)
        if self.client_timestamp.tzinfo is None:
            raise ValueError("Sync operation timestamp must be timezone-aware.")


def _require_uuid(value: object, label: str) -> None:
    try:
        UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"{label} must be a UUID.") from error


def _require_revisions(local_revision: int, sync_revision: int) -> None:
    if local_revision < 1:
        raise ValueError("Local revision must be at least one.")
    if sync_revision < 0:
        raise ValueError("Sync revision cannot be negative.")
