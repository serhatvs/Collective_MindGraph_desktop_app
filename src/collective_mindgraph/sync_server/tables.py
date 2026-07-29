"""Server-side schema holding sealed bytes and routing metadata only.

No column in this schema stores plaintext content. ``ciphertext`` columns hold
sealed bytes the service cannot open, and every other column is routing, audit,
or accounting metadata that the threat model already declares server-visible.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

METADATA = MetaData()

ROLES = ("owner", "admin", "editor", "reviewer", "viewer")
DEVICE_TRUST = ("pending", "trusted", "revoked")
BLOB_STATES = ("pending", "complete", "aborted")

_UUID = String(36)


def _in_clause(column: str, allowed: tuple[str, ...]) -> str:
    values = ", ".join(f"'{value}'" for value in allowed)
    return f"{column} IN ({values})"


tenants = Table(
    "tenants",
    METADATA,
    Column("id", _UUID, primary_key=True),
    Column("name", String(200), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

user_subjects = Table(
    "user_subjects",
    METADATA,
    Column("id", _UUID, primary_key=True),
    Column("tenant_id", _UUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
    Column("issuer", String(500), nullable=False),
    Column("subject", String(500), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("issuer", "subject", name="uq_user_subjects_identity"),
)

workspaces = Table(
    "workspaces",
    METADATA,
    Column("id", _UUID, primary_key=True),
    Column("tenant_id", _UUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
    Column("name", String(200), nullable=False),
    Column("raw_audio_enabled", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
)

workspace_cursors = Table(
    "workspace_cursors",
    METADATA,
    Column(
        "workspace_id",
        _UUID,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("next_sequence", BigInteger, nullable=False, default=1),
)

memberships = Table(
    "memberships",
    METADATA,
    Column("id", _UUID, primary_key=True),
    Column("workspace_id", _UUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", _UUID, ForeignKey("user_subjects.id", ondelete="CASCADE"), nullable=False),
    Column("role", String(20), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("removed_at", DateTime(timezone=True), nullable=True),
    CheckConstraint(_in_clause("role", ROLES), name="ck_memberships_role"),
    UniqueConstraint("workspace_id", "user_id", name="uq_memberships_member"),
)

devices = Table(
    "devices",
    METADATA,
    Column("id", _UUID, primary_key=True),
    Column("workspace_id", _UUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", _UUID, ForeignKey("user_subjects.id", ondelete="CASCADE"), nullable=False),
    Column("name", String(200), nullable=False),
    Column("public_key", LargeBinary, nullable=False),
    Column("trust", String(20), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
    CheckConstraint(_in_clause("trust", DEVICE_TRUST), name="ck_devices_trust"),
    Index("ix_devices_workspace", "workspace_id", "trust"),
)

key_envelopes = Table(
    "key_envelopes",
    METADATA,
    Column("id", _UUID, primary_key=True),
    Column("workspace_id", _UUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
    Column(
        "recipient_device_id",
        _UUID,
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=True,
    ),
    Column("key_version", Integer, nullable=False),
    Column("wrapped_key", LargeBinary, nullable=False),
    Column("ephemeral_public_key", LargeBinary, nullable=True),
    Column("salt", LargeBinary, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
    CheckConstraint("key_version >= 1", name="ck_key_envelopes_version"),
    Index("ix_key_envelopes_recipient", "workspace_id", "recipient_device_id", "key_version"),
)

sync_objects = Table(
    "sync_objects",
    METADATA,
    Column(
        "workspace_id", _UUID, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("object_id", _UUID, primary_key=True),
    Column("object_type", String(60), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("cursor_sequence", BigInteger, nullable=False),
    Column("deleted", Boolean, nullable=False, default=False),
    Column("ciphertext", LargeBinary, nullable=True),
    Column("nonce", LargeBinary, nullable=True),
    Column("key_version", Integer, nullable=False),
    Column("ciphertext_sha256", String(64), nullable=True),
    Column("size_bytes", Integer, nullable=False, default=0),
    Column("updated_by_device", _UUID, nullable=True),
    Column("client_timestamp", DateTime(timezone=True), nullable=False),
    Column("server_timestamp", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
    CheckConstraint("revision >= 1", name="ck_sync_objects_revision"),
    Index("ix_sync_objects_cursor", "workspace_id", "cursor_sequence"),
)

sync_operations = Table(
    "sync_operations",
    METADATA,
    Column("operation_id", _UUID, primary_key=True),
    Column("workspace_id", _UUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
    Column("object_id", _UUID, nullable=False),
    Column("accepted", Boolean, nullable=False),
    Column("applied_revision", Integer, nullable=True),
    Column("conflict_revision", Integer, nullable=True),
    Column("cursor_sequence", BigInteger, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("ix_sync_operations_workspace", "workspace_id", "created_at"),
)

blob_manifests = Table(
    "blob_manifests",
    METADATA,
    Column("id", _UUID, primary_key=True),
    Column("workspace_id", _UUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
    Column("object_id", _UUID, nullable=False),
    Column("chunk_bytes", Integer, nullable=False),
    Column("total_chunks", Integer, nullable=False),
    Column("declared_sha256", String(64), nullable=False),
    Column("state", String(20), nullable=False),
    Column("size_bytes", BigInteger, nullable=False, default=0),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
    CheckConstraint(_in_clause("state", BLOB_STATES), name="ck_blob_manifests_state"),
    UniqueConstraint("workspace_id", "object_id", name="uq_blob_manifests_object"),
)

blob_chunks = Table(
    "blob_chunks",
    METADATA,
    Column(
        "manifest_id",
        _UUID,
        ForeignKey("blob_manifests.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("chunk_index", Integer, primary_key=True),
    Column("sha256", String(64), nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("storage_key", String(500), nullable=False),
    Column("uploaded_at", DateTime(timezone=True), nullable=False),
)

audit_events = Table(
    "audit_events",
    METADATA,
    Column("id", _UUID, primary_key=True),
    Column("workspace_id", _UUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
    Column("actor_user_id", _UUID, nullable=True),
    Column("actor_device_id", _UUID, nullable=True),
    Column("kind", String(60), nullable=False),
    Column("object_type", String(60), nullable=True),
    Column("object_id", _UUID, nullable=True),
    Column("detail", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("ix_audit_events_workspace", "workspace_id", "created_at"),
)

usage_counters = Table(
    "usage_counters",
    METADATA,
    Column(
        "workspace_id", _UUID, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("object_count", BigInteger, nullable=False, default=0),
    Column("ciphertext_bytes", BigInteger, nullable=False, default=0),
    Column("blob_bytes", BigInteger, nullable=False, default=0),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


__all__ = [
    "BLOB_STATES",
    "DEVICE_TRUST",
    "METADATA",
    "ROLES",
    "audit_events",
    "blob_chunks",
    "blob_manifests",
    "devices",
    "key_envelopes",
    "memberships",
    "sync_objects",
    "sync_operations",
    "tenants",
    "usage_counters",
    "user_subjects",
    "workspace_cursors",
    "workspaces",
]
