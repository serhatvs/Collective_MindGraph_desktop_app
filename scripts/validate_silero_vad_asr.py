"""Validate VAD choices as separate ASR pipeline components."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from asr_benchmark_common import (
    REPO_ROOT,
    diagnostics_block,
    format_run_summary,
    format_seconds,
    provider_status,
    run_pipeline_sync,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate EnergyVAD, SileroVAD, and no-VAD ASR paths.")
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--model", default="small")
    parser.add_argument("--profile", choices=["cpu", "gpu_asr"], default="gpu_asr")
    parser.add_argument("--language", default="tr")
    parser.add_argument("--quality-mode", default="max_quality")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/reports/2026-06-30/gpu-asr/SILERO_VAD_ASR_VALIDATION_REPORT.md"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = _resolve_repo_path(args.output)
    audio_path = args.audio.expanduser().resolve()

    if not audio_path.exists():
        _write_report(output_path, _not_run_report(audio_path, args.model))
        print(f"Audio file not found: {audio_path}")
        print(f"Report written to {output_path}")
        return 1

    require_gpu = args.profile == "gpu_asr"
    runs = [
        run_pipeline_sync(
            audio_path=audio_path,
            label="energy_vad",
            profile=args.profile,
            model=args.model,
            vad_provider="energy",
            language=args.language,
            quality_mode=args.quality_mode,
            require_gpu=require_gpu,
        ),
        run_pipeline_sync(
            audio_path=audio_path,
            label="silero_vad",
            profile=args.profile,
            model=args.model,
            vad_provider="silero",
            language=args.language,
            quality_mode=args.quality_mode,
            require_gpu=require_gpu,
        ),
        run_pipeline_sync(
            audio_path=audio_path,
            label="no_vad",
            profile=args.profile,
            model=args.model,
            vad_provider="none",
            language=args.language,
            quality_mode=args.quality_mode,
            require_gpu=require_gpu,
        ),
    ]

    status = "SILERO_VAD_ASR_VALIDATION_RUN"
    if any(run.error for run in runs):
        status = "SILERO_VAD_ASR_VALIDATION_RUN_WITH_ERRORS"
    report = _build_report(status, runs)
    _write_report(output_path, report)
    print(f"Report written to {output_path}")
    return 0 if status == "SILERO_VAD_ASR_VALIDATION_RUN" else 2


def _build_report(status: str, runs: list) -> str:
    audio_path = runs[0].audio_path if runs else None
    audio_duration = runs[0].audio_duration if runs else None
    lines = [
        "# Silero VAD ASR Validation Report",
        "",
        f"Date: {datetime.now(tz=UTC).date().isoformat()}",
        f"Status: `{status}`",
        "",
        "## Scope",
        "",
        "This report validates VAD behavior as a separate ASR component. It does not make Silero a requirement for GPU ASR and does not involve diarization.",
        "",
        "## Summary",
        "",
        f"- Audio path: `{audio_path}`",
        f"- Audio duration: `{format_seconds(audio_duration)}` seconds",
        "",
        "| Requested VAD | Actual VAD | Status | Speech Segments | ASR GPU Used | Time | Error |",
        "|---|---|---|---:|---|---:|---|",
    ]
    for run in runs:
        lines.append(
            f"| {run.requested_vad_provider} | {run.actual_vad_provider} | "
            f"{provider_status(run.requested_vad_provider, run.actual_vad_provider, run.error)} | "
            f"{run.speech_region_count} | {run.metadata.get('gpu_loaded', run.diagnostics.get('GPU actually loaded by ASR'))} | "
            f"{format_seconds(run.transcription_time_seconds)} | {run.error or ''} |"
        )

    for run in runs:
        lines.extend(
            [
                "",
                f"## {run.label}",
                "",
                format_run_summary(run),
                "",
                "Speech region timestamps:",
                "",
                "```text",
                _format_regions(run.speech_regions),
                "```",
                "",
                "Diagnostics:",
                "",
                "```text",
                diagnostics_block(run),
                "```",
                "",
                "Transcription result:",
                "",
                "```text",
                run.cleaned_transcript or run.raw_transcript or "[not produced]",
                "```",
            ]
        )
    return "\n".join(lines) + "\n"


def _format_regions(regions: list[tuple[float, float]]) -> str:
    if not regions:
        return "[no VAD speech regions]"
    return "\n".join(f"{start:.3f} -> {end:.3f}" for start, end in regions)


def _not_run_report(audio_path: Path, model: str) -> str:
    return "\n".join(
        [
            "# Silero VAD ASR Validation Report",
            "",
            f"Date: {datetime.now(tz=UTC).date().isoformat()}",
            "Status: `SILERO_VAD_ASR_VALIDATION_NOT_RUN_NO_AUDIO`",
            "",
            f"Audio path: `{audio_path}`",
            f"Model: `{model}`",
            "",
            "No validation was run because the audio file was not found.",
        ]
    ) + "\n"


def _resolve_repo_path(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def _write_report(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
