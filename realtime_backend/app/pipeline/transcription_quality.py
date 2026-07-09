"""Estimated transcription quality scoring.

These scores are operational confidence estimates. They are not WER/CER and
must not be presented as real transcription accuracy without references.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..models import ASRSegment, TranscriptSegment

_MOJIBAKE_RE = re.compile(r"(�|Ã|Â|â€|Ä±|ÅŸ|ÄŸ|Ã§|Ã¶|Ã¼)")
_ALPHA_RE = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşü]")
_TURKISH_VOWEL_RE = re.compile(r"[aeıioöuüAEIİOÖUÜ]")


@dataclass(frozen=True, slots=True)
class TranscriptionConfidenceEstimate:
    score: int
    label: str
    audio_quality_score: int | None
    audio_quality_label: str | None
    segment_confidence: float | None
    avg_no_speech_prob: float | None
    empty_segment_ratio: float
    transcript_length_score: int
    turkish_text_sanity_score: int | None
    warnings: tuple[str, ...]

    def to_metadata(self) -> dict[str, object]:
        return {
            "score": self.score,
            "label": self.label,
            "audio_quality_score": self.audio_quality_score,
            "audio_quality_label": self.audio_quality_label,
            "segment_confidence": self.segment_confidence,
            "avg_no_speech_prob": self.avg_no_speech_prob,
            "empty_segment_ratio": self.empty_segment_ratio,
            "transcript_length_score": self.transcript_length_score,
            "turkish_text_sanity_score": self.turkish_text_sanity_score,
            "warnings": list(self.warnings),
            "interpretation": "Estimated transcription quality, not real accuracy or WER/CER.",
        }


def estimate_transcription_confidence(
    *,
    audio_quality: dict[str, object] | None,
    asr_segments: list[ASRSegment],
    transcript_segments: list[TranscriptSegment],
    language: str | None,
    duration_seconds: float | None,
) -> TranscriptionConfidenceEstimate:
    transcript_text = " ".join(
        (segment.corrected_text or segment.raw_text or "").strip()
        for segment in transcript_segments
        if (segment.corrected_text or segment.raw_text or "").strip()
    )
    audio_score = _optional_int(audio_quality.get("audio_quality_score")) if audio_quality else None
    audio_label = str(audio_quality.get("audio_quality_label")) if audio_quality and audio_quality.get("audio_quality_label") else None
    audio_component = (audio_score if audio_score is not None else 60) / 100.0
    segment_confidence = _average(_segment_confidence_values(asr_segments, transcript_segments))
    segment_component = segment_confidence if segment_confidence is not None else 0.55
    no_speech_values = [_safe_float(getattr(item, "no_speech_prob", None)) for item in asr_segments]
    no_speech_values = [value for value in no_speech_values if value is not None]
    avg_no_speech_prob = _average(no_speech_values)
    empty_segment_ratio = _empty_segment_ratio(transcript_segments)
    length_score = transcript_length_sanity_score(transcript_text, duration_seconds)
    turkish_score = turkish_text_sanity_score(transcript_text) if (language or "").lower() == "tr" else None
    text_component = length_score / 100.0
    language_component = (turkish_score / 100.0) if turkish_score is not None else text_component

    score = (
        0.30 * audio_component
        + 0.45 * segment_component
        + 0.15 * text_component
        + 0.10 * language_component
    ) * 100.0
    if avg_no_speech_prob is not None:
        score -= min(20.0, avg_no_speech_prob * 18.0)
    score -= min(25.0, empty_segment_ratio * 25.0)
    if not transcript_text.strip() and (duration_seconds or 0.0) > 1.0:
        score = min(score, 25.0)
    score_int = int(round(_clamp(score, 0.0, 100.0)))
    warnings = _confidence_warnings(
        score=score_int,
        audio_quality=audio_quality,
        avg_no_speech_prob=avg_no_speech_prob,
        empty_segment_ratio=empty_segment_ratio,
        transcript_length_score=length_score,
        turkish_text_sanity_score=turkish_score,
        transcript_text=transcript_text,
    )
    return TranscriptionConfidenceEstimate(
        score=score_int,
        label=confidence_label(score_int),
        audio_quality_score=audio_score,
        audio_quality_label=audio_label,
        segment_confidence=round(segment_confidence, 3) if segment_confidence is not None else None,
        avg_no_speech_prob=round(avg_no_speech_prob, 3) if avg_no_speech_prob is not None else None,
        empty_segment_ratio=round(empty_segment_ratio, 3),
        transcript_length_score=length_score,
        turkish_text_sanity_score=turkish_score,
        warnings=tuple(warnings),
    )


def transcript_length_sanity_score(text: str, duration_seconds: float | None) -> int:
    cleaned = text.strip()
    if not cleaned:
        return 0
    if not duration_seconds or duration_seconds <= 0.0:
        return 75
    chars_per_minute = len(cleaned) / max(duration_seconds / 60.0, 0.01)
    if chars_per_minute < 20:
        return 30
    if chars_per_minute < 60:
        return 60
    if chars_per_minute > 2600:
        return 55
    if chars_per_minute > 1800:
        return 75
    return 95


def turkish_text_sanity_score(text: str) -> int:
    cleaned = text.strip()
    if not cleaned:
        return 0
    alpha_count = len(_ALPHA_RE.findall(cleaned))
    if alpha_count < 5:
        return 35
    score = 100
    if _MOJIBAKE_RE.search(cleaned):
        score -= 30
    vowel_count = len(_TURKISH_VOWEL_RE.findall(cleaned))
    vowel_ratio = vowel_count / max(alpha_count, 1)
    if vowel_ratio < 0.22:
        score -= 20
    if sum(1 for char in cleaned if char.isdigit()) > max(12, len(cleaned) * 0.25):
        score -= 10
    return int(_clamp(score, 0, 100))


def confidence_label(score: int) -> str:
    if score >= 75:
        return "High"
    if score >= 50:
        return "Medium"
    return "Low"


def _segment_confidence_values(
    asr_segments: list[ASRSegment],
    transcript_segments: list[TranscriptSegment],
) -> list[float]:
    values: list[float] = []
    for segment in asr_segments:
        value = _safe_float(segment.metadata.get("segment_confidence_estimate"))
        if value is None:
            value = _safe_float(segment.confidence)
        if value is not None:
            values.append(_clamp(value, 0.0, 1.0))
    if values:
        return values
    for segment in transcript_segments:
        value = _safe_float(segment.confidence)
        if value is not None:
            values.append(_clamp(value, 0.0, 1.0))
    return values


def _empty_segment_ratio(transcript_segments: list[TranscriptSegment]) -> float:
    if not transcript_segments:
        return 1.0
    empty_count = 0
    for segment in transcript_segments:
        text = (segment.corrected_text or segment.raw_text or "").strip()
        if len(text) < 2:
            empty_count += 1
    return empty_count / len(transcript_segments)


def _confidence_warnings(
    *,
    score: int,
    audio_quality: dict[str, object] | None,
    avg_no_speech_prob: float | None,
    empty_segment_ratio: float,
    transcript_length_score: int,
    turkish_text_sanity_score: int | None,
    transcript_text: str,
) -> list[str]:
    warnings: list[str] = []
    if audio_quality:
        raw_warnings = audio_quality.get("warnings")
        if isinstance(raw_warnings, list):
            warnings.extend(str(item) for item in raw_warnings)
    if avg_no_speech_prob is not None and avg_no_speech_prob > 0.65:
        warnings.append("high no-speech probability")
    if empty_segment_ratio > 0.35:
        warnings.append("many empty or very short transcript segments")
    if transcript_length_score < 60:
        warnings.append("transcript length looks suspicious for audio duration")
    if turkish_text_sanity_score is not None and turkish_text_sanity_score < 70:
        warnings.append("Turkish text sanity check is low")
    if not transcript_text.strip():
        warnings.append("empty transcript")
    if score < 60:
        warnings.append("transcript should be manually reviewed")
    return _dedupe(warnings)


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    numeric = _safe_float(value)
    if numeric is None:
        return None
    return int(round(numeric))


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
