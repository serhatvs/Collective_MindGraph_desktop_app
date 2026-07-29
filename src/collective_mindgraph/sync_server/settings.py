"""Deployment configuration for the synchronization service."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

MEBIBYTE = 1024 * 1024
DEFAULT_PUSH_OPERATION_LIMIT = 500
DEFAULT_PUSH_BYTE_LIMIT = 4 * MEBIBYTE
DEFAULT_BLOB_CHUNK_BYTES = 8 * MEBIBYTE
DEFAULT_PULL_LIMIT = 500
MAX_PULL_LIMIT = 2000

# Retention windows fixed by the production programme.
DEFAULT_CONTENT_RETENTION_DAYS = 30
DEFAULT_AUDIT_RETENTION_DAYS = 90
DEFAULT_BACKUP_RETENTION_DAYS = 35


class SyncServerConfigurationError(ValueError):
    """Raised when the deployment configuration is unusable."""


@dataclass(slots=True)
class SyncServerSettings:
    """Configuration resolved from the deployment environment."""

    database_url: str
    blob_root: Path
    push_operation_limit: int = DEFAULT_PUSH_OPERATION_LIMIT
    push_byte_limit: int = DEFAULT_PUSH_BYTE_LIMIT
    blob_chunk_bytes: int = DEFAULT_BLOB_CHUNK_BYTES
    pull_limit: int = DEFAULT_PULL_LIMIT
    content_retention_days: int = DEFAULT_CONTENT_RETENTION_DAYS
    audit_retention_days: int = DEFAULT_AUDIT_RETENTION_DAYS
    backup_retention_days: int = DEFAULT_BACKUP_RETENTION_DAYS
    log_level: str = "info"
    trusted_hosts: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.database_url.strip():
            raise SyncServerConfigurationError("A database URL is required.")
        if not self.database_url.startswith(("postgresql+asyncpg://", "sqlite+aiosqlite://")):
            raise SyncServerConfigurationError(
                "The database URL must use the postgresql+asyncpg or sqlite+aiosqlite driver."
            )
        self.blob_root = Path(self.blob_root).expanduser()
        _require_positive(self.push_operation_limit, "push operation limit")
        _require_positive(self.push_byte_limit, "push byte limit")
        _require_positive(self.blob_chunk_bytes, "blob chunk size")
        _require_positive(self.pull_limit, "pull limit")
        if self.pull_limit > MAX_PULL_LIMIT:
            raise SyncServerConfigurationError(
                f"The pull limit cannot exceed {MAX_PULL_LIMIT} objects."
            )
        for name, value in (
            ("content", self.content_retention_days),
            ("audit", self.audit_retention_days),
            ("backup", self.backup_retention_days),
        ):
            _require_positive(value, f"{name} retention window")

    @property
    def is_postgres(self) -> bool:
        """Whether this deployment targets PostgreSQL."""

        return self.database_url.startswith("postgresql+asyncpg://")


def get_sync_server_settings(
    environment: dict[str, str] | None = None,
) -> SyncServerSettings:
    """Resolve settings from environment variables."""

    source = environment if environment is not None else dict(os.environ)
    database_url = source.get("CMG_SYNC_DATABASE_URL", "").strip()
    if not database_url:
        raise SyncServerConfigurationError(
            "CMG_SYNC_DATABASE_URL must be set before the sync service starts."
        )
    blob_root = source.get("CMG_SYNC_BLOB_ROOT", "").strip()
    if not blob_root:
        raise SyncServerConfigurationError(
            "CMG_SYNC_BLOB_ROOT must point at the encrypted blob storage root."
        )
    hosts = tuple(
        host.strip() for host in source.get("CMG_SYNC_TRUSTED_HOSTS", "").split(",") if host.strip()
    )
    return SyncServerSettings(
        database_url=database_url,
        blob_root=Path(blob_root),
        push_operation_limit=_read_int(
            source, "CMG_SYNC_PUSH_OPERATION_LIMIT", DEFAULT_PUSH_OPERATION_LIMIT
        ),
        push_byte_limit=_read_int(source, "CMG_SYNC_PUSH_BYTE_LIMIT", DEFAULT_PUSH_BYTE_LIMIT),
        blob_chunk_bytes=_read_int(source, "CMG_SYNC_BLOB_CHUNK_BYTES", DEFAULT_BLOB_CHUNK_BYTES),
        pull_limit=_read_int(source, "CMG_SYNC_PULL_LIMIT", DEFAULT_PULL_LIMIT),
        content_retention_days=_read_int(
            source, "CMG_SYNC_CONTENT_RETENTION_DAYS", DEFAULT_CONTENT_RETENTION_DAYS
        ),
        audit_retention_days=_read_int(
            source, "CMG_SYNC_AUDIT_RETENTION_DAYS", DEFAULT_AUDIT_RETENTION_DAYS
        ),
        backup_retention_days=_read_int(
            source, "CMG_SYNC_BACKUP_RETENTION_DAYS", DEFAULT_BACKUP_RETENTION_DAYS
        ),
        log_level=source.get("CMG_SYNC_LOG_LEVEL", "info"),
        trusted_hosts=hosts,
    )


def _read_int(source: dict[str, str], name: str, fallback: int) -> int:
    raw = source.get(name, "").strip()
    if not raw:
        return fallback
    try:
        return int(raw)
    except ValueError as error:
        raise SyncServerConfigurationError(f"{name} must be an integer.") from error


def _require_positive(value: int, label: str) -> None:
    if value < 1:
        raise SyncServerConfigurationError(f"The {label} must be at least one.")


__all__ = [
    "DEFAULT_BLOB_CHUNK_BYTES",
    "DEFAULT_PUSH_BYTE_LIMIT",
    "DEFAULT_PUSH_OPERATION_LIMIT",
    "MAX_PULL_LIMIT",
    "SyncServerConfigurationError",
    "SyncServerSettings",
    "get_sync_server_settings",
]
