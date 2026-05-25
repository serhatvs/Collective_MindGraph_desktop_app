"""Retrieval system provider submodule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from collective_mindgraph.shared import SourceReference


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    text: str
    source: SourceReference
    score: float


class RetrievalProvider(Protocol):
    """Provider boundary for vector, graph, lexical, or hybrid retrieval."""

    def retrieve(self, query_text: str, limit: int = 10) -> tuple[RetrievedContext, ...]:
        """Find relevant historical context."""
