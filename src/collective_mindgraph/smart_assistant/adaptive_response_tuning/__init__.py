"""Adaptive response tuning service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.smart_assistant.models import AssistantAnswer, AssistantQuery


class ResponseTuner(Protocol):
    """Adapts answer style and format for users or teams."""

    def tune(self, query: AssistantQuery, answer: AssistantAnswer) -> AssistantAnswer:
        """Return a style-adjusted answer without changing the evidence."""
