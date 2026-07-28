"""Human-review and transcript-correction use cases."""

from __future__ import annotations

from collective_mindgraph.domain import (
    Insight,
    InsightId,
    KnowledgeNodeId,
    ReviewDecision,
    SegmentId,
    TranscriptSegment,
)

from .meeting_workflows import Clock, utc_now
from .ports import InsightStore, KnowledgeGraphStore, TranscriptStore


class ReviewInsight:
    def __init__(
        self,
        insights: InsightStore,
        knowledge: KnowledgeGraphStore,
        clock: Clock = utc_now,
    ) -> None:
        self._insights = insights
        self._knowledge = knowledge
        self._clock = clock

    def __call__(
        self,
        insight_id: InsightId,
        *,
        decision: ReviewDecision,
        title: str | None = None,
        body: str | None = None,
    ) -> Insight | None:
        cleaned_title = title.strip() if title is not None else None
        cleaned_body = body.strip() if body is not None else None
        if title is not None and not cleaned_title and not cleaned_body:
            raise ValueError("A reviewed insight cannot be empty.")
        now = self._clock()
        insight = self._insights.review(
            insight_id,
            decision=decision,
            title=cleaned_title,
            body=cleaned_body,
            now=now,
        )
        if insight is not None:
            self._knowledge.review_node(
                KnowledgeNodeId(str(insight_id)),
                decision=decision,
                title=cleaned_title,
                body=cleaned_body,
                now=now,
            )
        return insight


class UpdateTranscriptSegment:
    def __init__(
        self,
        transcripts: TranscriptStore,
        insights: InsightStore,
        knowledge: KnowledgeGraphStore,
        clock: Clock = utc_now,
    ) -> None:
        self._transcripts = transcripts
        self._insights = insights
        self._knowledge = knowledge
        self._clock = clock

    def __call__(self, segment_id: SegmentId, corrected_text: str) -> TranscriptSegment | None:
        cleaned_text = corrected_text.strip()
        if not cleaned_text:
            raise ValueError("Corrected transcript text is required.")
        now = self._clock()
        meeting_id = self._transcripts.meeting_id_for_segment(segment_id)
        updated = self._transcripts.update_segment_text(
            segment_id,
            corrected_text=cleaned_text,
            now=now,
        )
        if updated is not None and meeting_id is not None:
            self._insights.mark_meeting_insights_for_review(meeting_id, now=now)
            self._knowledge.mark_meeting_nodes_for_review(meeting_id, now=now)
        return updated
