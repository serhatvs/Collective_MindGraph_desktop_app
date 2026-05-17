"""Meeting-scoped query assistant submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.shared import ConversationId


class MeetingQueryAssistant(Protocol):
    """Answers questions against one meeting before escalating to org memory."""

    def answer(self, conversation_id: ConversationId, question: str) -> str:
        """Answer using only authorized meeting context."""
