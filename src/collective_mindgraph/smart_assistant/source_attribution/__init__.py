"""Source attribution service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.smart_assistant.models import AssistantSource
from collective_mindgraph.smart_assistant.retrieval_system import RetrievedContext


class SourceAttributor(Protocol):
    """Attaches evidence references to generated answers."""

    def attribute(
        self,
        answer_text: str,
        context: tuple[RetrievedContext, ...],
    ) -> tuple[AssistantSource, ...]:
        """Return answer sources ranked by contribution."""
