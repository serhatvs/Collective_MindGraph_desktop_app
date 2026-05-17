"""Assistant context builder service submodule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from collective_mindgraph.smart_assistant.retrieval_system import RetrievedContext


@dataclass(frozen=True, slots=True)
class AssistantContext:
    prompt_context: str
    retrieved: tuple[RetrievedContext, ...] = ()


class AssistantContextBuilder(Protocol):
    """Combines retrieved memory into a generation-ready context."""

    def build(self, query_text: str, retrieved: tuple[RetrievedContext, ...]) -> AssistantContext:
        """Build bounded assistant context."""
