"""Deterministic scoring and selection for raw ASR candidates."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

from ..models import ASRSegment
from .transcription_quality import turkish_text_sanity_score


_WORD_RE = re.compile(r"[\w'-]+", flags=re.UNICODE)


@dataclass(frozen=True, slots=True)
class CandidateScore:
    score: float
    components: dict[str, float]
    warnings: tuple[str, ...]

    def to_metadata(self) -> dict[str, object]:
        return {
            "score": self.score,
            "components": dict(self.components),
            "warnings": list(self.warnings),
            "interpretation": "Estimated candidate quality, not accuracy or WER/CER.",
        }


@dataclass(frozen=True, slots=True)
class CandidateSelection:
    selected_pass: str
    first_pass: CandidateScore
    second_pass: CandidateScore
    score_difference: float
    selection_reason: str
    glossary_preservation_penalty: float

    def to_metadata(
        self,
        *,
        first_pass_text: str,
        second_pass_text: str,
        trigger_reasons: Iterable[str],
    ) -> dict[str, object]:
        return {
            "selected_pass": self.selected_pass,
            "first_pass_score": self.first_pass.score,
            "second_pass_score": self.second_pass.score,
            "score_difference": self.score_difference,
            "selection_reason": self.selection_reason,
            "first_pass_text": first_pass_text,
            "second_pass_text": second_pass_text,
            "retranscription_trigger_reasons": list(trigger_reasons),
            "glossary_preservation_penalty": self.glossary_preservation_penalty,
            "first_pass_candidate": self.first_pass.to_metadata(),
            "second_pass_candidate": self.second_pass.to_metadata(),
        }


class TranscriptionCandidateSelector:
    def __init__(
        self,
        *,
        min_improvement: float,
        min_words_per_second: float,
        max_words_per_second: float,
        min_text_length: int,
    ) -> None:
        self._min_improvement = max(0.0, float(min_improvement))
        self._min_words_per_second = max(0.0, float(min_words_per_second))
        self._max_words_per_second = max(self._min_words_per_second, float(max_words_per_second))
        self._min_text_length = max(1, int(min_text_length))

    def score(self, candidate: ASRSegment, *, language: str | None) -> CandidateScore:
        text = candidate.text.strip()
        duration = max(0.0, candidate.end - candidate.start)
        word_probability = mean_word_probability(candidate)
        logprob_score = _logprob_score(candidate.avg_logprob)
        word_probability_score = _probability_score(word_probability, candidate.confidence)
        no_speech_score = _no_speech_score(candidate.no_speech_prob)
        compression_score = _compression_score(candidate.compression_ratio)
        duration_text_score, duration_warnings = self._duration_text_score(text, duration)
        language_score = (
            float(turkish_text_sanity_score(text))
            if (language or "").strip().lower() == "tr"
            else duration_text_score
        )
        repetition_ratio = _repetition_ratio(text)
        repetition_penalty = min(30.0, max(0.0, repetition_ratio - 0.25) * 60.0)
        timestamps_valid = _timestamps_valid(candidate)
        timestamp_penalty = 0.0 if timestamps_valid else 18.0

        weighted = (
            0.30 * logprob_score
            + 0.25 * word_probability_score
            + 0.15 * no_speech_score
            + 0.10 * compression_score
            + 0.15 * duration_text_score
            + 0.05 * language_score
        )
        score = _clamp(weighted - repetition_penalty - timestamp_penalty, 0.0, 100.0)
        warnings = list(duration_warnings)
        if repetition_penalty:
            warnings.append("repeated text pattern")
        if not timestamps_valid:
            warnings.append("invalid timestamp shape")
        if not text:
            warnings.append("empty candidate")
        return CandidateScore(
            score=round(score, 3),
            components={
                "avg_logprob": round(logprob_score, 3),
                "word_probability": round(word_probability_score, 3),
                "no_speech": round(no_speech_score, 3),
                "compression": round(compression_score, 3),
                "duration_text_sanity": round(duration_text_score, 3),
                "language_sanity": round(language_score, 3),
                "repetition_penalty": round(repetition_penalty, 3),
                "timestamp_penalty": round(timestamp_penalty, 3),
            },
            warnings=tuple(_dedupe(warnings)),
        )

    def select(
        self,
        first_pass: ASRSegment,
        second_pass: ASRSegment,
        *,
        language: str | None,
        glossary_terms: Iterable[str] = (),
    ) -> CandidateSelection:
        first_score = self.score(first_pass, language=language)
        second_score = self.score(second_pass, language=language)
        glossary_penalty = _glossary_preservation_penalty(
            first_pass.text,
            second_pass.text,
            glossary_terms,
        )
        adjusted_second = max(0.0, second_score.score - glossary_penalty)
        difference = round(adjusted_second - first_score.score, 3)
        if not second_pass.text.strip():
            selected_pass = "first"
            reason = "second pass was empty"
        elif difference >= self._min_improvement:
            selected_pass = "second"
            reason = f"second pass exceeded the minimum candidate-score improvement ({self._min_improvement:g})"
        else:
            selected_pass = "first"
            reason = f"second pass improvement was below the required minimum ({self._min_improvement:g})"
        return CandidateSelection(
            selected_pass=selected_pass,
            first_pass=first_score,
            second_pass=CandidateScore(
                score=round(adjusted_second, 3),
                components=dict(second_score.components),
                warnings=second_score.warnings,
            ),
            score_difference=difference,
            selection_reason=reason,
            glossary_preservation_penalty=round(glossary_penalty, 3),
        )

    def _duration_text_score(self, text: str, duration: float) -> tuple[float, list[str]]:
        if not text:
            return 0.0, ["empty text"]
        if duration <= 0.0:
            return 0.0, ["non-positive duration"]
        tokens = _WORD_RE.findall(text)
        words_per_second = len(tokens) / duration
        warnings: list[str] = []
        score = 92.0
        if len(text) < self._min_text_length:
            score = min(score, 35.0)
            warnings.append("nearly empty text")
        if words_per_second < self._min_words_per_second:
            score = min(score, 40.0)
            warnings.append("abnormally low words per second")
        if words_per_second > self._max_words_per_second:
            score = min(score, 35.0)
            warnings.append("abnormally high words per second")
        return score, warnings


def mean_word_probability(candidate: ASRSegment) -> float | None:
    values = [word.probability for word in candidate.words if word.probability is not None]
    if not values:
        value = candidate.metadata.get("word_confidence")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    return sum(float(value) for value in values) / len(values)


def _logprob_score(value: float | None) -> float:
    if value is None:
        return 60.0
    return _clamp((math.exp(float(value)) * 100.0), 0.0, 100.0)


def _probability_score(word_probability: float | None, fallback: float | None) -> float:
    value = word_probability if word_probability is not None else fallback
    return 60.0 if value is None else _clamp(float(value) * 100.0, 0.0, 100.0)


def _no_speech_score(value: float | None) -> float:
    return 70.0 if value is None else _clamp((1.0 - float(value)) * 100.0, 0.0, 100.0)


def _compression_score(value: float | None) -> float:
    if value is None:
        return 70.0
    if value <= 2.0:
        return 100.0
    return _clamp(100.0 - ((float(value) - 2.0) * 45.0), 0.0, 100.0)


def _repetition_ratio(text: str) -> float:
    tokens = [token.casefold() for token in _WORD_RE.findall(text)]
    if len(tokens) < 4:
        return 0.0
    bigrams = list(zip(tokens, tokens[1:]))
    if not bigrams:
        return 0.0
    return 1.0 - (len(set(bigrams)) / len(bigrams))


def _timestamps_valid(candidate: ASRSegment) -> bool:
    if candidate.end <= candidate.start or candidate.start < 0.0:
        return False
    for word in candidate.words:
        if word.start is None or word.end is None:
            continue
        if word.end <= word.start:
            return False
        if word.start < candidate.start - 0.05 or word.end > candidate.end + 0.05:
            return False
    return True


def _glossary_preservation_penalty(first_text: str, second_text: str, terms: Iterable[str]) -> float:
    first_folded = first_text.casefold()
    second_folded = second_text.casefold()
    lost = [term for term in terms if term.casefold() in first_folded and term.casefold() not in second_folded]
    return min(12.0, len(lost) * 3.0)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _dedupe(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))
