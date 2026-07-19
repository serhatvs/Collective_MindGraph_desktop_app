"""Shared helpers for local ASR validation scripts."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass, field
import os
from pathlib import Path
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REALTIME_BACKEND_ROOT = REPO_ROOT / "realtime_backend"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REALTIME_BACKEND_ROOT))

from app.config import Settings  # noqa: E402
from app.evaluation.transcription_metrics import (  # noqa: E402
    character_error_rate as _shared_character_error_rate,
    word_error_rate as _shared_word_error_rate,
)
from app.models import SpeechRegion  # noqa: E402
from app.pipeline.asr_runtime_config import build_asr_diagnostics, format_asr_diagnostics  # noqa: E402
from app.pipeline.orchestrator import TranscriptionPipeline  # noqa: E402
from app.utils.audio_process import inspect_audio  # noqa: E402


TURKISH_CHARS = ["ç", "ğ", "ı", "İ", "ö", "ş", "ü"]


@dataclass(slots=True)
class PipelineRun:
    label: str
    profile: str
    model: str
    requested_vad_provider: str
    actual_vad_provider: str | None = None
    audio_path: Path | None = None
    audio_duration: float | None = None
    model_load_time_seconds: float | None = None
    transcription_time_seconds: float | None = None
    real_time_factor: float | None = None
    segment_count: int = 0
    speech_region_count: int = 0
    speech_regions: list[tuple[float, float]] = field(default_factory=list)
    raw_transcript: str = ""
    cleaned_transcript: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


class NoVAD:
    provider_name = "none"

    def __init__(self, _settings: Settings) -> None:
        return

    def detect(self, _audio_path: Path) -> list[SpeechRegion]:
        return []


async def run_cmg_pipeline(
    *,
    audio_path: Path,
    label: str,
    profile: str,
    model: str,
    vad_provider: str,
    language: str = "tr",
    quality_mode: str = "max_quality",
    require_gpu: bool = False,
) -> PipelineRun:
    audio_path = audio_path.expanduser().resolve()
    inspection = inspect_audio(audio_path)
    duration = inspection.duration_seconds if inspection else None
    run = PipelineRun(
        label=label,
        profile=profile,
        model=model,
        requested_vad_provider=vad_provider,
        audio_path=audio_path,
        audio_duration=duration,
    )
    if not audio_path.exists():
        run.error = f"Audio file not found: {audio_path}"
        return run

    with asr_environment(profile=profile, model=model, language=language, require_gpu=require_gpu):
        settings = Settings()
        settings.vad_provider = "energy" if vad_provider == "none" else vad_provider
        settings.default_language = language
        settings.transcription_quality_mode = quality_mode
        settings.diarization_enabled = False
        settings.diarizer_provider = "fallback"
        settings.llm_provider = "none"
        settings.enable_summary = False
        settings.ensure_directories()

        start_load = time.perf_counter()
        try:
            vad = NoVAD(settings) if vad_provider == "none" else None
            pipeline = TranscriptionPipeline(settings=settings, vad=vad)
        except Exception as exc:
            run.error = f"{type(exc).__name__}: {exc}"
            run.model_load_time_seconds = time.perf_counter() - start_load
            return run
        run.model_load_time_seconds = time.perf_counter() - start_load
        run.actual_vad_provider = getattr(pipeline._vad, "provider_name", settings.vad_provider)
        run.diagnostics = build_asr_diagnostics(
            settings,
            pipeline._asr,
            llm_provider=pipeline._llm_postprocessor._provider,
        )
        if vad_provider == "silero" and run.actual_vad_provider != "silero":
            run.warnings.append("Silero VAD was requested but did not load; ASR continued with fallback VAD.")

        start_transcribe = time.perf_counter()
        try:
            transcript = await pipeline.process_audio_path(
                audio_path,
                source=f"asr_benchmark_{label}",
                language=language,
                quality_mode=quality_mode,
                include_summary=False,
                debug=True,
            )
        except Exception as exc:
            run.error = f"{type(exc).__name__}: {exc}"
            run.transcription_time_seconds = time.perf_counter() - start_transcribe
            return run

    run.transcription_time_seconds = time.perf_counter() - start_transcribe
    run.metadata = dict(transcript.metadata)
    if transcript.debug is not None:
        run.speech_region_count = len(transcript.debug.vad_regions)
        run.speech_regions = [(region.start, region.end) for region in transcript.debug.vad_regions]
    run.segment_count = len(transcript.segments)
    run.raw_transcript = "\n".join(segment.raw_text for segment in transcript.segments).strip()
    run.cleaned_transcript = "\n".join(segment.corrected_text for segment in transcript.segments).strip()
    run.warnings.extend(str(item) for item in run.metadata.get("warnings", []) if item)
    if duration and run.transcription_time_seconds is not None:
        run.real_time_factor = run.transcription_time_seconds / duration
    return run


def run_pipeline_sync(**kwargs: Any) -> PipelineRun:
    return asyncio.run(run_cmg_pipeline(**kwargs))


@contextmanager
def asr_environment(*, profile: str, model: str, language: str, require_gpu: bool):
    keys = [
        "CMG_RUNTIME_PROFILE",
        "CMG_GPU_ENABLED",
        "CMG_REQUIRE_GPU",
        "CMG_ASR_MODEL",
        "CMG_ASR_LANGUAGE",
        "CMG_ASR_DEVICE",
        "CMG_ASR_COMPUTE_TYPE",
        "CMG_EMBEDDING_DEVICE",
    ]
    previous = {key: os.environ.get(key) for key in keys}
    try:
        os.environ["CMG_RUNTIME_PROFILE"] = profile
        os.environ["CMG_GPU_ENABLED"] = "1" if profile == "gpu_asr" else "0"
        os.environ["CMG_REQUIRE_GPU"] = "1" if require_gpu else "0"
        os.environ["CMG_ASR_MODEL"] = model
        os.environ["CMG_ASR_LANGUAGE"] = language
        os.environ["CMG_EMBEDDING_DEVICE"] = "cpu"
        if profile == "gpu_asr":
            os.environ["CMG_ASR_DEVICE"] = "cuda"
            os.environ["CMG_ASR_COMPUTE_TYPE"] = "float16"
        else:
            os.environ["CMG_ASR_DEVICE"] = "cpu"
            os.environ["CMG_ASR_COMPUTE_TYPE"] = "int8"
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def word_error_rate(reference: str, hypothesis: str) -> float:
    result = _shared_word_error_rate(reference, hypothesis)
    return result if result is not None else (0.0 if not hypothesis.strip() else 1.0)


def character_error_rate(reference: str, hypothesis: str) -> float:
    result = _shared_character_error_rate(reference, hypothesis)
    return result if result is not None else (0.0 if not hypothesis.strip() else 1.0)


def should_score_accuracy(reference_path: Path | None) -> bool:
    return bool(reference_path and reference_path.exists())


def provider_status(requested: str, actual: str | None, error: str | None) -> str:
    if error:
        return "error"
    if requested == "silero" and actual != "silero":
        return "silero_unavailable_asr_continued"
    return "ok"


def format_seconds(value: float | None) -> str:
    return "unknown" if value is None else f"{value:.3f}"


def format_run_summary(run: PipelineRun) -> str:
    return "\n".join(
        [
            f"- Label: `{run.label}`",
            f"- Profile: `{run.profile}`",
            f"- Model: `{run.model}`",
            f"- Requested VAD provider: `{run.requested_vad_provider}`",
            f"- Actual VAD provider: `{run.actual_vad_provider}`",
            f"- Model load time: `{format_seconds(run.model_load_time_seconds)}` seconds",
            f"- Transcription time: `{format_seconds(run.transcription_time_seconds)}` seconds",
            f"- Real-time factor: `{format_seconds(run.real_time_factor)}`",
            f"- Segment count: `{run.segment_count}`",
            f"- Speech region count: `{run.speech_region_count}`",
            f"- ASR status: `{run.metadata.get('asr_status')}`",
            f"- Mock fallback used: `{run.metadata.get('mock_fallback_used')}`",
            f"- GPU requested: `{run.metadata.get('gpu_requested', run.diagnostics.get('GPU requested by ASR'))}`",
            f"- GPU actually used by ASR: `{run.metadata.get('gpu_loaded', run.diagnostics.get('GPU actually loaded by ASR'))}`",
            f"- GPU fallback happened: `{run.metadata.get('gpu_fallback_happened', run.diagnostics.get('Fallback happened'))}`",
            f"- Fallback reason: `{run.metadata.get('gpu_fallback_reason', run.diagnostics.get('Fallback reason'))}`",
            f"- Error: `{run.error}`",
        ]
    )


def diagnostics_block(run: PipelineRun) -> str:
    return format_asr_diagnostics(run.diagnostics) if run.diagnostics else "[diagnostics unavailable]"
