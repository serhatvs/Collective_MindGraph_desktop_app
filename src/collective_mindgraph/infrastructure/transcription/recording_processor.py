"""Pipeline orchestration from normalized audio to structured transcript."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from collective_mindgraph.application.ports import TranscriptionConfiguration
from collective_mindgraph.application.transcription.contracts import (
    ASRSegment,
    ConversationTranscript,
    DiarizationTurn,
    TranscriptSegment,
)
from collective_mindgraph.application.transcription.conversation_ids import (
    new_conversation_id,
    validate_conversation_id,
)
from collective_mindgraph.application.transcription.extract_insights import (
    ExtractTranscriptInsights,
)
from collective_mindgraph.application.transcription.processing_port import (
    ProcessingRuntimeSnapshot,
)
from collective_mindgraph.application.transcription.speaker_mapper import (
    StableSpeakerMapper,
)
from collective_mindgraph.application.transcription.transcription_glossary import (
    resolve_transcription_glossary,
)
from collective_mindgraph.application.transcription.turkish_cleanup import clean_turkish_transcript
from collective_mindgraph.infrastructure.audio.ffmpeg_processing import (
    analyze_audio_quality,
    inspect_audio,
    normalize_audio,
    preprocessing_steps,
)
from collective_mindgraph.infrastructure.audio.wav_files import (
    create_temporary_wav_path,
    wav_duration_seconds,
)

from .alignment import merge_transcript_segments
from .asr import (
    BaseASR,
    build_asr,
    offset_asr_segments,
    resolve_asr_quality_profile,
    transcribe_with_glossary_compatibility,
)
from .asr_runtime_config import build_asr_diagnostics
from .diarization import BaseDiarizer, build_diarizer
from .llm_postprocess import LLMPostProcessor, build_llm_postprocessor
from .recording_processing_helpers import (
    build_processing_windows as _build_processing_windows,
)
from .recording_processing_helpers import (
    clip_regions_to_window as _clip_regions_to_window,
)
from .recording_processing_helpers import (
    extract_wav_region_owned as _extract_wav_region_owned,
)
from .recording_processing_helpers import (
    initial_selective_metadata as _initial_selective_metadata,
)
from .recording_processing_helpers import (
    is_full_audio_window as _is_full_audio_window,
)
from .recording_processing_helpers import (
    merge_selective_metadata as _merge_selective_metadata,
)
from .recording_processing_helpers import (
    offset_diarization_turns as _offset_diarization_turns,
)
from .recording_processing_helpers import (
    replace_timeline_tail as _replace_timeline_tail,
)
from .recording_processing_helpers import report_progress as _report_progress
from .recording_processing_helpers import (
    to_thread_cancellation_safe as _to_thread_cancellation_safe,
)
from .selective_retranscription import SelectiveRetranscriptionEngine
from .transcription_candidate_selector import TranscriptionCandidateSelector
from .transcription_result_builder import build_transcription_result

if TYPE_CHECKING:
    from .vad import BaseVAD


class RecordingProcessor:
    def __init__(
        self,
        settings: TranscriptionConfiguration,
        vad: BaseVAD | None = None,
        asr: BaseASR | None = None,
        diarizer: BaseDiarizer | None = None,
        llm_postprocessor: LLMPostProcessor | None = None,
        summary_service: ExtractTranscriptInsights | None = None,
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
        self._summary_service = summary_service or ExtractTranscriptInsights()

    def runtime_status(self) -> ProcessingRuntimeSnapshot:
        diagnostics = build_asr_diagnostics(self._settings, self._asr)
        diagnostics["LLM provider resolved"] = self._llm_postprocessor.provider_name
        return ProcessingRuntimeSnapshot(
            vad_provider=getattr(self._vad, "provider_name", None),
            asr_provider_resolved=getattr(self._asr, "provider_name", None),
            asr_fallback_provider=getattr(self._asr, "fallback_provider_name", None),
            asr_status=getattr(self._asr, "asr_status", None),
            asr_mock_fallback_used=bool(getattr(self._asr, "mock_fallback_used", False)),
            cuda_available_through_torch=diagnostics["CUDA available through torch"],
            gpu_requested=bool(getattr(self._asr, "gpu_requested", False)),
            gpu_loaded=bool(getattr(self._asr, "gpu_loaded", False)),
            faster_whisper_cuda_load_status=getattr(self._asr, "cuda_load_status", None),
            gpu_fallback_happened=bool(getattr(self._asr, "gpu_fallback_happened", False)),
            gpu_fallback_reason=getattr(self._asr, "gpu_fallback_reason", None),
            local_llm_enabled=bool(diagnostics["Local LLM enabled"]),
            llm_provider_resolved=self._llm_postprocessor.provider_name,
            llm_fallback_provider=self._llm_postprocessor.fallback_provider_name,
            _diagnostic_items=tuple(diagnostics.items()),
        )

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
        session_glossary_terms: list[str] | None = None,
        user_hotwords: list[str] | None = None,
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> ConversationTranscript:
        _report_progress(progress_callback, "preparing", 5)
        start_process = datetime.now(tz=UTC)
        resolved_conversation_id = (
            validate_conversation_id(conversation_id) if conversation_id else new_conversation_id()
        )
        resolved_language = language or self._settings.default_language
        resolved_profile = resolve_asr_quality_profile(self._settings, quality_mode)
        resolved_quality = resolved_profile.name
        prior = list(prior_segments or [])
        mapper = speaker_mapper or StableSpeakerMapper()
        warnings: list[str] = []
        resolved_glossary = resolve_transcription_glossary(
            self._settings,
            session_terms=session_glossary_terms,
            user_hotwords=user_hotwords,
        )
        selector = TranscriptionCandidateSelector(
            min_improvement=self._settings.selective_retranscription_min_improvement,
            min_words_per_second=self._settings.selective_retranscription_min_words_per_second,
            max_words_per_second=self._settings.selective_retranscription_max_words_per_second,
            min_text_length=self._settings.selective_retranscription_min_text_length,
        )
        selective_engine = SelectiveRetranscriptionEngine(
            settings=self._settings,
            asr_provider=self._asr,
            selector=selector,
            glossary=resolved_glossary,
        )
        selective_metadata = _initial_selective_metadata(self._settings)

        # 1. Audio Preprocessing
        _report_progress(progress_callback, "normalize", 15)
        input_inspection = await _to_thread_cancellation_safe(inspect_audio, audio_path)
        normalized_path = create_temporary_wav_path(
            self._settings.temp_dir,
            prefix="pipeline_norm_",
        )
        trim_silence = (
            resolved_profile.name == "bad_mic_recovery" and self._settings.asr_safe_silence_trim
        )
        noise_reduction = (
            resolved_profile.name == "bad_mic_recovery"
            and self._settings.asr_bad_mic_noise_reduction
        )
        preprocessing_step_names = preprocessing_steps(
            resolved_profile.preprocessing_strength,
            trim_silence=trim_silence,
            noise_reduction=noise_reduction,
        )
        try:
            normalize_success = await _to_thread_cancellation_safe(
                normalize_audio,
                audio_path,
                normalized_path,
                self._settings.sample_rate,
                resolved_profile.preprocessing_strength,
                trim_silence=trim_silence,
                noise_reduction=noise_reduction,
            )
        except BaseException:
            normalized_path.unlink(missing_ok=True)
            raise
        working_path = normalized_path if normalize_success else audio_path
        preprocessing_status = (
            f"ffmpeg_{resolved_profile.preprocessing_strength}"
            if normalize_success
            else "ffmpeg_failed_original_used"
        )
        if not normalize_success:
            warnings.append("ffmpeg normalization failed; original file used for transcription.")

        try:
            output_inspection = await _to_thread_cancellation_safe(inspect_audio, working_path)
            if output_inspection is None:
                warnings.append("Audio inspection unavailable for the file passed to VAD/ASR.")
            audio_quality_analysis = await _to_thread_cancellation_safe(
                analyze_audio_quality,
                working_path,
                preprocessing_applied=normalize_success,
                preprocessing_strength=resolved_profile.preprocessing_strength,
                preprocessing_steps=preprocessing_step_names,
            )
            audio_quality_metadata = (
                audio_quality_analysis.to_metadata() if audio_quality_analysis else None
            )
            if audio_quality_metadata is None:
                warnings.append(
                    "Audio quality analysis unavailable; confidence estimate is less complete."
                )
            else:
                warnings.extend(
                    str(item) for item in audio_quality_metadata.get("warnings", []) if item
                )

            total_duration = await _to_thread_cancellation_safe(wav_duration_seconds, working_path)
            _report_progress(progress_callback, "vad", 25)
            vad_regions = await _to_thread_cancellation_safe(self._vad.detect, working_path)
            processing_windows = _build_processing_windows(
                total_duration=total_duration,
                regions=vad_regions,
                max_window_seconds=self._settings.pipeline_max_window_seconds,
                overlap_seconds=self._settings.pipeline_window_overlap_seconds,
            )
            asr_segments: list[ASRSegment] = []
            first_pass_segments: list[ASRSegment] = []
            diarization_turns: list[DiarizationTurn] = []
            merged_segments: list[TranscriptSegment] = []

            _report_progress(progress_callback, "asr", 40)
            for window in processing_windows:
                local_regions = _clip_regions_to_window(vad_regions, window.start, window.end)
                window_path = working_path
                cleanup_window = False
                if not _is_full_audio_window(window, total_duration):
                    window_path = await _extract_wav_region_owned(
                        working_path,
                        window.start,
                        window.end,
                        self._settings.temp_dir,
                    )
                    cleanup_window = True

                try:
                    first_pass_started = time.perf_counter()
                    window_asr_segments = await _to_thread_cancellation_safe(
                        transcribe_with_glossary_compatibility,
                        self._asr,
                        window_path,
                        resolved_language,
                        local_regions or None,
                        resolved_profile.name,
                        resolved_glossary,
                    )
                    selective_metadata["first_pass_processing_time_seconds"] += (
                        time.perf_counter() - first_pass_started
                    )
                    absolute_offset = chunk_offset + window.start
                    absolute_first_pass = offset_asr_segments(window_asr_segments, absolute_offset)
                    first_pass_segments = _replace_timeline_tail(
                        first_pass_segments,
                        absolute_first_pass,
                        absolute_offset,
                    )
                    selective_metadata["number_of_first_pass_segments"] = len(first_pass_segments)

                    if (
                        self._settings.selective_retranscription_enabled
                        and window_asr_segments
                        and not selective_metadata.get("fallback_reason")
                        and int(selective_metadata["number_of_second_pass_regions"])
                        < self._settings.selective_retranscription_max_regions
                    ):
                        remaining_selective_regions = max(
                            0,
                            self._settings.selective_retranscription_max_regions
                            - int(selective_metadata["number_of_second_pass_regions"]),
                        )
                        (
                            window_asr_segments,
                            window_selective_metadata,
                        ) = await _to_thread_cancellation_safe(
                            selective_engine.run,
                            window_path=window_path,
                            first_pass_segments=window_asr_segments,
                            language=resolved_language,
                            audio_duration=max(0.0, window.end - window.start),
                            audio_quality=audio_quality_metadata,
                            absolute_offset=absolute_offset,
                            max_regions=remaining_selective_regions,
                        )
                        _merge_selective_metadata(selective_metadata, window_selective_metadata)
                    window_diarization_turns = await _to_thread_cancellation_safe(
                        self._diarizer.diarize,
                        window_path,
                        local_regions or None,
                    )
                finally:
                    if cleanup_window:
                        window_path.unlink(missing_ok=True)

                _report_progress(progress_callback, "alignment", 70)
                merged_window_segments = merge_transcript_segments(
                    asr_segments=window_asr_segments,
                    diarization_turns=window_diarization_turns,
                    speaker_mapper=mapper,
                    prior_segments=prior + merged_segments,
                    chunk_offset=absolute_offset,
                )
                merged_segments = _replace_timeline_tail(
                    merged_segments, merged_window_segments, absolute_offset
                )
                asr_segments = _replace_timeline_tail(
                    asr_segments,
                    offset_asr_segments(window_asr_segments, absolute_offset),
                    absolute_offset,
                )
                diarization_turns = _replace_timeline_tail(
                    diarization_turns,
                    _offset_diarization_turns(window_diarization_turns, absolute_offset),
                    absolute_offset,
                )

            selective_metadata["number_of_first_pass_segments"] = len(first_pass_segments)
            for count_key in (
                "number_of_flagged_segments",
                "number_of_second_pass_regions",
                "number_of_replaced_segments",
            ):
                selective_metadata[count_key] = int(selective_metadata[count_key])
            selective_metadata["number_of_retained_first_pass_segments"] = max(
                0,
                len(first_pass_segments) - int(selective_metadata["number_of_replaced_segments"]),
            )
            selective_metadata["number_of_selected_segments"] = len(asr_segments)
            selective_metadata["first_pass_processing_time_seconds"] = round(
                float(selective_metadata["first_pass_processing_time_seconds"]),
                6,
            )
            selective_metadata["second_pass_processing_time_seconds"] = round(
                float(selective_metadata["second_pass_processing_time_seconds"]),
                6,
            )
            selective_metadata["total_additional_processing_time_seconds"] = selective_metadata[
                "second_pass_processing_time_seconds"
            ]
            selective_metadata["percentage_of_audio_retranscribed"] = round(
                (float(selective_metadata["retranscribed_audio_seconds"]) / total_duration * 100.0)
                if total_duration > 0.0
                else 0.0,
                3,
            )
            selective_metadata["first_pass_segments"] = [
                segment.model_dump(mode="json") for segment in first_pass_segments
            ]
            if selective_metadata.get("fallback_reason"):
                warnings.append(str(selective_metadata["fallback_reason"]))

            glossary_metadata = resolved_glossary.to_metadata()
            glossary_metadata["hotwords_supported"] = any(
                bool(segment.metadata.get("hotwords_supported")) for segment in asr_segments
            )
            glossary_metadata["hotwords_applied"] = any(
                bool(segment.metadata.get("hotwords_applied")) for segment in asr_segments
            )
            if glossary_metadata.get("omitted_count"):
                warnings.append(
                    f"Glossary limits omitted {glossary_metadata['omitted_count']} supplied term(s); see glossary metadata."
                )
            if (
                glossary_metadata.get("project_glossary_error")
                and self._settings.transcription_project_glossary_path
            ):
                warnings.append(str(glossary_metadata["project_glossary_error"]))

            # 2. LLM Cleanup
            _report_progress(progress_callback, "extraction", 80)
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
            transcript = build_transcription_result(
                settings=self._settings,
                asr=self._asr,
                vad=self._vad,
                profile=resolved_profile,
                conversation_id=resolved_conversation_id,
                source=source,
                language=resolved_language,
                quality_mode=resolved_quality,
                segments=corrected_segments,
                asr_segments=asr_segments,
                vad_regions=vad_regions,
                diarization_turns=diarization_turns,
                processing_windows=processing_windows,
                start_process=start_process,
                end_process=end_process,
                total_duration=total_duration,
                preprocessing_status=preprocessing_status,
                preprocessing_step_names=preprocessing_step_names,
                normalize_success=normalize_success,
                input_inspection=input_inspection,
                output_inspection=output_inspection,
                audio_quality_metadata=audio_quality_metadata,
                selective_metadata=selective_metadata,
                glossary_metadata=glossary_metadata,
                warnings=warnings,
                debug=debug,
            )

            if include_summary and self._settings.enable_summary:
                summary, topics, action_items, decisions = self._summary_service.build_summary(
                    transcript
                )
                transcript.summary = summary
                transcript.topics = topics
                transcript.action_items = action_items
                transcript.decisions = decisions
            transcript.updated_at = datetime.now(tz=UTC)
            return transcript
        finally:
            normalized_path.unlink(missing_ok=True)
