"""Hybrid keyword, local-vector, and relationship search."""

from __future__ import annotations

from collective_mindgraph.application.errors import ProviderUnavailableError
from collective_mindgraph.application.pagination import PageRequest
from collective_mindgraph.application.ports import (
    EmbeddingStore,
    KnowledgeGraphStore,
    TextEmbeddingModel,
)
from collective_mindgraph.domain import KnowledgeNodeId, MeetingId, ReviewDecision

from .memory_results import MemorySearchResult


class SearchMemory:
    def __init__(
        self,
        knowledge: KnowledgeGraphStore,
        embeddings: EmbeddingStore | None = None,
        embedding_model: TextEmbeddingModel | None = None,
        *,
        semantic_enabled: bool | None = None,
    ) -> None:
        self._knowledge = knowledge
        self._embeddings = embeddings
        self._embedding_model = embedding_model
        self._semantic_enabled = (
            embedding_model is not None if semantic_enabled is None else semantic_enabled
        )

    def __call__(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        meeting_id: MeetingId | None = None,
        include_pending: bool = False,
        limit: int = 50,
    ) -> tuple[MemorySearchResult, ...]:
        normalized = query.strip()
        if not normalized:
            raise ValueError("A memory query is required.")
        if mode not in {"keyword", "semantic", "hybrid"}:
            raise ValueError("Search mode must be keyword, semantic, or hybrid.")
        capped_limit = min(max(1, limit), 200)
        semantic_available = self._semantic_is_available()
        if mode == "semantic" and not semantic_available:
            raise ProviderUnavailableError("Semantic memory search is unavailable.")
        results: dict[KnowledgeNodeId, MemorySearchResult] = {}

        if mode in {"keyword", "hybrid"}:
            results.update(
                self._keyword_matches(
                    normalized,
                    meeting_id=meeting_id,
                    include_pending=include_pending,
                    limit=capped_limit,
                )
            )

        if mode in {"semantic", "hybrid"} and semantic_available:
            self._merge_semantic_matches(
                results,
                normalized,
                meeting_id=meeting_id,
                include_pending=include_pending,
                limit=capped_limit,
            )

        if mode == "hybrid":
            self._expand_graph(
                results,
                meeting_id=meeting_id,
                include_pending=include_pending,
            )

        ordered = sorted(
            results.values(),
            key=lambda item: (-item.score, item.node.title.casefold(), str(item.node.id)),
        )
        return tuple(ordered[:capped_limit])

    def _keyword_matches(
        self,
        query: str,
        *,
        meeting_id: MeetingId | None,
        include_pending: bool,
        limit: int,
    ) -> dict[KnowledgeNodeId, MemorySearchResult]:
        page = self._knowledge.list_nodes(
            PageRequest(limit=limit),
            query=query,
            meeting_id=meeting_id,
        )
        query_terms = {term.casefold() for term in query.split() if term}
        results: dict[KnowledgeNodeId, MemorySearchResult] = {}
        for node in page.items:
            if _is_excluded(node.attributes, include_pending):
                continue
            haystack = f"{node.title} {node.body}".casefold()
            hits = sum(term in haystack for term in query_terms)
            results[node.id] = MemorySearchResult(
                node=node,
                score=max(0.35, hits / max(1, len(query_terms))),
                matched_by=frozenset({"keyword"}),
                evidence=(
                    self._knowledge.get_evidence(node.evidence_id) if node.evidence_id else None
                ),
            )
        return results

    def _merge_semantic_matches(
        self,
        results: dict[KnowledgeNodeId, MemorySearchResult],
        query: str,
        *,
        meeting_id: MeetingId | None,
        include_pending: bool,
        limit: int,
    ) -> None:
        if self._embeddings is None or self._embedding_model is None:
            return
        for match in self._embeddings.search(
            self._embedding_model.embed_text(query),
            limit=limit,
        ):
            node = self._knowledge.get_node(match.node_id)
            if node is None or _is_excluded(node.attributes, include_pending):
                continue
            if meeting_id is not None and node.meeting_id != meeting_id:
                continue
            current = results.get(node.id)
            matched_by = {"semantic", *(current.matched_by if current else ())}
            results[node.id] = MemorySearchResult(
                node=node,
                score=max(match.score, current.score if current else 0.0),
                matched_by=frozenset(matched_by),
                evidence=(
                    self._knowledge.get_evidence(node.evidence_id) if node.evidence_id else None
                ),
            )

    def _expand_graph(
        self,
        results: dict[KnowledgeNodeId, MemorySearchResult],
        *,
        meeting_id: MeetingId | None,
        include_pending: bool,
    ) -> None:
        for seed in tuple(results.values()):
            for edge, node in self._knowledge.related_nodes(
                seed.node.id,
                include_rejected=False,
            ):
                if node.id in results or _is_excluded(node.attributes, include_pending):
                    continue
                if meeting_id is not None and node.meeting_id != meeting_id:
                    continue
                results[node.id] = MemorySearchResult(
                    node=node,
                    score=max(0.1, seed.score * 0.75),
                    matched_by=frozenset({"graph"}),
                    evidence=(
                        self._knowledge.get_evidence(node.evidence_id) if node.evidence_id else None
                    ),
                    related_from=edge,
                )

    def _semantic_is_available(self) -> bool:
        return (
            self._semantic_enabled
            and self._embeddings is not None
            and self._embedding_model is not None
            and self._embedding_model.is_available()
        )


def _is_excluded(attributes: dict[str, object], include_pending: bool) -> bool:
    review = str(attributes.get("review", ReviewDecision.ACCEPTED.value)).casefold()
    if review == ReviewDecision.REJECTED.value:
        return True
    if not include_pending and bool(attributes.get("needs_review")):
        return True
    return not include_pending and review == ReviewDecision.PENDING.value
