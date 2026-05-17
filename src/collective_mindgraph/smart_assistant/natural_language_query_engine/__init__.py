"""Natural-language query engine service submodule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from collective_mindgraph.smart_assistant.models import AssistantQuery


@dataclass(frozen=True, slots=True)
class InterpretedQuery:
    normalized_text: str
    intent: str
    entities: tuple[str, ...] = ()


class QueryInterpreter(Protocol):
    """Understands user questions before retrieval or generation."""

    def interpret(self, query: AssistantQuery) -> InterpretedQuery:
        """Return a structured representation of the question."""
