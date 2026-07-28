"""Vector persistence boundary used by memory search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from collective_mindgraph.domain import EvidenceId, KnowledgeNodeId


@dataclass(frozen=True, slots=True)
class EmbeddingMatch:
    node_id: KnowledgeNodeId
    score: float
    text_chunk: str
    evidence_id: EvidenceId | None = None


class EmbeddingStore(Protocol):
    def put(
        self,
        *,
        node_id: KnowledgeNodeId,
        vector: list[float],
        text_chunk: str,
        evidence_id: EvidenceId | None = None,
    ) -> str: ...

    def search(
        self,
        vector: list[float],
        *,
        limit: int = 10,
        threshold: float = 0.3,
    ) -> tuple[EmbeddingMatch, ...]: ...
