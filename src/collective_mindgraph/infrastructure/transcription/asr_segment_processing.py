"""Timeline and confidence processing shared by ASR adapters."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from collective_mindgraph.application.transcription.contracts import (
    ASRSegment,
    SpeechRegion,
    WordTimestamp,
)
from collective_mindgraph.application.transcription.time_ranges import overlap_ratio
from collective_mindgraph.infrastructure.audio.wav_files import extract_wav_region


def regions_for_asr(
    regions: list[SpeechRegion],
    padding_seconds: float,
) -> list[SpeechRegion]:
    windows: list[SpeechRegion] = []
    for region in sorted(regions, key=lambda item: item.start):
        padded = SpeechRegion(
            start=max(0.0, region.start - padding_seconds),
            end=region.end + padding_seconds,
            confidence=region.confidence,
        )
        if not windows:
            windows.append(padded)
            continue
        previous = windows[-1]
        if padded.start <= previous.end:
            windows[-1] = SpeechRegion(
                start=previous.start,
                end=max(previous.end, padded.end),
                confidence=previous.confidence or padded.confidence,
            )
            continue
        windows.append(padded)
    return windows


def extract_region(
    source_path: Path,
    start_seconds: float,
    end_seconds: float,
    target_dir: Path,
) -> Path:
    return extract_wav_region(source_path, start_seconds, end_seconds, target_dir)


def dedupe_segments(segments: list[ASRSegment]) -> list[ASRSegment]:
    ordered = sorted(segments, key=lambda item: (item.start, item.end, item.text))
    unique: list[ASRSegment] = []
    for segment in ordered:
        if unique and _segments_look_duplicate(unique[-1], segment):
            continue
        unique.append(segment)
    return unique


def offset_value(value: float | None, offset_seconds: float) -> float | None:
    if value is None:
        return None
    return float(value) + offset_seconds


def average_probability(words: list[WordTimestamp]) -> float | None:
    probabilities = [item.probability for item in words if item.probability is not None]
    if not probabilities:
        return None
    return float(sum(probabilities) / len(probabilities))


def estimate_segment_confidence(
    *,
    word_confidence: float | None,
    avg_logprob: float | None,
    no_speech_prob: float | None,
    compression_ratio: float | None,
) -> float | None:
    candidates: list[float] = []
    if word_confidence is not None:
        candidates.append(_clamp(float(word_confidence), 0.0, 1.0))
    if avg_logprob is not None:
        candidates.append(_clamp(math.exp(float(avg_logprob)), 0.0, 1.0))
    if not candidates:
        return None
    score = sum(candidates) / len(candidates)
    if no_speech_prob is not None:
        score *= 1.0 - (0.45 * _clamp(no_speech_prob, 0.0, 1.0))
    if compression_ratio is not None and compression_ratio > 2.4:
        score *= 0.85
    if compression_ratio is not None and compression_ratio > 3.0:
        score *= 0.75
    return round(_clamp(score, 0.0, 1.0), 3)


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _segments_look_duplicate(left: ASRSegment, right: ASRSegment) -> bool:
    return (
        overlap_ratio(left.start, left.end, right.start, right.end) >= 0.85
        and left.text.strip().lower() == right.text.strip().lower()
    )


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
