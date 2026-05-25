"""Search engine provider submodule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from collective_mindgraph.shared import OrganizationId
from collective_mindgraph.knowledge_management_tool.models import KnowledgeRecord


@dataclass(frozen=True, slots=True)
class SearchQuery:
    organization_id: OrganizationId
    text: str
    tags: tuple[str, ...] = ()
    limit: int = 10


class KnowledgeSearchProvider(Protocol):
    """Provider boundary for lexical, vector, or hybrid search."""

    def search(self, query: SearchQuery) -> tuple[KnowledgeRecord, ...]:
        """Find relevant records for a user or assistant request."""
