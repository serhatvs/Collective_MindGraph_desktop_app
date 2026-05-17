"""Discussion context sharing service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.shared import ConversationId, WorkspaceId


class DiscussionContextSharing(Protocol):
    """Preserves and shares the context behind decisions."""

    def share_context(self, workspace_id: WorkspaceId, conversation_id: ConversationId) -> None:
        """Publish discussion context to an authorized workspace."""
