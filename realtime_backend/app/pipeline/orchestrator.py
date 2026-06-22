"""Pipeline orchestration from normalized audio to structured transcript."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

from ..config import Settings
from ..models import (
    ASRSegment,
    ConversationTranscript,
    DiarizationTurn,
    ProcessingDebug,
    SpeechRegion,
    TranscriptSegment,
    TranscriptionDiagnostics,
)
from ..services.summary import ConversationSummaryService
from ..utils.audio import extract_wav_region, wav_duration_seconds
from ..utils.audio_process import inspect_audio, normalize_audio
from ..utils.ids import new_conversation_id
from ..utils.turkish_cleanup import clean_turkish_transcript
from .alignment import merge_transcript_segments
from .asr import ASR_STATUS_MOCK_FALLBACK, ASR_STATUS_OK, BaseASR, build_asr, resolve_asr_quality_profile
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
        settings.ensure_directories()
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
        quality_mode: str | None = None,
        prior_segments: list[TranscriptSegment] | None = None,
        speaker_mapper: StableSpeakerMapper | None = None,
        chunk_offset: float = 0.0,
        include_summary: bool = True,
        debug: bool = True,
    ) -> ConversationTranscript:
        start_process = datetime.now(tz=UTC)
        resolved_conversation_id = conversation_id or new_conversation_id()
        resolved_language = language or self._settings.default_language
        resolved_profile = resolve_asr_quality_profile(self._settings, quality_mode)
        resolved_quality = resolved_profile.name
        prior = list(prior_segments or [])
        mapper = speaker_mapper or StableSpeakerMapper()
        warnings: list[str] = []

        # 1. Audio Preprocessing
        input_inspection = await asyncio.to_thread(inspect_audio, audio_path)
        normalized_path = self._settings.temp_dir / f"{resolved_conversation_id}_pipeline_norm.wav"
        normalize_success = await asyncio.to_thread(
            normalize_audio,
            audio_path,
            normalized_path,
            self._settings.sample_rate
        )
        working_path = normalized_path if normalize_success else audio_path
        preprocessing_status = "ffmpeg_normalized" if normalize_success else "ffmpeg_failed_original_used"
        if not normalize_success:
            warnings.append("ffmpeg normalization failed; original file used for transcription.")

        try:
            output_inspection = await asyncio.to_thread(inspect_audio, working_path)
            if output_inspection is None:
                warnings.append("Audio inspection unavailable for the file passed to VAD/ASR.")

            total_duration = await asyncio.to_thread(wav_duration_seconds, working_path)
            vad_regions = await asyncio.to_thread(self._vad.detect, working_path)
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
                window_path = working_path
                cleanup_window = False
                if not _is_full_audio_window(window, total_duration):
                    window_path = await asyncio.to_thread(
                        extract_wav_region,
                        working_path,
                        window.start,
                        window.end,
                        self._settings.temp_dir,
                    )
                    cleanup_window = True

                try:
                    window_asr_segments = await asyncio.to_thread(
                        self._asr.transcribe,
                        window_path,
                        resolved_language,
                        local_regions or None,
                        resolved_profile.name,
                    )
                    window_diarization_turns = await asyncio.to_thread(
                        self._diarizer.diarize,
                        window_path,
                        local_regions or None,
                    )
                finally:
                    if cleanup_window:
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

            # 2. LLM Cleanup
            corrected_segments = await self._llm_postprocessor.apply(
                conversation_id=resolved_conversation_id,
                language=resolved_language,
                segments=merged_segments,
            )

            # 3. Deterministic Turkish cleanup
            if resolved_language == "tr":
                for segment in corrected_segments:
                    segment.corrected_text = clean_turkish_transcript(
                        segment.corrected_text,
                        mode=self._settings.transcript_cleanup_mode,
                    )

            end_process = datetime.now(tz=UTC)
            processing_time_seconds = (end_process - start_process).total_seconds()
            raw_asr_status = getattr(self._asr, "asr_status", ASR_STATUS_OK)
            asr_status = raw_asr_status if isinstance(raw_asr_status, str) else ASR_STATUS_OK
            raw_mock_fallback = getattr(self._asr, "mock_fallback_used", False)
            mock_fallback_used = raw_mock_fallback if isinstance(raw_mock_fallback, bool) else False
            raw_fallback_reason = getattr(self._asr, "fallback_reason", None)
            fallback_reason = raw_fallback_reason if isinstance(raw_fallback_reason, str) else None
            if mock_fallback_used:
                warnings.append(f"{ASR_STATUS_MOCK_FALLBACK}: Mock ASR fallback used; transcript is not real ASR output.")
                for segment in corrected_segments:
                    if ASR_STATUS_MOCK_FALLBACK not in segment.notes:
                        segment.notes.append(ASR_STATUS_MOCK_FALLBACK)
                    segment.metadata["mock_fallback_used"] = True
                    segment.metadata["asr_status"] = ASR_STATUS_MOCK_FALLBACK
            elif asr_status != ASR_STATUS_OK:
                warnings.append(f"{asr_status}: Mock ASR used; transcript is not real ASR output.")
                for segment in corrected_segments:
                    if asr_status not in segment.notes:
                        segment.notes.append(asr_status)
                    segment.metadata["asr_status"] = asr_status

            metadata = {
                "asr_provider": self._asr.provider_name,
                "asr_status": asr_status,
                "ASR_STATUS": asr_status.removeprefix("ASR_STATUS="),
                "model_name": self._settings.asr_model_name,
                "quality_profile": resolved_profile.name,
                "language": resolved_language,
                "beam_size": resolved_profile.beam_size,
                "compute_type": self._settings.asr_compute_type,
                "word_timestamps": resolved_profile.word_timestamps,
                "internal_faster_whisper_vad": resolved_profile.vad_filter,
                "condition_on_previous_text": resolved_profile.condition_on_previous_text,
                "vad_provider": getattr(self._vad, "provider_name", self._settings.vad_provider),
                "preprocessing_status": preprocessing_status,
                "ffmpeg_normalization_succeeded": normalize_success,
                "input_audio": _audio_inspection_metadata(input_inspection),
                "asr_input_audio": _audio_inspection_metadata(output_inspection),
                "processing_time_seconds": processing_time_seconds,
                "mock_fallback_used": mock_fallback_used,
                "transcript_cleanup_mode": self._settings.transcript_cleanup_mode,
                "raw_asr_text_preserved": True,
                "warnings": warnings,
            }
            if fallback_reason:
                metadata["asr_fallback_reason"] = fallback_reason
            
            diagnostics = TranscriptionDiagnostics(
                provider=self._asr.provider_name,
                model=self._settings.asr_model_name,
                asr_status=asr_status,
                mock_fallback_used=mock_fallback_used,
                language=resolved_language,
                quality_mode=resolved_quality,
                quality_profile=resolved_profile.name,
                beam_size=resolved_profile.beam_size,
                compute_type=self._settings.asr_compute_type,
                word_timestamps_enabled=resolved_profile.word_timestamps,
                internal_vad_enabled=resolved_profile.vad_filter,
                condition_on_previous_text=resolved_profile.condition_on_previous_text,
                preprocessing_status=preprocessing_status,
                preprocessing_format=output_inspection.format if output_inspection else None,
                audio_duration=total_duration,
                sample_rate_in=input_inspection.sample_rate if input_inspection else None,
                sample_rate_out=output_inspection.sample_rate if output_inspection else None,
                channels_in=input_inspection.channels if input_inspection else None,
                channels_out=output_inspection.channels if output_inspection else None,
                vad_settings={
                    "provider": getattr(self._vad, "provider_name", self._settings.vad_provider),
                    "frame_ms": self._settings.vad_frame_ms,
                    "min_speech_ms": self._settings.vad_min_speech_ms,
                    "min_silence_ms": self._settings.vad_min_silence_ms,
                    "padding_ms": self._settings.vad_padding_ms,
                    "merge_gap_ms": self._settings.vad_merge_gap_ms,
                    "max_region_seconds": self._settings.vad_max_region_seconds,
                    "target_region_seconds": self._settings.vad_target_region_seconds,
                },
                chunk_count=len(processing_windows),
                processing_time_seconds=processing_time_seconds,
                raw_transcript_length=sum(len(s.raw_text) for s in corrected_segments),
                cleaned_transcript_length=sum(len(s.corrected_text) for s in corrected_segments),
                warnings=warnings,
            )

            transcript = ConversationTranscript(
                conversation_id=resolved_conversation_id,
                source=source,
                language=resolved_language,
                quality_mode=resolved_quality,
                segments=corrected_segments,
                metadata=metadata,
                diagnostics=diagnostics,
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
        finally:
            if normalize_success:
                normalized_path.unlink(missing_ok=True)


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


def _audio_inspection_metadata(inspection: object | None) -> dict[str, object] | None:
    if inspection is None:
        return None
    return {
        "sample_rate": getattr(inspection, "sample_rate", None),
        "channels": getattr(inspection, "channels", None),
        "sample_width_bytes": getattr(inspection, "sample_width_bytes", None),
        "frame_count": getattr(inspection, "frame_count", None),
        "duration_seconds": getattr(inspection, "duration_seconds", None),
        "format": getattr(inspection, "format", None),
    }
