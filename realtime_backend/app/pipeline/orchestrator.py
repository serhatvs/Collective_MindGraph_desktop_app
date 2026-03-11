"""Pipeline orchestration from normalized audio to structured transcript."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

from ..config import Settings
from ..models import ASRSegment, ConversationTranscript, DiarizationTurn, ProcessingDebug, SpeechRegion, TranscriptSegment
from ..services.summary import ConversationSummaryService
from ..utils.audio import extract_wav_region, wav_duration_seconds
from ..utils.ids import new_conversation_id
from .alignment import merge_transcript_segments
from .asr import BaseASR, build_asr
from .diarization import BaseDiarizer, build_diarizer
from .llm_postprocess import LLMPostProcessor, build_llm_postprocessor
from .speaker_mapper import StableSpeakerMapper

if TYPE_CHECKING:
    from .vad import BaseVAD

_TimelineItem = TypeVar("_TimelineItem", ASRSegment, DiarizationTurn, TranscriptSegment)


class TranscriptionPipeline:
    def __init__(
        self,
        settings: Settings,
        vad: BaseVAD | None = None,
        asr: BaseASR | None = None,
        diarizer: BaseDiarizer | None = None,
        llm_postprocessor: LLMPostProcessor | None = None,
        summary_service: ConversationSummaryService | None = None,
    ) -> None:
        self._settings = settings
        if vad is None:
            from .vad import build_vad

            self._vad = build_vad(settings)
        else:
            self._vad = vad
        self._asr = asr or build_asr(settings)
        self._diarizer = diarizer or build_diarizer(settings)
        self._llm_postprocessor = llm_postprocessor or build_llm_postprocessor(settings)
        self._summary_service = summary_service or ConversationSummaryService()

    async def process_audio_path(
        self,
        audio_path: Path,
        *,
        conversation_id: str | None = None,
        source: str,
        language: str | None = None,
        prior_segments: list[TranscriptSegment] | None = None,
        speaker_mapper: StableSpeakerMapper | None = None,
        chunk_offset: float = 0.0,
        include_summary: bool = True,
        debug: bool = True,
    ) -> ConversationTranscript:
        resolved_conversation_id = conversation_id or new_conversation_id()
        prior = list(prior_segments or [])
        mapper = speaker_mapper or StableSpeakerMapper()

        total_duration = await asyncio.to_thread(wav_duration_seconds, audio_path)
        vad_regions = await asyncio.to_thread(self._vad.detect, audio_path)
        processing_windows = _build_processing_windows(
            total_duration=total_duration,
            regions=vad_regions,
            max_window_seconds=self._settings.pipeline_max_window_seconds,
            overlap_seconds=self._settings.pipeline_window_overlap_seconds,
        )
        asr_segments: list[ASRSegment] = []
        diarization_turns: list[DiarizationTurn] = []
        merged_segments: list[TranscriptSegment] = []

        for window in processing_windows:
            local_regions = _clip_regions_to_window(vad_regions, window.start, window.end)
            window_path = audio_path
            cleanup_path = False
            if not _is_full_audio_window(window, total_duration):
                window_path = await asyncio.to_thread(
                    extract_wav_region,
                    audio_path,
                    window.start,
                    window.end,
                    self._settings.temp_dir,
                )
                cleanup_path = True

            try:
                window_asr_segments = await asyncio.to_thread(
                    self._asr.transcribe,
                    window_path,
                    language,
                    local_regions or None,
                )
                window_diarization_turns = await asyncio.to_thread(
                    self._diarizer.diarize,
                    window_path,
                    local_regions or None,
                )
            finally:
                if cleanup_path:
                    window_path.unlink(missing_ok=True)

            absolute_offset = chunk_offset + window.start
            merged_window_segments = merge_transcript_segments(
                asr_segments=window_asr_segments,
                diarization_turns=window_diarization_turns,
                speaker_mapper=mapper,
                prior_segments=prior + merged_segments,
                chunk_offset=absolute_offset,
            )
            merged_segments = _replace_timeline_tail(merged_segments, merged_window_segments, absolute_offset)
            asr_segments = _replace_timeline_tail(
                asr_segments,
                _offset_asr_segments(window_asr_segments, absolute_offset),
                absolute_offset,
            )
            diarization_turns = _replace_timeline_tail(
                diarization_turns,
                _offset_diarization_turns(window_diarization_turns, absolute_offset),
                absolute_offset,
            )

        corrected_segments = await self._llm_postprocessor.apply(
            conversation_id=resolved_conversation_id,
            language=language or self._settings.default_language,
            segments=merged_segments,
        )

        transcript = ConversationTranscript(
            conversation_id=resolved_conversation_id,
            source=source,
            language=language or self._settings.default_language,
            segments=corrected_segments,
            debug=ProcessingDebug(
                vad_regions=vad_regions,
                diarization_turns=diarization_turns,
                asr_segments=asr_segments,
            )
            if debug
            else None,
        )

        if include_summary and self._settings.enable_summary:
            summary, topics, action_items, decisions = self._summary_service.build_summary(transcript)
            transcript.summary = summary
            transcript.topics = topics
            transcript.action_items = action_items
            transcript.decisions = decisions
        transcript.updated_at = datetime.now(tz=UTC)
        return transcript


def _build_processing_windows(
    total_duration: float,
    regions: list[SpeechRegion],
    max_window_seconds: float,
    overlap_seconds: float,
) -> list[SpeechRegion]:
    if total_duration <= 0:
        return []

    safe_max_window = max(max_window_seconds, 1.0)
    safe_overlap = max(overlap_seconds, 0.0)
    if total_duration <= safe_max_window:
        return [SpeechRegion(start=0.0, end=total_duration)]

    if not regions:
        return _split_full_duration(total_duration, safe_max_window, safe_overlap)

    windows: list[SpeechRegion] = []
    current_start = max(0.0, regions[0].start - safe_overlap)
    current_end = min(total_duration, regions[0].end + safe_overlap)

    for region in regions[1:]:
        proposed_end = min(total_duration, region.end + safe_overlap)
        if proposed_end - current_start <= safe_max_window:
            current_end = max(current_end, proposed_end)
            continue
        windows.append(SpeechRegion(start=current_start, end=current_end))
        current_start = max(0.0, region.start - safe_overlap)
        current_end = proposed_end

    windows.append(SpeechRegion(start=current_start, end=current_end))
    return windows


def _split_full_duration(
    total_duration: float,
    max_window_seconds: float,
    overlap_seconds: float,
) -> list[SpeechRegion]:
    windows: list[SpeechRegion] = []
    step_seconds = max(max_window_seconds - overlap_seconds, 1.0)
    start = 0.0
    while start < total_duration:
        end = min(total_duration, start + max_window_seconds)
        windows.append(SpeechRegion(start=start, end=end))
        if end >= total_duration:
            break
        start = max(0.0, end - overlap_seconds)
    return windows


def _clip_regions_to_window(
    regions: list[SpeechRegion],
    window_start: float,
    window_end: float,
) -> list[SpeechRegion]:
    clipped: list[SpeechRegion] = []
    for region in regions:
        overlap_start = max(region.start, window_start)
        overlap_end = min(region.end, window_end)
        if overlap_end <= overlap_start:
            continue
        clipped.append(
            SpeechRegion(
                start=overlap_start - window_start,
                end=overlap_end - window_start,
                confidence=region.confidence,
            )
        )
    return clipped


def _replace_timeline_tail(
    existing: list[_TimelineItem],
    incoming: list[_TimelineItem],
    from_second: float,
) -> list[_TimelineItem]:
    preserved = [item for item in existing if item.end <= from_second]
    return preserved + incoming


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
            }
        )
        for item in items
    ]


def _offset_diarization_turns(items: list[DiarizationTurn], offset_seconds: float) -> list[DiarizationTurn]:
    if not offset_seconds:
        return list(items)
    return [
        item.model_copy(
            update={
                "start": item.start + offset_seconds,
                "end": item.end + offset_seconds,
            }
        )
        for item in items
    ]


def _is_full_audio_window(window: SpeechRegion, total_duration: float) -> bool:
    return window.start <= 0.0 and window.end >= total_duration
