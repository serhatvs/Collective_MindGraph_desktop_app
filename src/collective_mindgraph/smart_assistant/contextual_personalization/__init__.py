"""Contextual personalization service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.smart_assistant.models import AssistantQuery


class PersonalizationService(Protocol):
    """Applies organization-aware preferences to assistant behavior."""

    def personalize_query(self, query: AssistantQuery) -> AssistantQuery:
        """Return a query enriched with authorized preference context."""
