"""Context linking service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.knowledge_management_tool.models import KnowledgeLink, KnowledgeRecord


class ContextLinker(Protocol):
    """Connects related records without owning storage or retrieval providers."""

    def link(self, records: tuple[KnowledgeRecord, ...]) -> tuple[KnowledgeLink, ...]:
        """Return inferred links between records."""
