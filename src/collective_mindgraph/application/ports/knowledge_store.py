"""Insight and knowledge persistence ports."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from collective_mindgraph.application.pagination import Page, PageRequest
from collective_mindgraph.domain import (
    EvidenceId,
    EvidenceReference,
    Insight,
    InsightId,
    KnowledgeEdge,
    KnowledgeNode,
    KnowledgeNodeId,
    KnowledgeNodeKind,
    MeetingId,
    ReviewDecision,
)


class InsightStore(Protocol):
    def save(self, insight: Insight) -> None: ...

    def get(self, insight_id: InsightId) -> Insight | None: ...

    def list(
        self,
        request: PageRequest,
        *,
        meeting_id: MeetingId | None = None,
        review: ReviewDecision | None = None,
        query: str = "",
    ) -> Page[Insight]: ...

    def review(
        self,
        insight_id: InsightId,
        *,
        decision: ReviewDecision,
        title: str | None,
        body: str | None,
        now: datetime,
    ) -> Insight | None: ...

    def mark_meeting_insights_for_review(self, meeting_id: MeetingId, *, now: datetime) -> int: ...

    def pending_count(self) -> int: ...


class KnowledgeGraphStore(Protocol):
    def list_nodes(
        self,
        request: PageRequest,
        *,
        query: str = "",
        meeting_id: MeetingId | None = None,
        kind: KnowledgeNodeKind | None = None,
        review: ReviewDecision | None = None,
    ) -> Page[KnowledgeNode]: ...

    def list_edges(self, request: PageRequest, *, query: str = "") -> Page[KnowledgeEdge]: ...

    def get_node(self, node_id: KnowledgeNodeId) -> KnowledgeNode | None: ...

    def related_nodes(
        self,
        node_id: KnowledgeNodeId,
        *,
        include_rejected: bool = False,
    ) -> tuple[tuple[KnowledgeEdge, KnowledgeNode], ...]: ...

    def get_evidence(self, evidence_id: EvidenceId) -> EvidenceReference | None: ...

    def list_evidence(
        self,
        request: PageRequest,
        *,
        meeting_id: MeetingId,
    ) -> Page[EvidenceReference]: ...

    def save_evidence(self, evidence: EvidenceReference) -> None: ...

    def save_node(self, node: KnowledgeNode) -> None: ...

    def save_edge(self, edge: KnowledgeEdge) -> None: ...

    def review_node(
        self,
        node_id: KnowledgeNodeId,
        *,
        decision: ReviewDecision,
        title: str | None,
        body: str | None,
        now: datetime,
    ) -> KnowledgeNode | None: ...

    def mark_meeting_nodes_for_review(
        self,
        meeting_id: MeetingId,
        *,
        now: datetime,
    ) -> int: ...

    def count_nodes(self) -> int: ...
