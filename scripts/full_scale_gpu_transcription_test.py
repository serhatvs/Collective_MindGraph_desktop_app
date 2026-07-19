"""Run an end-to-end CMG transcription pipeline test for GPU ASR validation."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REALTIME_BACKEND_ROOT = REPO_ROOT / "realtime_backend"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REALTIME_BACKEND_ROOT))

from app.config import Settings  # noqa: E402
from app.pipeline.asr import ASR_STATUS_MOCK_FALLBACK  # noqa: E402
from app.pipeline.asr_runtime_config import format_asr_diagnostics  # noqa: E402
from app.pipeline.orchestrator import TranscriptionPipeline  # noqa: E402
from app.utils.audio_process import inspect_audio  # noqa: E402
from app.utils.logging import configure_logging  # noqa: E402


TURKISH_CHARS = ["ç", "ğ", "ı", "İ", "ö", "ş", "ü"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a full CMG transcription pipeline GPU ASR test.")
    parser.add_argument("--audio", type=Path, required=True, help="Audio file to transcribe.")
    parser.add_argument("--profile", choices=["gpu_asr", "cpu"], help="Runtime profile for this run.")
    parser.add_argument("--vad-provider", default="energy", help="VAD provider for this ASR-focused test.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/reports/2026-06-30/gpu-asr/FULL_SCALE_GPU_ASR_TEST_REPORT.md"),
        help="Markdown report path.",
    )
    parser.add_argument(
        "--observation-seconds",
        type=int,
        default=0,
        help="Optional pause after model load so nvidia-smi can be observed manually.",
    )
    return parser.parse_args()


async def main_async() -> int:
    args = parse_args()
    output_path = _resolve_repo_path(args.output)
    audio_path = args.audio.expanduser().resolve()

    if args.profile:
        os.environ["CMG_RUNTIME_PROFILE"] = args.profile
    os.environ.setdefault("CMG_RT_VAD_PROVIDER", args.vad_provider)
    os.environ.setdefault("CMG_RT_DIARIZATION_ENABLED", "false")
    os.environ.setdefault("CMG_RT_DIARIZER_PROVIDER", "fallback")
    os.environ.setdefault("CMG_RT_LLM_PROVIDER", "none")
    os.environ.setdefault("CMG_RT_ENABLE_SUMMARY", "false")

    configure_logging("INFO")
    settings = Settings()
    settings.vad_provider = args.vad_provider
    settings.diarization_enabled = False
    settings.diarizer_provider = "fallback"
    settings.llm_provider = "none"
    settings.enable_summary = False
    settings.ensure_directories()

    started_at = datetime.now(tz=UTC)
    if not audio_path.exists():
        report = _build_report(
            status="FULL_SCALE_GPU_ASR_TEST_NOT_RUN_NO_AUDIO",
            settings=settings,
            audio_path=audio_path,
            audio_duration=None,
            diagnostics={},
            nvidia_smi_load="not run",
            nvidia_smi_after="not run",
            error=f"Audio file not found: {audio_path}",
            started_at=started_at,
        )
        _write_report(output_path, report)
        print(f"Audio file not found: {audio_path}")
        print(f"Report written to {output_path}")
        return 1

    audio_inspection = inspect_audio(audio_path)
    audio_duration = audio_inspection.duration_seconds if audio_inspection else None

    try:
        pipeline = TranscriptionPipeline(settings=settings)
    except Exception as exc:
        report = _build_report(
            status="FULL_SCALE_GPU_ASR_TEST_FAILED_ASR_INIT",
            settings=settings,
            audio_path=audio_path,
            audio_duration=audio_duration,
            diagnostics={},
            nvidia_smi_load=_capture_nvidia_smi(),
            nvidia_smi_after="not run",
            error=f"{type(exc).__name__}: {exc}",
            started_at=started_at,
        )
        _write_report(output_path, report)
        print(f"ASR pipeline failed to initialize: {type(exc).__name__}: {exc}")
        print(f"Report written to {output_path}")
        return 1

    asr_diagnostics = pipeline.runtime_status().diagnostics()
    nvidia_smi_load = _capture_nvidia_smi()
    if args.observation_seconds > 0:
        print(f"GPU observation window after model load: {args.observation_seconds} seconds")
        time.sleep(args.observation_seconds)

    start = time.perf_counter()
    try:
        transcript = await pipeline.process_audio_path(
            audio_path,
            source="full_scale_gpu_asr_test",
            language=settings.default_language,
            quality_mode=settings.transcription_quality_mode,
            include_summary=False,
            debug=True,
        )
    except Exception as exc:
        report = _build_report(
            status="FULL_SCALE_GPU_ASR_TEST_FAILED_TRANSCRIPTION",
            settings=settings,
            audio_path=audio_path,
            audio_duration=audio_duration,
            diagnostics=asr_diagnostics,
            nvidia_smi_load=nvidia_smi_load,
            nvidia_smi_after=_capture_nvidia_smi(),
            error=f"{type(exc).__name__}: {exc}",
            started_at=started_at,
        )
        _write_report(output_path, report)
        print(f"Transcription failed: {type(exc).__name__}: {exc}")
        print(f"Report written to {output_path}")
        return 1

    transcription_time = time.perf_counter() - start
    nvidia_smi_after = _capture_nvidia_smi()
    raw_transcript = "\n".join(segment.raw_text for segment in transcript.segments).strip()
    cleaned_transcript = "\n".join(segment.corrected_text for segment in transcript.segments).strip()
    metadata = dict(transcript.metadata)
    duration = audio_duration or metadata.get("input_audio", {}).get("duration_seconds")
    real_time_factor = transcription_time / duration if isinstance(duration, (int, float)) and duration > 0 else None
    mock_fallback_used = bool(metadata.get("mock_fallback_used"))
    status = "FULL_SCALE_GPU_ASR_TEST_RUN"
    if metadata.get("asr_status") == ASR_STATUS_MOCK_FALLBACK or mock_fallback_used:
        status = "FULL_SCALE_GPU_ASR_TEST_INVALID_MOCK_FALLBACK"
    elif metadata.get("gpu_requested") and not metadata.get("gpu_loaded"):
        status = "FULL_SCALE_GPU_ASR_TEST_FAILED_GPU_NOT_LOADED"

    report = _build_report(
        status=status,
        settings=settings,
        audio_path=audio_path,
        audio_duration=duration if isinstance(duration, (int, float)) else audio_duration,
        diagnostics=asr_diagnostics,
        nvidia_smi_load=nvidia_smi_load,
        nvidia_smi_after=nvidia_smi_after,
        error=None,
        started_at=started_at,
        transcription_time=transcription_time,
        real_time_factor=real_time_factor,
        segment_count=len(transcript.segments),
        raw_transcript=raw_transcript,
        cleaned_transcript=cleaned_transcript,
        metadata=metadata,
    )
    _write_report(output_path, report)
    print(f"Report written to {output_path}")
    if status != "FULL_SCALE_GPU_ASR_TEST_RUN":
        return 2
    return 0


def _build_report(
    *,
    status: str,
    settings: Settings,
    audio_path: Path,
    audio_duration: float | None,
    diagnostics: dict[str, Any],
    nvidia_smi_load: str,
    nvidia_smi_after: str,
    error: str | None,
    started_at: datetime,
    transcription_time: float | None = None,
    real_time_factor: float | None = None,
    segment_count: int | None = None,
    raw_transcript: str = "",
    cleaned_transcript: str = "",
    metadata: dict[str, Any] | None = None,
) -> str:
    metadata = metadata or {}
    gpu_observed = _current_process_seen_in_nvidia_smi(nvidia_smi_load) or _current_process_seen_in_nvidia_smi(nvidia_smi_after)
    char_lines = [
        f"- `{char}`: raw={char in raw_transcript}, cleaned={char in cleaned_transcript}"
        for char in TURKISH_CHARS
    ]
    lines = [
        "# Full-Scale GPU ASR Test Report",
        "",
        f"Date: {started_at.date().isoformat()}",
        f"Status: `{status}`",
        "",
        "## Scope",
        "",
        "This report validates only the Collective MindGraph ASR/transcription path. It does not validate diarization, graph persistence, Ask Memory, extraction, semantic retrieval, or UI behavior.",
        "",
        "## Runtime Configuration",
        "",
        f"- Audio path: `{audio_path}`",
        f"- Audio duration: `{_format_float(audio_duration)}` seconds",
        f"- ASR backend: `{settings.asr_provider}`",
        f"- ASR model: `{settings.asr_model_name}`",
        f"- ASR device: `{settings.asr_device}`",
        f"- ASR compute type: `{settings.asr_compute_type}`",
        f"- ASR language: `{settings.default_language}`",
        f"- Runtime profile: `{settings.asr_runtime_profile}`",
        f"- VAD provider: `{settings.vad_provider}`",
        f"- Diarization enabled: `{settings.diarization_enabled}`",
        f"- Local LLM provider: `{settings.llm_provider}`",
        "",
        "## ASR Diagnostics",
        "",
        "```text",
        format_asr_diagnostics(diagnostics) if diagnostics else "[ASR diagnostics unavailable]",
        "```",
        "",
        "## Result",
        "",
        f"- Transcription time: `{_format_float(transcription_time)}` seconds",
        f"- Real-time factor: `{_format_float(real_time_factor)}`",
        f"- Segment count: `{segment_count if segment_count is not None else 'unknown'}`",
        f"- ASR status: `{metadata.get('asr_status')}`",
        f"- Mock fallback used: `{metadata.get('mock_fallback_used')}`",
        f"- GPU requested: `{metadata.get('gpu_requested', diagnostics.get('GPU requested by ASR'))}`",
        f"- GPU actually loaded: `{metadata.get('gpu_loaded', diagnostics.get('GPU actually loaded by ASR'))}`",
        f"- GPU fallback happened: `{metadata.get('gpu_fallback_happened', diagnostics.get('Fallback happened'))}`",
        f"- Fallback reason: `{metadata.get('gpu_fallback_reason', diagnostics.get('Fallback reason'))}`",
        f"- nvidia-smi observed this Python process: `{gpu_observed}`",
    ]
    if error:
        lines.extend(["", f"Error: `{error}`"])
    lines.extend(
        [
            "",
            "## Turkish Character Preservation Check",
            "",
            *char_lines,
            "",
            "## Raw Transcript",
            "",
            "```text",
            raw_transcript or "[not produced]",
            "```",
            "",
            "## Cleaned Transcript",
            "",
            "```text",
            cleaned_transcript or "[not produced]",
            "```",
            "",
            "## nvidia-smi Evidence",
            "",
            "After model load:",
            "",
            "```text",
            nvidia_smi_load.strip() or "[empty]",
            "```",
            "",
            "After transcription:",
            "",
            "```text",
            nvidia_smi_after.strip() or "[empty]",
            "```",
            "",
            "## Manual Observation Instructions",
            "",
            "Terminal 1:",
            "",
            "```cmd",
            "set CMG_RUNTIME_PROFILE=gpu_asr",
            "set CMG_GPU_ENABLED=1",
            "set CMG_REQUIRE_GPU=1",
            "set CMG_ASR_DEVICE=cuda",
            "set CMG_ASR_COMPUTE_TYPE=float16",
            "set CMG_ASR_MODEL=small",
            "set CMG_ASR_LANGUAGE=tr",
            "set CMG_EMBEDDING_DEVICE=cpu",
            "set PYTHONPATH=%CD%\\src;%CD%",
            "python scripts\\check_asr_gpu.py",
            "```",
            "",
            "Terminal 2:",
            "",
            "```cmd",
            "nvidia-smi -l 1",
            "```",
            "",
            "Expected if GPU is really used: a Python process appears under GPU processes, VRAM usage rises above idle, and GPU utilization may rise during transcription.",
            "",
            "Large-v3 full-scale mode after the small model GPU smoke test passes:",
            "",
            "```cmd",
            "set CMG_ASR_MODEL=large-v3",
            "python scripts\\full_scale_gpu_transcription_test.py --profile gpu_asr --audio recordings\\test.wav",
            "```",
            "",
            "## Pass/Fail Boundary",
            "",
            "- Pass requires the real CMG pipeline to load Faster-Whisper with `device=cuda`, `compute_type=float16`, `language=tr`, and transcribe real audio without mock fallback.",
            "- This report does not prove meeting-room readiness unless the audio is real meeting-room audio.",
        ]
    )
    return "\n".join(lines) + "\n"


def _capture_nvidia_smi() -> str:
    command = [
        "nvidia-smi",
        "--query-compute-apps=pid,process_name,used_memory",
        "--format=csv,noheader",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return "nvidia-smi not found on PATH"
    output = (result.stdout or "").strip()
    error = (result.stderr or "").strip()
    if result.returncode != 0:
        return error or f"nvidia-smi exited with code {result.returncode}"
    return output or "[no compute processes reported]"


def _current_process_seen_in_nvidia_smi(output: str) -> bool:
    return str(os.getpid()) in output


def _format_float(value: float | None) -> str:
    if value is None:
        return "unknown"
    return f"{value:.3f}"


def _resolve_repo_path(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def _write_report(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
