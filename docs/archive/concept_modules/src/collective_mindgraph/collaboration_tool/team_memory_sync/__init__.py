"""Team memory sync service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.shared import WorkspaceId


class TeamMemorySync(Protocol):
    """Keeps shared organizational memory current for team workspaces."""

    def sync(self, workspace_id: WorkspaceId) -> None:
        """Refresh all synchronized memory views for a workspace."""
