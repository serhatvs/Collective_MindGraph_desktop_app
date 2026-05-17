"""Public service boundary for collaboration workflows."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.shared import KnowledgeRecordId, WorkspaceId


class CollaborationService(Protocol):
    """Coordinates workspace access, sync, and shared decision context."""

    def publish_record(self, workspace_id: WorkspaceId, record_id: KnowledgeRecordId) -> None:
        """Make a memory record visible to an authorized workspace."""

    def sync_workspace_memory(self, workspace_id: WorkspaceId) -> None:
        """Synchronize derived memory views for a workspace."""
