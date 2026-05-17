"""Shared knowledge access service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.shared import KnowledgeRecordId, UserId, WorkspaceId


class SharedKnowledgeAccess(Protocol):
    """Controls visibility of extracted information across a team."""

    def visible_records(self, user_id: UserId, workspace_id: WorkspaceId) -> tuple[KnowledgeRecordId, ...]:
        """Return records a user may see in a workspace."""
