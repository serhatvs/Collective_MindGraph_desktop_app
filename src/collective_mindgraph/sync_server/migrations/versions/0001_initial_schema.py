"""Create the initial synchronization service schema.

Revision ID: 0001
Revises:
"""

from __future__ import annotations

from alembic import op

from collective_mindgraph.sync_server.tables import METADATA

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_ORDER = (
    "tenants",
    "user_subjects",
    "workspaces",
    "workspace_cursors",
    "memberships",
    "devices",
    "key_envelopes",
    "sync_objects",
    "sync_operations",
    "blob_manifests",
    "blob_chunks",
    "audit_events",
    "usage_counters",
)


def upgrade() -> None:
    bind = op.get_bind()
    METADATA.create_all(bind=bind, tables=[METADATA.tables[name] for name in _ORDER])


def downgrade() -> None:
    bind = op.get_bind()
    METADATA.drop_all(bind=bind, tables=[METADATA.tables[name] for name in reversed(_ORDER)])
