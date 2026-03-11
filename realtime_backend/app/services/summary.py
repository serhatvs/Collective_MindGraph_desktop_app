"""Transcript summary, topic, decision, and action-item helpers."""

from __future__ import annotations

import re
from collections import Counter

from ..models import ConversationTranscript, TopicSegment, TranscriptSegment

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9'-]{2,}")
_ACTION_PATTERNS = (
    re.compile(r"\b(?:i|we|you|they)\s+(?:need to|should|must|will|have to)\s+(.+)", re.IGNORECASE),
    re.compile(r"\blet'?s\s+(.+)", re.IGNORECASE),
    re.compile(r"\bplease\s+(.+)", re.IGNORECASE),
    re.compile(r"\btodo[:\s-]+(.+)", re.IGNORECASE),
    re.compile(r"\bcan you\s+(.+)", re.IGNORECASE),
)
_DECISION_PATTERNS = (
    re.compile(r"\b(?:we|i)\s+(?:will|won't)\s+(.+)", re.IGNORECASE),
    re.compile(r"\bdecided to\s+(.+)", re.IGNORECASE),
    re.compile(r"\bagreed to\s+(.+)", re.IGNORECASE),
    re.compile(r"\blet'?s\s+(.+)", re.IGNORECASE),
    re.compile(r"\bsounds good\b", re.IGNORECASE),
)
_QUESTION_WORDS = {"what", "why", "when", "where", "who", "how", "which", "can", "should", "do"}
_STOPWORDS = {
    "about",
    "after",
    "also",
    "been",
    "before",
    "could",
    "from",
    "have",
    "into",
    "just",
    "like",
    "make",
    "more",
    "need",
    "next",
    "only",
    "really",
    "should",
    "some",
    "that",
    "them",
    "then",
    "there",
    "they",
    "this",
    "today",
    "tomorrow",
    "want",
    "were",
    "what",
    "when",
    "where",
    "which",
    "will",
    "with",
    "would",
    "yeah",
    "okay",
    "right",
}


class ConversationSummaryService:
    def build_summary(
        self,
        transcript: ConversationTranscript,
    ) -> tuple[str | None, list[TopicSegment], list[str], list[str]]:
        if not transcript.segments:
            return None, [], [], []

        topics = self._topic_segments(transcript.segments)
        action_items = self._action_items(transcript.segments)
        decisions = self._decisions(transcript.segments)
        summary = self._heuristic_summary(
            transcript.segments,
            topics=topics,
            action_items=action_items,
            decisions=decisions,
        )
        return summary, topics, action_items, decisions

    def _heuristic_summary(
        self,
        segments: list[TranscriptSegment],
        *,
        topics: list[TopicSegment],
        action_items: list[str],
        decisions: list[str],
    ) -> str:
        speakers = sorted({segment.speaker for segment in segments})
        summary_parts: list[str] = []
        summary_parts.append(
            f"{len(speakers)} speaker{'s' if len(speakers) != 1 else ''} covered "
            f"{', '.join(topic.label for topic in topics[:3]) or 'general discussion'}."
        )

        first_lines = [segment.corrected_text.strip() for segment in segments[:2] if segment.corrected_text.strip()]
        if first_lines:
            summary_parts.append("Early context: " + " ".join(first_lines)[:220].strip())
        if decisions:
            summary_parts.append("Decisions: " + "; ".join(decisions[:2]))
        if action_items:
            summary_parts.append("Action items: " + "; ".join(action_items[:3]))

        summary = " ".join(part.strip() for part in summary_parts if part.strip()).strip()
        return summary[:700]

    def _topic_segments(self, segments: list[TranscriptSegment]) -> list[TopicSegment]:
        if not segments:
            return []

        topics: list[TopicSegment] = []
        current_label: str | None = None
        current_start = 0.0
        current_end = 0.0

        for segment in segments:
            label = self._topic_label(segment)
            if current_label is None:
                current_label = label
                current_start = segment.start
                current_end = segment.end
                continue

            time_gap = max(0.0, segment.start - current_end)
            if label == current_label and time_gap <= 45.0:
                current_end = max(current_end, segment.end)
                continue

            topics.append(TopicSegment(label=current_label, start=current_start, end=current_end))
            current_label = label
            current_start = segment.start
            current_end = segment.end

        if current_label is not None:
            topics.append(TopicSegment(label=current_label, start=current_start, end=current_end))
        return topics[:12]

    def _topic_label(self, segment: TranscriptSegment) -> str:
        text = segment.corrected_text.strip()
        lowered = text.lower()
        tokens = self._keywords(text)

        if text.endswith("?") or any(lowered.startswith(f"{item} ") for item in _QUESTION_WORDS):
            return "Questions"
        if self._match_patterns(lowered, _DECISION_PATTERNS):
            return "Decisions"
        if self._match_patterns(lowered, _ACTION_PATTERNS):
            return "Action Items"
        if not tokens:
            return "General Discussion"

        top_tokens = [token for token, _count in Counter(tokens).most_common(2)]
        return " / ".join(token.title() for token in top_tokens)

    def _action_items(self, segments: list[TranscriptSegment]) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()
        for segment in segments:
            text = segment.corrected_text.strip()
            lowered = text.lower()
            matched = self._match_patterns(lowered, _ACTION_PATTERNS)
            if matched is None:
                continue
            item = f"{segment.speaker}: {self._clean_excerpt(matched)}"
            if item.lower() in seen:
                continue
            seen.add(item.lower())
            candidates.append(item)
        if candidates:
            return candidates[:8]

        speakers = Counter(segment.speaker for segment in segments)
        if not speakers:
            return []
        dominant = speakers.most_common(1)[0][0]
        return [f"{dominant}: Review open points from the conversation."]

    def _decisions(self, segments: list[TranscriptSegment]) -> list[str]:
        decisions: list[str] = []
        seen: set[str] = set()
        for segment in segments:
            text = segment.corrected_text.strip()
            lowered = text.lower()
            matched = self._match_patterns(lowered, _DECISION_PATTERNS)
            if matched is None:
                continue
            decision = f"{segment.speaker}: {self._clean_excerpt(matched)}"
            if decision.lower() in seen:
                continue
            seen.add(decision.lower())
            decisions.append(decision)
        return decisions[:8]

    @staticmethod
    def _keywords(text: str) -> list[str]:
        return [
            token.lower()
            for token in _TOKEN_RE.findall(text)
            if token.lower() not in _STOPWORDS
        ]

    @staticmethod
    def _clean_excerpt(text: str) -> str:
        cleaned = text.strip(" .,:;!-")
        return cleaned[:1].upper() + cleaned[1:] if cleaned else ""

    @staticmethod
    def _match_patterns(text: str, patterns: tuple[re.Pattern[str], ...]) -> str | None:
        for pattern in patterns:
            match = pattern.search(text)
            if match is None:
                continue
            if match.groups():
                return match.group(1)
            return match.group(0)
        return None
