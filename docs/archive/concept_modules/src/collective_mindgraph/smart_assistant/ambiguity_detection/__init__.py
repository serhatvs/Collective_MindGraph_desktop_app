"""Ambiguity detection service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.smart_assistant.models import AssistantAnswer, AssistantQuery


class AmbiguityDetector(Protocol):
    """Flags uncertain or conflicting information."""

    def warnings(self, query: AssistantQuery, answer: AssistantAnswer) -> tuple[str, ...]:
        """Return ambiguity warnings that should be surfaced with the answer."""
