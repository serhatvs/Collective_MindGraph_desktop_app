"""Build canonical processing results and diagnostics from pipeline artifacts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from collective_mindgraph.application.ports import TranscriptionConfiguration
from collective_mindgraph.application.transcription.contracts import (
    ASRSegment,
    ConversationTranscript,
    DiarizationTurn,
    ProcessingDebug,
    SpeechRegion,
    TranscriptionDiagnostics,
    TranscriptSegment,
)

from .asr import ASR_STATUS_MOCK_FALLBACK, ASR_STATUS_OK
from .recording_processing_helpers import audio_inspection_metadata, unique_strings
from .transcription_quality import estimate_transcription_confidence


def build_transcription_result(
    *,
    settings: TranscriptionConfiguration,
    asr: Any,
    vad: Any,
    profile: Any,
    conversation_id: str,
    source: str,
    language: str,
    quality_mode: str,
    segments: list[TranscriptSegment],
    asr_segments: list[ASRSegment],
    vad_regions: list[SpeechRegion],
    diarization_turns: list[DiarizationTurn],
    processing_windows: list[SpeechRegion],
    start_process: datetime,
    end_process: datetime,
    total_duration: float,
    preprocessing_status: str,
    preprocessing_step_names: tuple[str, ...] | list[str],
    normalize_success: bool,
    input_inspection: Any,
    output_inspection: Any,
    audio_quality_metadata: dict[str, object],
    selective_metadata: dict[str, object],
    glossary_metadata: dict[str, object],
    warnings: list[str],
    debug: bool,
) -> ConversationTranscript:
    processing_time_seconds = (end_process - start_process).total_seconds()
    raw_asr_status = getattr(asr, "asr_status", ASR_STATUS_OK)
    asr_status = raw_asr_status if isinstance(raw_asr_status, str) else ASR_STATUS_OK
    raw_mock_fallback = getattr(asr, "mock_fallback_used", False)
    mock_fallback_used = raw_mock_fallback if isinstance(raw_mock_fallback, bool) else False
    fallback_reason = _string_attribute(asr, "fallback_reason")
    gpu_fallback_reason = _string_attribute(asr, "gpu_fallback_reason")
    cuda_load_status = _string_attribute(asr, "cuda_load_status")
    _mark_fallback_segments(
        segments,
        warnings,
        asr_status=asr_status,
        mock_fallback_used=mock_fallback_used,
    )

    confidence_estimate = estimate_transcription_confidence(
        audio_quality=audio_quality_metadata,
        asr_segments=asr_segments,
        transcript_segments=segments,
        language=language,
        duration_seconds=total_duration,
    )
    warnings.extend(confidence_estimate.warnings)
    warnings = unique_strings(warnings)

    metadata = {
        "asr_provider": asr.provider_name,
        "asr_status": asr_status,
        "ASR_STATUS": asr_status.removeprefix("ASR_STATUS="),
        "model_name": profile.model_name,
        "base_model_name": settings.asr_model_name,
        "quality_profile": profile.name,
        "language": language,
        "beam_size": profile.beam_size,
        "runtime_profile": getattr(settings, "asr_runtime_profile", "cpu"),
        "device": settings.asr_device,
        "compute_type": profile.compute_type,
        "base_compute_type": settings.asr_compute_type,
        "word_timestamps": profile.word_timestamps,
        "internal_faster_whisper_vad": profile.vad_filter,
        "condition_on_previous_text": profile.condition_on_previous_text,
        "no_speech_threshold": profile.no_speech_threshold,
        "temperature_fallback": list(profile.temperature),
        "vad_provider": getattr(vad, "provider_name", settings.vad_provider),
        "preprocessing_status": preprocessing_status,
        "preprocessing_strength": profile.preprocessing_strength,
        "preprocessing_steps": list(preprocessing_step_names),
        "ffmpeg_normalization_succeeded": normalize_success,
        "input_audio": audio_inspection_metadata(input_inspection),
        "asr_input_audio": audio_inspection_metadata(output_inspection),
        "audio_quality": audio_quality_metadata,
        "audio_quality_score": confidence_estimate.audio_quality_score,
        "audio_quality_label": confidence_estimate.audio_quality_label,
        "transcription_confidence_estimate": confidence_estimate.score,
        "estimated_transcription_quality": confidence_estimate.score,
        "transcription_confidence_label": confidence_estimate.label,
        "confidence_estimate": confidence_estimate.to_metadata(),
        "confidence_estimate_not_accuracy": True,
        "selective_retranscription": selective_metadata,
        "selective_retranscription_enabled": bool(settings.selective_retranscription_enabled),
        "glossary": glossary_metadata,
        "processing_time_seconds": processing_time_seconds,
        "mock_fallback_used": mock_fallback_used,
        "gpu_requested": bool(getattr(asr, "gpu_requested", False)),
        "gpu_loaded": bool(getattr(asr, "gpu_loaded", False)),
        "gpu_fallback_happened": bool(getattr(asr, "gpu_fallback_happened", False)),
        "gpu_fallback_reason": gpu_fallback_reason,
        "faster_whisper_cuda_load_status": cuda_load_status,
        "gpu_required": bool(getattr(settings, "gpu_required", False)),
        "gpu_enabled": bool(getattr(settings, "gpu_enabled", False)),
        "transcript_cleanup_mode": settings.transcript_cleanup_mode,
        "raw_asr_text_preserved": True,
        "warnings": warnings,
    }
    if fallback_reason:
        metadata["asr_fallback_reason"] = fallback_reason

    diagnostics = TranscriptionDiagnostics(
        provider=asr.provider_name,
        model=profile.model_name,
        asr_status=asr_status,
        mock_fallback_used=mock_fallback_used,
        runtime_profile=getattr(settings, "asr_runtime_profile", "cpu"),
        device=settings.asr_device,
        language=language,
        quality_mode=quality_mode,
        quality_profile=profile.name,
        beam_size=profile.beam_size,
        compute_type=profile.compute_type,
        word_timestamps_enabled=profile.word_timestamps,
        internal_vad_enabled=profile.vad_filter,
        condition_on_previous_text=profile.condition_on_previous_text,
        preprocessing_status=preprocessing_status,
        preprocessing_format=output_inspection.format if output_inspection else None,
        audio_duration=total_duration,
        sample_rate_in=input_inspection.sample_rate if input_inspection else None,
        sample_rate_out=output_inspection.sample_rate if output_inspection else None,
        channels_in=input_inspection.channels if input_inspection else None,
        channels_out=output_inspection.channels if output_inspection else None,
        vad_settings={
            "provider": getattr(vad, "provider_name", settings.vad_provider),
            "frame_ms": settings.vad_frame_ms,
            "min_speech_ms": settings.vad_min_speech_ms,
            "min_silence_ms": settings.vad_min_silence_ms,
            "padding_ms": settings.vad_padding_ms,
            "merge_gap_ms": settings.vad_merge_gap_ms,
            "max_region_seconds": settings.vad_max_region_seconds,
            "target_region_seconds": settings.vad_target_region_seconds,
        },
        chunk_count=len(processing_windows),
        processing_time_seconds=processing_time_seconds,
        gpu_requested=bool(getattr(asr, "gpu_requested", False)),
        gpu_loaded=bool(getattr(asr, "gpu_loaded", False)),
        gpu_fallback_happened=bool(getattr(asr, "gpu_fallback_happened", False)),
        gpu_fallback_reason=gpu_fallback_reason,
        faster_whisper_cuda_load_status=cuda_load_status,
        raw_transcript_length=sum(len(item.raw_text) for item in segments),
        cleaned_transcript_length=sum(len(item.corrected_text) for item in segments),
        audio_quality_score=confidence_estimate.audio_quality_score,
        audio_quality_label=confidence_estimate.audio_quality_label,
        transcription_confidence_estimate=confidence_estimate.score,
        estimated_transcription_quality=confidence_estimate.score,
        confidence_warnings=list(confidence_estimate.warnings),
        selective_retranscription_enabled=bool(settings.selective_retranscription_enabled),
        selective_retranscription_profile=str(selective_metadata["second_pass_profile"]),
        selective_retranscription_model=str(selective_metadata["second_pass_model"]),
        selective_retranscription_flagged_segments=int(
            selective_metadata["number_of_flagged_segments"]
        ),
        selective_retranscription_regions=int(selective_metadata["number_of_second_pass_regions"]),
        selective_retranscription_replaced_segments=int(
            selective_metadata["number_of_replaced_segments"]
        ),
        selective_retranscription_fallback_reason=(
            str(selective_metadata["fallback_reason"])
            if selective_metadata.get("fallback_reason")
            else None
        ),
        selective_retranscription_additional_seconds=float(
            selective_metadata["total_additional_processing_time_seconds"]
        ),
        glossary_metadata=glossary_metadata,
        warnings=warnings,
    )
    return ConversationTranscript(
        conversation_id=conversation_id,
        source=source,
        language=language,
        quality_mode=quality_mode,
        segments=segments,
        metadata=metadata,
        diagnostics=diagnostics,
        debug=(
            ProcessingDebug(
                vad_regions=vad_regions,
                diarization_turns=diarization_turns,
                asr_segments=asr_segments,
            )
            if debug
            else None
        ),
    )


def _string_attribute(owner: object, name: str) -> str | None:
    value = getattr(owner, name, None)
    return value if isinstance(value, str) else None


def _mark_fallback_segments(
    segments: list[TranscriptSegment],
    warnings: list[str],
    *,
    asr_status: str,
    mock_fallback_used: bool,
) -> None:
    if mock_fallback_used:
        warnings.append(
            f"{ASR_STATUS_MOCK_FALLBACK}: Mock ASR fallback used; "
            "transcript is not real ASR output."
        )
        marker = ASR_STATUS_MOCK_FALLBACK
    elif asr_status != ASR_STATUS_OK:
        warnings.append(f"{asr_status}: Mock ASR used; transcript is not real ASR output.")
        marker = asr_status
    else:
        return
    for segment in segments:
        if marker not in segment.notes:
            segment.notes.append(marker)
        segment.metadata["asr_status"] = marker
        if mock_fallback_used:
            segment.metadata["mock_fallback_used"] = True
