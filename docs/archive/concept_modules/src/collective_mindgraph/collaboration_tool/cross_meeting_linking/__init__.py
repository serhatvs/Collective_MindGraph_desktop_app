"""Cross-meeting linking service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.shared import ConversationId, KnowledgeRecordId


class CrossMeetingLinker(Protocol):
    """Connects related discussions across sessions."""

    def link_conversations(
        self,
        conversation_ids: tuple[ConversationId, ...],
    ) -> tuple[KnowledgeRecordId, ...]:
        """Return records that represent cross-meeting links."""
