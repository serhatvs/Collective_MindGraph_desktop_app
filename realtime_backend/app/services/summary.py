"""Transcript summary and action-item helpers."""

from __future__ import annotations

from collections import Counter

from ..models import ConversationTranscript, TopicSegment, TranscriptSegment


class ConversationSummaryService:
    def build_summary(self, transcript: ConversationTranscript) -> tuple[str | None, list[TopicSegment], list[str]]:
        if not transcript.segments:
            return None, [], []

        summary = self._heuristic_summary(transcript.segments)
        topics = self._topic_segments(transcript.segments)
        action_items = self._action_items(transcript.segments)
        return summary, topics, action_items

    @staticmethod
    def _heuristic_summary(segments: list[TranscriptSegment]) -> str:
        first_lines = [segment.corrected_text for segment in segments[:3] if segment.corrected_text.strip()]
        last_lines = [segment.corrected_text for segment in segments[-2:] if segment.corrected_text.strip()]
        body = " ".join(first_lines + last_lines)
        return body[:700].strip()

    @staticmethod
    def _topic_segments(segments: list[TranscriptSegment]) -> list[TopicSegment]:
        if not segments:
            return []

        buckets: dict[str, list[TranscriptSegment]] = {"General discussion": []}
        for segment in segments:
            label = "Questions" if "?" in segment.corrected_text else "General discussion"
            buckets.setdefault(label, []).append(segment)

        topics: list[TopicSegment] = []
        for label, bucket in buckets.items():
            if not bucket:
                continue
            topics.append(
                TopicSegment(
                    label=label,
                    start=bucket[0].start,
                    end=bucket[-1].end,
                )
            )
        return topics

    @staticmethod
    def _action_items(segments: list[TranscriptSegment]) -> list[str]:
        candidates: list[str] = []
        for segment in segments:
            text = segment.corrected_text.strip()
            lowered = text.lower()
            if any(token in lowered for token in ("need to", "should", "action", "follow up", "todo")):
                candidates.append(text)

        if candidates:
            return candidates[:8]

        speakers = Counter(segment.speaker for segment in segments)
        if not speakers:
            return []
        dominant = speakers.most_common(1)[0][0]
        return [f"Review conversation items raised by {dominant}."]
