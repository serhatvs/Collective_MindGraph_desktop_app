"""Transcript quality metrics and operational warnings."""

from __future__ import annotations

import re
from collections import Counter

from ..models import ConversationTranscript, QualityComparison, QualityReport

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9'-]{1,}")


class TranscriptQualityService:
    def build_report(
        self,
        transcript: ConversationTranscript,
        reference: ConversationTranscript | None = None,
    ) -> QualityReport:
        segments = transcript.segments
        segment_count = len(segments)
        speaker_count = len({segment.speaker for segment in segments})
        unresolved_segments = sum(1 for segment in segments if segment.speaker.startswith("UNRESOLVED"))
        overlap_ratio = self._ratio(sum(1 for segment in segments if segment.overlap), segment_count)
        avg_asr_confidence = self._average(
            [segment.confidence for segment in segments if segment.confidence is not None]
        )
        avg_speaker_confidence = self._average(
            [segment.speaker_confidence for segment in segments if segment.speaker_confidence is not None]
        )
        word_timing_coverage = self._ratio(
            sum(1 for segment in segments if segment.words),
            segment_count,
        )
        corrected_change_ratio = self._ratio(
            sum(
                1
                for segment in segments
                if segment.corrected_text.strip() != segment.raw_text.strip()
            ),
            segment_count,
        )
        question_count = sum(1 for segment in segments if "?" in segment.corrected_text)
        report = QualityReport(
            conversation_id=transcript.conversation_id,
            segment_count=segment_count,
            speaker_count=speaker_count,
            unresolved_segments=unresolved_segments,
            overlap_ratio=overlap_ratio,
            avg_asr_confidence=avg_asr_confidence,
            avg_speaker_confidence=avg_speaker_confidence,
            word_timing_coverage=word_timing_coverage,
            corrected_change_ratio=corrected_change_ratio,
            topic_count=len(transcript.topics),
            action_item_count=len(transcript.action_items),
            decision_count=len(transcript.decisions),
            question_count=question_count,
            summary_present=bool((transcript.summary or "").strip()),
            comparison=self._comparison(transcript, reference),
            warnings=self._warnings(
                unresolved_segments=unresolved_segments,
                segment_count=segment_count,
                avg_asr_confidence=avg_asr_confidence,
                avg_speaker_confidence=avg_speaker_confidence,
                word_timing_coverage=word_timing_coverage,
                overlap_ratio=overlap_ratio,
                summary_present=bool((transcript.summary or "").strip()),
            ),
        )
        return report

    @staticmethod
    def _comparison(
        transcript: ConversationTranscript,
        reference: ConversationTranscript | None,
    ) -> QualityComparison | None:
        if reference is None:
            return None

        transcript_tokens = Counter(_TOKEN_RE.findall(" ".join(item.corrected_text for item in transcript.segments).lower()))
        reference_tokens = Counter(_TOKEN_RE.findall(" ".join(item.corrected_text for item in reference.segments).lower()))
        text_overlap = _counter_overlap(transcript_tokens, reference_tokens)

        speaker_matches = 0
        comparable = min(len(transcript.segments), len(reference.segments))
        if comparable:
            speaker_matches = sum(
                1
                for index in range(comparable)
                if transcript.segments[index].speaker == reference.segments[index].speaker
            )
        speaker_match_ratio = TranscriptQualityService._ratio(speaker_matches, comparable)

        action_item_overlap = _counter_overlap(
            Counter(item.lower() for item in transcript.action_items),
            Counter(item.lower() for item in reference.action_items),
        )
        summary_overlap = _counter_overlap(
            Counter(_TOKEN_RE.findall((transcript.summary or "").lower())),
            Counter(_TOKEN_RE.findall((reference.summary or "").lower())),
        )
        return QualityComparison(
            text_overlap=text_overlap,
            speaker_match_ratio=speaker_match_ratio,
            action_item_overlap=action_item_overlap,
            summary_overlap=summary_overlap,
        )

    @staticmethod
    def _warnings(
        *,
        unresolved_segments: int,
        segment_count: int,
        avg_asr_confidence: float | None,
        avg_speaker_confidence: float | None,
        word_timing_coverage: float,
        overlap_ratio: float,
        summary_present: bool,
    ) -> list[str]:
        warnings: list[str] = []
        if segment_count == 0:
            warnings.append("no transcript segments were produced")
            return warnings
        if unresolved_segments > 0:
            warnings.append("some segments still use unresolved speaker attribution")
        if avg_asr_confidence is not None and avg_asr_confidence < 0.65:
            warnings.append("average ASR confidence is low")
        if avg_speaker_confidence is not None and avg_speaker_confidence < 0.60:
            warnings.append("average speaker confidence is low")
        if word_timing_coverage < 0.75:
            warnings.append("word timestamp coverage is limited")
        if overlap_ratio > 0.20:
            warnings.append("overlap-heavy conversation may still contain attribution errors")
        if not summary_present:
            warnings.append("summary was not generated")
        return warnings

    @staticmethod
    def _average(values: list[float]) -> float | None:
        if not values:
            return None
        return round(sum(values) / len(values), 3)

    @staticmethod
    def _ratio(numerator: int | float, denominator: int | float) -> float:
        if not denominator:
            return 0.0
        return round(float(numerator) / float(denominator), 3)


def _counter_overlap(left: Counter[str], right: Counter[str]) -> float | None:
    if not left and not right:
        return None
    if not left or not right:
        return 0.0
    shared = sum(min(left[key], right[key]) for key in set(left) | set(right))
    total = sum(max(left[key], right[key]) for key in set(left) | set(right))
    if not total:
        return None
    return round(shared / total, 3)
