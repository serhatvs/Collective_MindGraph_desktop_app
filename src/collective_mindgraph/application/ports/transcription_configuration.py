"""Configuration shape consumed by local transcription adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class TranscriptionConfiguration(Protocol):
    temp_dir: Path
    sample_rate: int
    default_language: str | None
    transcription_quality_mode: str
    transcript_cleanup_mode: str
    transcription_project_glossary_path: Path | None
    enable_summary: bool
    allow_remote_access: bool
    allow_remote_download: bool
    vad_provider: str
    vad_energy_threshold: float
    vad_frame_ms: int
    vad_min_speech_ms: int
    vad_min_silence_ms: int
    vad_merge_gap_ms: int
    vad_padding_ms: int
    vad_max_region_seconds: float
    vad_target_region_seconds: float
    vad_split_search_seconds: float
    vad_adaptive_multiplier: float
    vad_smoothing_frames: int
    asr_provider: str
    asr_model_name: str
    asr_device: str
    asr_compute_type: str
    asr_beam_size: int
    asr_region_padding_seconds: float
    asr_word_timestamps: bool
    asr_internal_vad_enabled: bool
    asr_condition_on_previous_text: bool
    asr_safe_silence_trim: bool
    asr_fast_model_name: str
    asr_fast_compute_type: str
    asr_balanced_model_name: str
    asr_balanced_compute_type: str
    asr_max_quality_model_name: str
    asr_max_quality_compute_type: str
    asr_max_quality_beam_size: int
    asr_bad_mic_model_name: str
    asr_bad_mic_compute_type: str
    asr_bad_mic_noise_reduction: bool
    diarization_enabled: bool
    diarizer_provider: str
    diarizer_model_name: str
    diarizer_device: str
    diarizer_auth_token: str | None
    diarizer_region_padding_seconds: float
    diarizer_merge_gap_seconds: float
    diarizer_max_window_seconds: float
    diarizer_overlap_threshold: float
    llm_provider: str
    llm_model_name: str
    llm_endpoint: str | None
    llm_api_key: str | None
    llm_timeout_seconds: float
    llm_batch_size: int
    llm_context_segments: int
    pipeline_max_window_seconds: float
    pipeline_window_overlap_seconds: float
    selective_retranscription_enabled: bool
    selective_retranscription_profile: str
    selective_retranscription_model: str
    selective_retranscription_compute_type: str
    selective_retranscription_beam_size: int
    selective_retranscription_max_regions: int
    selective_retranscription_padding_seconds: float
    selective_retranscription_merge_gap_seconds: float
    selective_retranscription_min_segment_duration: float
    selective_retranscription_max_segment_duration: float
    selective_retranscription_min_text_length: int
    selective_retranscription_min_words_per_second: float
    selective_retranscription_max_words_per_second: float
    selective_retranscription_avg_logprob_threshold: float
    selective_retranscription_no_speech_threshold: float
    selective_retranscription_compression_ratio_threshold: float
    selective_retranscription_word_probability_threshold: float
    selective_retranscription_audio_quality_threshold: float
    selective_retranscription_candidate_score_threshold: float
    selective_retranscription_min_improvement: float

    def ensure_directories(self) -> None: ...
