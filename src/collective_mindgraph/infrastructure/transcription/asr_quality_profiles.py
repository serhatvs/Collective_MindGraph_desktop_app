"""Named ASR quality profiles derived from engine configuration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from collective_mindgraph.application.ports import TranscriptionConfiguration

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ASRQualityProfile:
    name: str
    model_name: str
    compute_type: str
    beam_size: int
    word_timestamps: bool
    vad_filter: bool
    condition_on_previous_text: bool
    no_speech_threshold: float
    temperature: tuple[float, ...]
    preprocessing_strength: str


def resolve_asr_quality_profile(
    settings: TranscriptionConfiguration,
    quality_mode: str | None = None,
) -> ASRQualityProfile:
    requested = (
        (quality_mode or settings.transcription_quality_mode or "max_quality").strip().lower()
    )
    if requested == "accurate":
        requested = "max_quality"
    valid_profiles = {
        "fast",
        "balanced",
        "max_quality",
        "bad_mic_recovery",
        "selective_recovery",
    }
    if requested not in valid_profiles:
        LOGGER.warning("Unknown ASR quality profile %r; using max_quality.", requested)
        requested = "max_quality"

    base_model = settings.asr_model_name
    base_compute_type = settings.asr_compute_type
    word_timestamps = bool(settings.asr_word_timestamps)
    vad_filter = bool(settings.asr_internal_vad_enabled)
    condition_on_previous_text = bool(settings.asr_condition_on_previous_text)
    if requested == "fast":
        return ASRQualityProfile(
            name="fast",
            model_name=_profile_value(settings.asr_fast_model_name, base_model),
            compute_type=_profile_value(
                settings.asr_fast_compute_type,
                base_compute_type,
            ),
            beam_size=1,
            word_timestamps=False if settings.asr_word_timestamps else word_timestamps,
            vad_filter=False,
            condition_on_previous_text=False,
            no_speech_threshold=0.5,
            temperature=(0.0,),
            preprocessing_strength="format_only",
        )
    if requested == "balanced":
        return ASRQualityProfile(
            name="balanced",
            model_name=_profile_value(settings.asr_balanced_model_name, base_model),
            compute_type=_profile_value(
                settings.asr_balanced_compute_type,
                base_compute_type,
            ),
            beam_size=max(3, settings.asr_beam_size),
            word_timestamps=word_timestamps,
            vad_filter=vad_filter,
            condition_on_previous_text=condition_on_previous_text,
            no_speech_threshold=0.6,
            temperature=(0.0, 0.2),
            preprocessing_strength="safe_loudness",
        )
    if requested == "bad_mic_recovery":
        return ASRQualityProfile(
            name="bad_mic_recovery",
            model_name=_profile_value(settings.asr_bad_mic_model_name, base_model),
            compute_type=_profile_value(
                settings.asr_bad_mic_compute_type,
                base_compute_type,
            ),
            beam_size=max(
                5,
                settings.asr_max_quality_beam_size,
                settings.asr_beam_size,
            ),
            word_timestamps=word_timestamps,
            vad_filter=False,
            condition_on_previous_text=False,
            no_speech_threshold=0.85,
            temperature=(0.0, 0.2, 0.4, 0.6),
            preprocessing_strength="bad_mic_recovery",
        )
    if requested == "selective_recovery":
        compute_type = settings.selective_retranscription_compute_type
        if not compute_type:
            compute_type = "float16" if _is_cuda_device(settings.asr_device) else base_compute_type
        return ASRQualityProfile(
            name="selective_recovery",
            model_name=_profile_value(
                settings.selective_retranscription_model,
                base_model,
            ),
            compute_type=compute_type,
            beam_size=max(
                settings.selective_retranscription_beam_size,
                settings.asr_max_quality_beam_size,
                settings.asr_beam_size,
            ),
            word_timestamps=True,
            vad_filter=False,
            condition_on_previous_text=False,
            no_speech_threshold=0.85,
            temperature=(0.0, 0.2, 0.4, 0.6),
            preprocessing_strength="format_only",
        )
    return ASRQualityProfile(
        name="max_quality",
        model_name=_profile_value(settings.asr_max_quality_model_name, base_model),
        compute_type=_profile_value(
            settings.asr_max_quality_compute_type,
            base_compute_type,
        ),
        beam_size=max(
            5,
            settings.asr_max_quality_beam_size,
            settings.asr_beam_size,
        ),
        word_timestamps=word_timestamps,
        vad_filter=vad_filter,
        condition_on_previous_text=condition_on_previous_text,
        no_speech_threshold=0.7,
        temperature=(0.0, 0.2, 0.4),
        preprocessing_strength="safe_loudness",
    )


def _profile_value(value: str | None, fallback: str) -> str:
    cleaned = (value or "").strip()
    return cleaned or fallback


def _is_cuda_device(device: str | None) -> bool:
    return (device or "").strip().lower().startswith("cuda")
