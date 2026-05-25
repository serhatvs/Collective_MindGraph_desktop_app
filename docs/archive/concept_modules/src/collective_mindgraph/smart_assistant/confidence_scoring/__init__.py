""""Confidence scoring service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.smart_assistant.models import AssistantAnswer


class ConfidenceScorer(Protocol):
    """Estimates reliability of generated answers."""

    def score(self, answer: AssistantAnswer) -> float:
        """Return a normalized confidence score."""
