"""Public service boundary for grounded assistant workflows."""

from __future__ import annotations

from typing import Protocol

from .models import AssistantAnswer, AssistantQuery


class SmartAssistantService(Protocol):
    """Coordinates query interpretation, retrieval, generation, and reliability."""

    def answer(self, query: AssistantQuery) -> AssistantAnswer:
        """Answer a user question using authorized organizational memory."""

    def accept_feedback(self, query: AssistantQuery, answer: AssistantAnswer, rating: int) -> None:
        """Feed response quality signals into the improvement loop."""
