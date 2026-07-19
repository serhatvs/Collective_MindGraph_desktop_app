"""Invoke the existing CMG transcription pipeline for annotation candidates."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from realtime_backend.app.config import Settings
from realtime_backend.app.pipeline.orchestrator import TranscriptionPipeline


class RealASRUnavailableError(RuntimeError):
    """Raised when a real local Faster-Whisper result cannot be produced."""


async def transcribe_for_annotation(
    audio_path: Path,
    *,
    profile: str = "balanced",
    model_override: str | None = None,
    selective_model_override: str | None = None,
    selective_enabled: bool = False,
    selective_profile: str = "selective_recovery",
    glossary_file: Path | None = None,
    glossary_terms: list[str] | None = None,
    settings_factory: Callable[[], Settings] = Settings,
    pipeline_factory: Callable[[Settings], Any] = TranscriptionPipeline,
) -> Any:
    """Run the normal pipeline with local-only, real-ASR-only settings."""

    source = audio_path.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    settings = settings_factory()
    settings.asr_provider = "faster_whisper"
    settings.allow_remote_download = False
    settings.default_language = "tr"
    settings.transcription_quality_mode = profile
    settings.selective_retranscription_enabled = bool(selective_enabled)
    settings.selective_retranscription_profile = selective_profile
    if glossary_file is not None:
        settings.transcription_project_glossary_path = glossary_file
    settings.diarization_enabled = False
    settings.diarizer_provider = "fallback"
    settings.llm_provider = "disabled"
    settings.enable_summary = False
    if model_override:
        _apply_model_override(settings, profile, model_override)
    if selective_model_override:
        settings.selective_retranscription_model = selective_model_override

    try:
        pipeline = pipeline_factory(settings)
        transcript = await pipeline.process_audio_path(
            source,
            source="transcript_annotation",
            language="tr",
            quality_mode=profile,
            include_summary=False,
            debug=False,
            session_glossary_terms=glossary_terms,
        )
    except Exception as exc:
        raise RealASRUnavailableError(
            f"Real local Faster-Whisper transcription is unavailable: {type(exc).__name__}: {exc}"
        ) from exc
    metadata = dict(getattr(transcript, "metadata", {}) or {})
    asr_status = str(metadata.get("asr_status") or "")
    if metadata.get("mock_fallback_used") or "MOCK" in asr_status.upper():
        raise RealASRUnavailableError(
            "The existing pipeline returned mock ASR. Install/cache the configured local Faster-Whisper model; "
            "the annotation dataset was not modified."
        )
    return transcript


def _apply_model_override(settings: Settings, profile: str, model: str) -> None:
    selected = profile.strip().lower()
    if selected == "balanced":
        settings.asr_balanced_model_name = model
    elif selected == "fast":
        settings.asr_fast_model_name = model
    elif selected == "bad_mic_recovery":
        settings.asr_bad_mic_model_name = model
    elif selected == "selective_recovery":
        settings.selective_retranscription_model = model
    else:
        settings.asr_max_quality_model_name = model
