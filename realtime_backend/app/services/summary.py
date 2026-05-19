"""Transcript summary, topic, decision, and action-item helpers."""

from __future__ import annotations

import re
from collections import Counter

from ..models import ConversationTranscript, DecisionItem, TaskItem, TopicSegment, TranscriptSegment

_TOKEN_RE = re.compile(r"[a-zA-ZçğışöüÇĞİŞÖÜ][a-zA-Z0-9'çğışöüÇĞİŞÖÜ-]{2,}")
_ACTION_PATTERNS = (
    re.compile(r"\b(?:i|we|you|they)\s+(?:need to|should|must|will|have to)\s+(.+)", re.IGNORECASE),
    re.compile(r"\blet'?s\s+(.+)", re.IGNORECASE),
    re.compile(r"\bplease\s+(.+)", re.IGNORECASE),
    re.compile(r"\btodo[:\s-]+(.+)", re.IGNORECASE),
    re.compile(r"\bcan you\s+(.+)", re.IGNORECASE),
    # Turkish Action Patterns
    # 1. Necessity/Requirement (Capture full phrase including verb)
    re.compile(r"(.+\s+(?:yapmalıyız|etmeliyiz|yapmalısın|etmelisin|iyileştirmeliyiz|yapmamız gerekiyor|etmemiz gerekiyor|gerekiyor|lazım|gerek|gerekmektedir))\b", re.IGNORECASE),
    # 2. Future Action
    re.compile(r"(.+\s+(?:yapacağız|edeceğiz|yapılacak|edilecek|bakılacak|kontrol edilecek|test edilecek|göstereceğiz))\b", re.IGNORECASE),
    # 3. Request/Directive
    re.compile(r"\b(?:lütfen)\s+(.+)", re.IGNORECASE),
    re.compile(r"(.+\s+(?:etsin|yapsın|hazırlasın))\b", re.IGNORECASE),
    # 4. Name-based assignment: Serhat ... yapsın/edecek
    re.compile(r"\b([A-ZÇĞİŞÖÜ][a-zçğışöü]+)\s+(.+)\s+(?:etsin|yapsın|edecek|yapacak|bakacak)\b"),
)
_DECISION_PATTERNS = (
    re.compile(r"\b(?:we|i)\s+(?:will|won't)\s+(.+)", re.IGNORECASE),
    re.compile(r"\bdecided to\s+(.+)", re.IGNORECASE),
    re.compile(r"\bagreed to\s+(.+)", re.IGNORECASE),
    re.compile(r"\blet'?s\s+(.+)", re.IGNORECASE),
    re.compile(r"\bsounds good\b", re.IGNORECASE),
    # Turkish Decision Patterns
    # 1. Explicit Agreement (Capture full phrase)
    re.compile(r"(.+\s+(?:kararlaştırıldı|karar verildi|karar verdik|anlaşıldı|kararı alındı))\b", re.IGNORECASE),
    re.compile(r"\b(karar verdik|anlaştık)\b", re.IGNORECASE),
    # 2. State-based Decision (Passive)
    re.compile(r"(.+\s+(?:ayrı tutulacak|kalacak|bırakıldı|olacak|seçildi))\b", re.IGNORECASE),
    # 3. Simple agreement markers
    re.compile(r"\b(tamam|uygun|peki)\b", re.IGNORECASE),
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
    ) -> tuple[str | None, list[TopicSegment], list[TaskItem], list[DecisionItem]]:
        if not transcript.segments:
            return None, [], [], []

        topics = self._topic_segments(transcript.segments)
        action_items = self._action_items(transcript.segments)
        decisions = self._decisions(transcript.segments)
        
        # Populate people list - filter out generic/unknown labels
        transcript.people = sorted({
            s.speaker for s in transcript.segments 
            if s.speaker and "Speaker_" not in s.speaker and "UNRESOLVED_" not in s.speaker and s.speaker != "Unknown"
        })
        
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
        action_items: list[TaskItem],
        decisions: list[DecisionItem],
    ) -> str:
        summary_parts: list[str] = []
        summary_parts.append(
            f"Technical conversation covered "
            f"{', '.join(topic.label for topic in topics[:3]) or 'general discussion'}."
        )

        first_lines = [
            (s.corrected_text or s.raw_text).strip()
            for s in segments[:2]
            if (s.corrected_text or s.raw_text).strip()
        ]
        if first_lines:
            summary_parts.append("Early context: " + " ".join(first_lines)[:220].strip())
        if decisions:
            summary_parts.append("Decisions: " + "; ".join(d.decision for d in decisions[:2]))
        if action_items:
            summary_parts.append("Action items: " + "; ".join(t.title for t in action_items[:3]))

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
        text = (segment.corrected_text or segment.raw_text).strip()
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

    def _action_items(self, segments: list[TranscriptSegment]) -> list[TaskItem]:
        candidates: list[TaskItem] = []
        seen: set[str] = set()
        for segment in segments:
            text = (segment.corrected_text or segment.raw_text).strip()
            # Split into sentences using a lookbehind to keep the punctuation
            sentences = re.split(r'(?<=[.!?])\s+', text)
            for sentence in sentences:
                lowered = sentence.strip().lower()
                if not lowered:
                    continue
                
                # Check for specific patterns
                match_result = None
                for pattern in _ACTION_PATTERNS:
                    match = pattern.search(lowered)
                    if match:
                        match_result = match
                        active_pattern = pattern
                        break
                
                if not match_result:
                    continue
                
                # Responsible person extraction logic
                raw_speaker = segment.speaker
                responsible = raw_speaker
                
                # If speaker is generic/unknown, mark as Unassigned
                if not raw_speaker or "Speaker_" in raw_speaker or "UNRESOLVED_" in raw_speaker or raw_speaker == "Unknown":
                    responsible = "Unassigned"
                
                # Check if it was the name-based pattern (e.g. "Serhat ... yapsın")
                # Group 1 is name, Group 2 is title
                if len(match_result.groups()) >= 2 and match_result.group(1).istitle():
                    responsible = match_result.group(1)
                    title = self._clean_excerpt(match_result.group(2))
                else:
                    title = self._clean_excerpt(match_result.group(1))

                if not title:
                    continue
                    
                item_key = f"{responsible}: {title}".lower()
                if item_key in seen:
                    continue
                seen.add(item_key)
                candidates.append(
                    TaskItem(
                        title=title,
                        responsible_person=responsible,
                        source_segment_id=segment.segment_id,
                        confidence_note="heuristic match",
                    )
                )
        if candidates:
            return candidates[:8]

        # Use Unassigned for fallback
        return [
            TaskItem(
                title="Review open points from the conversation.",
                responsible_person="Unassigned",
                confidence_note="default fallback",
            )
        ]

    def _decisions(self, segments: list[TranscriptSegment]) -> list[DecisionItem]:
        decisions: list[DecisionItem] = []
        seen: set[str] = set()
        for segment in segments:
            text = (segment.corrected_text or segment.raw_text).strip()
            sentences = re.split(r'(?<=[.!?])\s+', text)
            for sentence in sentences:
                lowered = sentence.strip().lower()
                if not lowered:
                    continue
                matched = self._match_patterns(lowered, _DECISION_PATTERNS)
                if matched is None:
                    continue
                decision_text = self._clean_excerpt(matched)
                if not decision_text:
                    decision_text = sentence.strip()

                item_key = f"{segment.speaker}: {decision_text}".lower()
                if item_key in seen:
                    continue
                seen.add(item_key)
                decisions.append(
                    DecisionItem(
                        decision=decision_text,
                        source_segment_id=segment.segment_id,
                        confidence_note="heuristic match",
                    )
                )
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
