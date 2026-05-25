"""Multi-user workspace repository submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.shared import WorkspaceId
from collective_mindgraph.collaboration_tool.models import Workspace


class WorkspaceRepository(Protocol):
    """Persistence boundary for team workspaces."""

    def save(self, workspace: Workspace) -> WorkspaceId:
        """Persist a workspace."""

    def get(self, workspace_id: WorkspaceId) -> Workspace | None:
        """Load one workspace."""
