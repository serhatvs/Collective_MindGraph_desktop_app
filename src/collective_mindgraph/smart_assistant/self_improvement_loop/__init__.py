"""Self-improvement loop service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.smart_assistant.models import AssistantAnswer, AssistantQuery


class FeedbackLearner(Protocol):
    """Learns from user feedback and manual corrections."""

    def record_feedback(self, query: AssistantQuery, answer: AssistantAnswer, rating: int) -> None:
        """Store feedback for later prompt, retrieval, or memory refinement."""
