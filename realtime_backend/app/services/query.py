"""Minimal local-first keyword search over transcribed sessions."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..models import ConversationTranscript, DecisionItem, TaskItem, TopicSegment, TranscriptSegment

LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True)
class QueryResult:
    result_type: str  # "transcript" | "task" | "decision" | "topic"
    text: str
    source_session_id: str
    source_segment_id: str | None = None
    matched_field: str | None = None
    matched_terms: list[str] = field(default_factory=list)
    score: float = 1.0
    preview: str | None = None
    timestamp: str | None = None


class KeywordMemoryQueryService:
    """
    Heuristic keyword-based search over memory nodes.
    This is NOT a semantic or vector-based search.
    """
    def __init__(self, transcript_provider: Any) -> None:
        self._provider = transcript_provider

    def search(self, query: str, conversation_ids: list[str]) -> list[QueryResult]:
        if not query or not query.strip():
            return []

        search_terms = [t.lower() for t in query.split() if len(t) > 1]
        if not search_terms:
            return []

        results: list[QueryResult] = []

        for conv_id in conversation_ids:
            transcript = self._provider.get_transcript(conv_id)
            if not transcript:
                continue

            # 1. Search cleaned transcripts (segments)
            for segment in transcript.segments:
                content = (segment.corrected_text or segment.raw_text or "").lower()
                matches = [t for t in search_terms if t in content]
                if matches:
                    results.append(
                        QueryResult(
                            result_type="transcript",
                            text=segment.corrected_text or segment.raw_text,
                            source_session_id=conv_id,
                            source_segment_id=segment.segment_id,
                            matched_field="corrected_text" if segment.corrected_text else "raw_text",
                            matched_terms=matches,
                            score=self._calculate_score(len(matches), len(search_terms), "transcript"),
                            preview=self._build_preview(segment.corrected_text or segment.raw_text, matches[0]),
                            timestamp=transcript.created_at.isoformat()
                        )
                    )

            # 2. Search tasks
            for task in transcript.action_items:
                content = task.title.lower()
                matches = [t for t in search_terms if t in content]
                if matches:
                    results.append(
                        QueryResult(
                            result_type="task",
                            text=task.title,
                            source_session_id=conv_id,
                            source_segment_id=task.source_segment_id,
                            matched_field="title",
                            matched_terms=matches,
                            score=self._calculate_score(len(matches), len(search_terms), "task"),
                            timestamp=transcript.created_at.isoformat()
                        )
                    )

            # 3. Search decisions
            for decision in transcript.decisions:
                content = decision.decision.lower()
                matches = [t for t in search_terms if t in content]
                if matches:
                    results.append(
                        QueryResult(
                            result_type="decision",
                            text=decision.decision,
                            source_session_id=conv_id,
                            source_segment_id=decision.source_segment_id,
                            matched_field="decision",
                            matched_terms=matches,
                            score=self._calculate_score(len(matches), len(search_terms), "decision"),
                            timestamp=transcript.created_at.isoformat()
                        )
                    )

            # 4. Search topics
            for topic in transcript.topics:
                content = topic.label.lower()
                matches = [t for t in search_terms if t in content]
                if matches:
                    results.append(
                        QueryResult(
                            result_type="topic",
                            text=topic.label,
                            source_session_id=conv_id,
                            matched_field="label",
                            matched_terms=matches,
                            score=self._calculate_score(len(matches), len(search_terms), "topic"),
                            timestamp=transcript.created_at.isoformat()
                        )
                    )

        # Sort by score (descending) and then type
        return sorted(results, key=lambda x: (-x.score, x.result_type))

    @staticmethod
    def _calculate_score(match_count: int, total_terms: int, result_type: str) -> float:
        # Base: match ratio
        score = match_count / total_terms
        
        # Boost specific types to prioritize structured items over raw mentions
        type_boost = {
            "decision": 1.2,
            "task": 1.1,
            "topic": 1.05,
            "transcript": 1.0
        }
        return round(score * type_boost.get(result_type, 1.0), 4)

    @staticmethod
    def _build_preview(text: str, first_term: str) -> str:
        if not text:
            return ""
        try:
            index = text.lower().find(first_term)
            if index == -1:
                return text[:100]
            start = max(0, index - 40)
            end = min(len(text), index + 60)
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(text) else ""
            return prefix + text[start:end].strip() + suffix
        except Exception:
            return text[:100]
