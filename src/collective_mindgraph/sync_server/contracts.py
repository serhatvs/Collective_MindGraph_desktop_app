"""Wire and repository contracts for the synchronization service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Role(StrEnum):
    """Fixed workspace roles enforced by the service."""

    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    REVIEWER = "reviewer"
    VIEWER = "viewer"

    @property
    def may_write_content(self) -> bool:
        return self in {Role.OWNER, Role.ADMIN, Role.EDITOR}

    @property
    def may_review(self) -> bool:
        return self in {Role.OWNER, Role.ADMIN, Role.EDITOR, Role.REVIEWER}

    @property
    def may_administer(self) -> bool:
        return self in {Role.OWNER, Role.ADMIN}


class OperationOutcome(StrEnum):
    """Result the service assigns to one pushed operation."""

    APPLIED = "applied"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated caller resolved from the identity layer."""

    user_id: str
    tenant_id: str
    issuer: str
    subject: str


@dataclass(frozen=True, slots=True)
class SyncOperationInput:
    """One opaque change a client asks the service to record."""

    operation_id: str
    object_id: str
    object_type: str
    base_revision: int
    key_version: int
    client_timestamp: datetime
    ciphertext: bytes | None = None
    nonce: bytes | None = None
    deleted: bool = False

    def __post_init__(self) -> None:
        if self.base_revision < 0:
            raise ValueError("Base revision cannot be negative.")
        if self.key_version < 1:
            raise ValueError("Key version must be at least one.")
        if not self.object_type.strip():
            raise ValueError("Object type is required.")
        if self.client_timestamp.tzinfo is None:
            raise ValueError("Client timestamp must be timezone-aware.")
        if self.deleted:
            if self.ciphertext is not None:
                raise ValueError("Deletions must not carry ciphertext.")
        elif not self.ciphertext or not self.nonce:
            raise ValueError("Content operations require ciphertext and a nonce.")

    @property
    def payload_bytes(self) -> int:
        return len(self.ciphertext or b"")


@dataclass(frozen=True, slots=True)
class OperationResult:
    """Per-operation outcome returned to the pushing client."""

    operation_id: str
    object_id: str
    outcome: OperationOutcome
    revision: int | None = None
    server_revision: int | None = None


@dataclass(frozen=True, slots=True)
class PushResult:
    """Aggregate result of one push batch."""

    results: tuple[OperationResult, ...]
    cursor: str

    @property
    def conflicts(self) -> tuple[OperationResult, ...]:
        return tuple(
            result for result in self.results if result.outcome is OperationOutcome.CONFLICT
        )


@dataclass(frozen=True, slots=True)
class SyncObjectRecord:
    """One sealed object revision handed back to a pulling client."""

    object_id: str
    object_type: str
    revision: int
    key_version: int
    deleted: bool
    client_timestamp: datetime
    server_timestamp: datetime
    ciphertext: bytes | None = None
    nonce: bytes | None = None
    ciphertext_sha256: str | None = None
    updated_by_device: str | None = None


@dataclass(frozen=True, slots=True)
class PullPage:
    """One cursor-ordered page of changes."""

    records: tuple[SyncObjectRecord, ...] = field(default_factory=tuple)
    cursor: str = "0"
    has_more: bool = False


class SyncServiceError(RuntimeError):
    """Base error for service-level failures."""


class WorkspaceNotFoundError(SyncServiceError):
    """Raised when a workspace does not exist or has been deleted."""


class AccessDeniedError(SyncServiceError):
    """Raised when a principal lacks the required workspace role."""


class PushLimitExceededError(SyncServiceError):
    """Raised when a batch exceeds the configured operation or byte limit."""


class BlobRejectedError(SyncServiceError):
    """Raised when a blob upload violates its manifest or workspace policy."""


__all__ = [
    "AccessDeniedError",
    "BlobRejectedError",
    "OperationOutcome",
    "OperationResult",
    "Principal",
    "PullPage",
    "PushLimitExceededError",
    "PushResult",
    "Role",
    "SyncObjectRecord",
    "SyncOperationInput",
    "SyncServiceError",
    "WorkspaceNotFoundError",
]
