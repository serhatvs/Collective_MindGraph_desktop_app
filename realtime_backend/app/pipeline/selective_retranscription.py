"""Trigger evaluation and bounded audio-region planning for selective ASR recovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any

from ..models import ASRSegment
from ..utils.audio import extract_wav_region
from .asr import resolve_asr_quality_profile
from .transcription_candidate_selector import TranscriptionCandidateSelector
from .transcription_glossary import ResolvedGlossary


@dataclass(frozen=True, slots=True)
class SegmentRetranscriptionTrigger:
    segment_index: int
    reasons: tuple[str, ...]
    first_pass_score: float

    def to_metadata(self) -> dict[str, object]:
        return {
            "segment_index": self.segment_index,
            "reasons": list(self.reasons),
            "first_pass_score": self.first_pass_score,
        }


@dataclass(frozen=True, slots=True)
class RetranscriptionRegion:
    start: float
    end: float
    segment_indices: tuple[int, ...]
    trigger_reasons: tuple[str, ...]

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_metadata(self) -> dict[str, object]:
        return {
            "start": self.start,
            "end": self.end,
            "duration": self.duration,
            "segment_indices": list(self.segment_indices),
            "trigger_reasons": list(self.trigger_reasons),
        }


class SelectiveRetranscriptionEngine:
    """Execute bounded second-pass ASR while preserving first-pass candidates."""

    def __init__(
        self,
        *,
        settings: Any,
        asr_provider: Any,
        selector: TranscriptionCandidateSelector,
        glossary: ResolvedGlossary,
    ) -> None:
        self._settings = settings
        self._asr = asr_provider
        self._selector = selector
        self._glossary = glossary

    def run(
        self,
        *,
        window_path: Path,
        first_pass_segments: list[ASRSegment],
        language: str | None,
        audio_duration: float,
        audio_quality: dict[str, object] | None,
        absolute_offset: float,
        max_regions: int,
    ) -> tuple[list[ASRSegment], dict[str, object]]:
        recovery_profile = resolve_asr_quality_profile(
            self._settings,
            self._settings.selective_retranscription_profile,
        )
        triggers = find_retranscription_triggers(
            first_pass_segments,
            settings=self._settings,
            selector=self._selector,
            language=language,
            audio_quality=audio_quality,
        )
        regions = build_retranscription_regions(
            first_pass_segments,
            triggers,
            audio_duration=audio_duration,
            padding_seconds=self._settings.selective_retranscription_padding_seconds,
            merge_gap_seconds=self._settings.selective_retranscription_merge_gap_seconds,
            max_region_duration=self._settings.selective_retranscription_max_segment_duration,
            max_regions=max_regions,
        )
        audit: dict[str, object] = {
            "number_of_flagged_segments": len(triggers),
            "number_of_second_pass_regions": len(regions),
            "number_of_replaced_segments": 0,
            "second_pass_processing_time_seconds": 0.0,
            "retranscribed_audio_seconds": sum(region.duration for region in regions),
            "fallback_reason": None,
            "triggers": [
                {
                    **trigger.to_metadata(),
                    "segment_start": first_pass_segments[trigger.segment_index].start + absolute_offset,
                    "segment_end": first_pass_segments[trigger.segment_index].end + absolute_offset,
                }
                for trigger in triggers
            ],
            "regions": [],
        }
        if not regions:
            return list(first_pass_segments), audit

        replacements: dict[int, tuple[set[int], list[ASRSegment]]] = {}
        for region in regions:
            started = time.perf_counter()
            region_path: Path | None = None
            try:
                region_path = extract_wav_region(
                    window_path,
                    region.start,
                    region.end,
                    self._settings.temp_dir,
                )
                second_pass_segments = _call_asr_provider(
                    self._asr,
                    region_path,
                    language,
                    recovery_profile.name,
                    self._glossary,
                )
            except Exception as exc:
                fallback_reason = (
                    "selective retranscription unavailable; retained first pass: "
                    f"{type(exc).__name__}: {exc}"
                )
                audit["fallback_reason"] = fallback_reason
                audit_regions = audit["regions"]
                if isinstance(audit_regions, list):
                    audit_regions.append(
                        {
                            **_absolute_region_metadata(region, absolute_offset),
                            "selected_pass": "first",
                            "selection_reason": fallback_reason,
                            "status": "fallback",
                        }
                    )
                break
            finally:
                audit["second_pass_processing_time_seconds"] = float(
                    audit["second_pass_processing_time_seconds"]
                ) + (time.perf_counter() - started)
                if region_path is not None:
                    region_path.unlink(missing_ok=True)

            second_pass_segments = _clamp_asr_segments_to_region(
                _offset_asr_segments(second_pass_segments, region.start),
                region,
            )
            first_candidate = _combine_asr_candidates(
                [first_pass_segments[index] for index in region.segment_indices],
                fallback_start=region.start,
                fallback_end=region.end,
            )
            second_candidate = _combine_asr_candidates(
                second_pass_segments,
                fallback_start=region.start,
                fallback_end=region.end,
            )
            selection = self._selector.select(
                first_candidate,
                second_candidate,
                language=language,
                glossary_terms=self._glossary.terms,
            )
            selection_metadata = selection.to_metadata(
                first_pass_text=first_candidate.text,
                second_pass_text=second_candidate.text,
                trigger_reasons=region.trigger_reasons,
            )
            selection_metadata.update(
                {
                    "first_pass_raw_segments": [
                        first_pass_segments[index].model_dump(mode="json")
                        for index in region.segment_indices
                    ],
                    "second_pass_raw_segments": [
                        segment.model_dump(mode="json") for segment in second_pass_segments
                    ],
                    "region_start": region.start + absolute_offset,
                    "region_end": region.end + absolute_offset,
                    "second_pass_profile": recovery_profile.name,
                    "second_pass_model": recovery_profile.model_name,
                }
            )
            region_indices = set(region.segment_indices)
            if selection.selected_pass == "second" and second_pass_segments:
                selected = [_with_selective_metadata(segment, selection_metadata) for segment in second_pass_segments]
                replacements[min(region.segment_indices)] = (region_indices, selected)
                audit["number_of_replaced_segments"] = int(audit["number_of_replaced_segments"]) + len(
                    region.segment_indices
                )
            else:
                retained = [
                    _with_selective_metadata(first_pass_segments[index], selection_metadata)
                    for index in region.segment_indices
                ]
                replacements[min(region.segment_indices)] = (region_indices, retained)

            audit_regions = audit["regions"]
            if isinstance(audit_regions, list):
                audit_regions.append(
                    {
                        **_absolute_region_metadata(region, absolute_offset),
                        **selection_metadata,
                        "status": "completed",
                    }
                )

        return _apply_replacements(first_pass_segments, replacements), audit


def find_retranscription_triggers(
    segments: list[ASRSegment],
    *,
    settings: Any,
    selector: TranscriptionCandidateSelector,
    language: str | None,
    audio_quality: dict[str, object] | None,
) -> list[SegmentRetranscriptionTrigger]:
    triggers: list[SegmentRetranscriptionTrigger] = []
    min_duration = max(0.0, float(settings.selective_retranscription_min_segment_duration))
    max_duration = max(min_duration, float(settings.selective_retranscription_max_segment_duration))
    audio_score = _optional_float((audio_quality or {}).get("audio_quality_score"))
    audio_is_weak = audio_score is not None and audio_score < float(
        settings.selective_retranscription_audio_quality_threshold
    )
    low_volume = bool((audio_quality or {}).get("low_volume"))
    noisy = bool((audio_quality or {}).get("possible_noise"))

    for index, segment in enumerate(segments):
        duration = max(0.0, segment.end - segment.start)
        if duration < min_duration or duration > max_duration:
            continue
        reasons: list[str] = []
        if segment.avg_logprob is not None and segment.avg_logprob < float(
            settings.selective_retranscription_avg_logprob_threshold
        ):
            reasons.append("avg_logprob_below_threshold")
        if segment.no_speech_prob is not None and segment.no_speech_prob > float(
            settings.selective_retranscription_no_speech_threshold
        ):
            reasons.append("no_speech_probability_above_threshold")
        if segment.compression_ratio is not None and segment.compression_ratio > float(
            settings.selective_retranscription_compression_ratio_threshold
        ):
            reasons.append("compression_ratio_above_threshold")
        word_probability = _mean_word_probability(segment)
        if word_probability is not None and word_probability < float(
            settings.selective_retranscription_word_probability_threshold
        ):
            reasons.append("mean_word_probability_below_threshold")
        if len(segment.text.strip()) < int(settings.selective_retranscription_min_text_length):
            reasons.append("empty_or_nearly_empty_text")

        score = selector.score(segment, language=language)
        if score.score < float(settings.selective_retranscription_candidate_score_threshold):
            reasons.append("candidate_score_below_threshold")
        for warning in score.warnings:
            if warning == "abnormally low words per second":
                reasons.append("abnormally_low_words_per_second")
            elif warning == "abnormally high words per second":
                reasons.append("abnormally_high_words_per_second")
            elif warning == "repeated text pattern":
                reasons.append("repeated_phrase_pattern")
            elif warning == "invalid timestamp shape":
                reasons.append("invalid_timestamp_shape")

        if audio_is_weak and reasons:
            reasons.append("audio_quality_score_below_threshold")
        if low_volume and reasons:
            reasons.append("low_volume_audio")
        if noisy and reasons:
            reasons.append("noisy_or_unclear_audio")
        reasons = list(dict.fromkeys(reasons))
        if reasons:
            triggers.append(
                SegmentRetranscriptionTrigger(
                    segment_index=index,
                    reasons=tuple(reasons),
                    first_pass_score=score.score,
                )
            )
    return triggers


def build_retranscription_regions(
    segments: list[ASRSegment],
    triggers: list[SegmentRetranscriptionTrigger],
    *,
    audio_duration: float,
    padding_seconds: float,
    merge_gap_seconds: float,
    max_region_duration: float,
    max_regions: int,
) -> list[RetranscriptionRegion]:
    if not segments or not triggers or audio_duration <= 0.0 or max_regions <= 0:
        return []
    trigger_by_index = {trigger.segment_index: trigger for trigger in triggers}
    flagged_indices = set(trigger_by_index)
    padding = max(0.0, padding_seconds)
    planned: list[RetranscriptionRegion] = []

    for index in sorted(flagged_indices):
        if index < 0 or index >= len(segments):
            continue
        segment = segments[index]
        start = max(0.0, segment.start - padding)
        end = min(audio_duration, segment.end + padding)
        if index > 0 and (index - 1) not in flagged_indices:
            previous = segments[index - 1]
            start = max(start, previous.end if previous.end <= segment.start else segment.start)
        if index + 1 < len(segments) and (index + 1) not in flagged_indices:
            following = segments[index + 1]
            end = min(end, following.start if following.start >= segment.end else segment.end)
        if end <= start:
            continue
        trigger = trigger_by_index[index]
        candidate = RetranscriptionRegion(
            start=round(start, 6),
            end=round(end, 6),
            segment_indices=(index,),
            trigger_reasons=trigger.reasons,
        )
        if planned and _regions_can_merge(
            planned[-1],
            candidate,
            merge_gap_seconds=max(0.0, merge_gap_seconds),
            max_region_duration=max_region_duration,
        ):
            previous = planned[-1]
            planned[-1] = RetranscriptionRegion(
                start=previous.start,
                end=max(previous.end, candidate.end),
                segment_indices=tuple(dict.fromkeys([*previous.segment_indices, *candidate.segment_indices])),
                trigger_reasons=tuple(dict.fromkeys([*previous.trigger_reasons, *candidate.trigger_reasons])),
            )
        else:
            planned.append(candidate)

    bounded = [region for region in planned if region.duration <= max(0.0, max_region_duration)]
    return bounded[:max_regions]


def _regions_can_merge(
    left: RetranscriptionRegion,
    right: RetranscriptionRegion,
    *,
    merge_gap_seconds: float,
    max_region_duration: float,
) -> bool:
    gap = max(0.0, right.start - left.end)
    combined_duration = max(left.end, right.end) - min(left.start, right.start)
    return gap <= merge_gap_seconds and combined_duration <= max_region_duration


def _mean_word_probability(segment: ASRSegment) -> float | None:
    values = [word.probability for word in segment.words if word.probability is not None]
    if values:
        return sum(float(value) for value in values) / len(values)
    return _optional_float(segment.metadata.get("word_confidence"))


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _call_asr_provider(
    provider: Any,
    audio_path: Path,
    language: str | None,
    quality_mode: str,
    glossary: ResolvedGlossary,
) -> list[ASRSegment]:
    try:
        return provider.transcribe(
            audio_path,
            language,
            None,
            quality_mode,
            glossary=glossary,
        )
    except TypeError as exc:
        if "glossary" not in str(exc):
            raise
        return provider.transcribe(audio_path, language, None, quality_mode)


def _offset_asr_segments(items: list[ASRSegment], offset_seconds: float) -> list[ASRSegment]:
    if not offset_seconds:
        return list(items)
    return [
        item.model_copy(
            update={
                "start": item.start + offset_seconds,
                "end": item.end + offset_seconds,
                "words": [
                    word.model_copy(
                        update={
                            "start": (word.start + offset_seconds) if word.start is not None else None,
                            "end": (word.end + offset_seconds) if word.end is not None else None,
                        }
                    )
                    for word in item.words
                ],
            },
            deep=True,
        )
        for item in items
    ]


def _combine_asr_candidates(
    items: list[ASRSegment],
    *,
    fallback_start: float,
    fallback_end: float,
) -> ASRSegment:
    if not items:
        return ASRSegment(
            start=fallback_start,
            end=max(fallback_start + 0.01, fallback_end),
            text="",
            text_length=0,
        )
    words = [word for item in items for word in item.words]
    text = " ".join(item.text.strip() for item in items if item.text.strip()).strip()
    return ASRSegment(
        start=min(item.start for item in items),
        end=max(item.end for item in items),
        text=text,
        confidence=_mean_optional(item.confidence for item in items),
        words=words,
        avg_logprob=_mean_optional(item.avg_logprob for item in items),
        no_speech_prob=_mean_optional(item.no_speech_prob for item in items),
        compression_ratio=max(
            (float(item.compression_ratio) for item in items if item.compression_ratio is not None),
            default=None,
        ),
        text_length=len(text),
        metadata={
            "word_confidence": _mean_optional(
                word.probability for word in words if word.probability is not None
            ),
            "combined_candidate_segment_count": len(items),
        },
    )


def _mean_optional(values) -> float | None:
    items = [float(value) for value in values if value is not None]
    if not items:
        return None
    return sum(items) / len(items)


def _with_selective_metadata(segment: ASRSegment, selection_metadata: dict[str, object]) -> ASRSegment:
    metadata = dict(segment.metadata)
    metadata["selective_retranscription"] = dict(selection_metadata)
    metadata["selected_raw_transcript"] = segment.text
    return segment.model_copy(update={"metadata": metadata}, deep=True)


def _absolute_region_metadata(region: RetranscriptionRegion, absolute_offset: float) -> dict[str, object]:
    metadata = region.to_metadata()
    metadata["start"] = region.start + absolute_offset
    metadata["end"] = region.end + absolute_offset
    return metadata


def _clamp_asr_segments_to_region(
    segments: list[ASRSegment],
    region: RetranscriptionRegion,
) -> list[ASRSegment]:
    clamped: list[ASRSegment] = []
    for segment in segments:
        start = max(region.start, min(region.end, segment.start))
        end = max(start, min(region.end, segment.end))
        if end <= start:
            continue
        words = []
        for word in segment.words:
            if word.start is None or word.end is None:
                words.append(word)
                continue
            word_start = max(start, min(end, word.start))
            word_end = max(word_start, min(end, word.end))
            if word_end <= word_start:
                continue
            words.append(word.model_copy(update={"start": word_start, "end": word_end}))
        clamped.append(
            segment.model_copy(
                update={"start": start, "end": end, "words": words},
                deep=True,
            )
        )
    return clamped


def _apply_replacements(
    first_pass_segments: list[ASRSegment],
    replacements: dict[int, tuple[set[int], list[ASRSegment]]],
) -> list[ASRSegment]:
    selected_segments: list[ASRSegment] = []
    skipped_indices: set[int] = set()
    for index, segment in enumerate(first_pass_segments):
        if index in skipped_indices:
            continue
        replacement = replacements.get(index)
        if replacement is None:
            selected_segments.append(segment)
            continue
        region_indices, items = replacement
        selected_segments.extend(items)
        skipped_indices.update(region_indices)
    return selected_segments
