"""Home-workspace dashboard query."""

from __future__ import annotations

from dataclasses import dataclass

from collective_mindgraph.domain import Meeting

from .pagination import PageRequest
from .ports import InsightStore, KnowledgeGraphStore, MeetingStore, TranscriptStore


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    total_meetings: int
    total_transcripts: int
    total_knowledge_nodes: int
    pending_reviews: int
    recent_meetings: tuple[Meeting, ...]


class GetDashboard:
    def __init__(
        self,
        meetings: MeetingStore,
        transcripts: TranscriptStore,
        insights: InsightStore,
        knowledge: KnowledgeGraphStore,
    ) -> None:
        self._meetings = meetings
        self._transcripts = transcripts
        self._insights = insights
        self._knowledge = knowledge

    def __call__(self) -> DashboardSnapshot:
        recent = self._meetings.list(PageRequest(limit=8))
        return DashboardSnapshot(
            total_meetings=self._meetings.count(),
            total_transcripts=self._transcripts.count(),
            total_knowledge_nodes=self._knowledge.count_nodes(),
            pending_reviews=self._insights.pending_count(),
            recent_meetings=recent.items,
        )
