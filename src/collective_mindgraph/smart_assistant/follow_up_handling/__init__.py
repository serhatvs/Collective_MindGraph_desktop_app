"""Follow-up handling service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.smart_assistant.models import AssistantQuery


class FollowUpHandler(Protocol):
    """Maintains multi-turn question context."""

    def rewrite_with_history(
        self,
        query: AssistantQuery,
        prior_turns: tuple[str, ...],
    ) -> AssistantQuery:
        """Rewrite a follow-up into a standalone grounded query."""
