"""Response generator provider submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.smart_assistant.context_builder import AssistantContext
from collective_mindgraph.smart_assistant.models import AssistantAnswer


class ResponseGenerator(Protocol):
    """Provider boundary for local, on-prem, or API-backed answer models."""

    def generate(self, question: str, context: AssistantContext) -> AssistantAnswer:
        """Produce an answer grounded in supplied context."""
