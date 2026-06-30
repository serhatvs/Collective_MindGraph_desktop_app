"""Compare CPU and GPU ASR runtime through the real CMG transcription pipeline."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from asr_benchmark_common import (
    REPO_ROOT,
    diagnostics_block,
    format_run_summary,
    format_seconds,
    run_pipeline_sync,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark CMG ASR on CPU and GPU for one local audio file.")
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--model", default="small")
    parser.add_argument("--vad-provider", default="energy")
    parser.add_argument("--language", default="tr")
    parser.add_argument("--quality-mode", default="max_quality")
    parser.add_argument(
        "--allow-gpu-fallback",
        action="store_true",
        help="Allow the GPU run to fall back to CPU. By default GPU fallback is treated as failure.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/dev/CPU_VS_GPU_ASR_BENCHMARK_REPORT.md"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = _resolve_repo_path(args.output)
    audio_path = args.audio.expanduser().resolve()

    if not audio_path.exists():
        report = _build_not_run_report(audio_path, args.model, "CPU_VS_GPU_ASR_BENCHMARK_NOT_RUN_NO_AUDIO")
        _write_report(output_path, report)
        print(f"Audio file not found: {audio_path}")
        print(f"Report written to {output_path}")
        return 1

    cpu = run_pipeline_sync(
        audio_path=audio_path,
        label="cpu",
        profile="cpu",
        model=args.model,
        vad_provider=args.vad_provider,
        language=args.language,
        quality_mode=args.quality_mode,
        require_gpu=False,
    )
    gpu = run_pipeline_sync(
        audio_path=audio_path,
        label="gpu",
        profile="gpu_asr",
        model=args.model,
        vad_provider=args.vad_provider,
        language=args.language,
        quality_mode=args.quality_mode,
        require_gpu=not args.allow_gpu_fallback,
    )

    status = "CPU_VS_GPU_ASR_BENCHMARK_RUN"
    if cpu.error or gpu.error:
        status = "CPU_VS_GPU_ASR_BENCHMARK_RUN_WITH_ERRORS"
    elif gpu.metadata.get("gpu_requested") and not gpu.metadata.get("gpu_loaded"):
        status = "CPU_VS_GPU_ASR_BENCHMARK_GPU_NOT_USED"

    report = _build_report(status=status, cpu=cpu, gpu=gpu)
    _write_report(output_path, report)
    print(f"Report written to {output_path}")
    return 0 if status == "CPU_VS_GPU_ASR_BENCHMARK_RUN" else 2


def _build_report(*, status: str, cpu, gpu) -> str:
    return "\n".join(
        [
            "# CPU vs GPU ASR Benchmark Report",
            "",
            f"Date: {datetime.now(tz=UTC).date().isoformat()}",
            f"Status: `{status}`",
            "",
            "## Claim Boundary",
            "",
            "This benchmark compares runtime behavior only. It does not claim transcription accuracy because no reference transcript is required or scored here.",
            "",
            "## Summary",
            "",
            f"- Audio path: `{cpu.audio_path}`",
            f"- Audio duration: `{format_seconds(cpu.audio_duration)}` seconds",
            f"- Model: `{cpu.model}`",
            f"- VAD provider: `{cpu.requested_vad_provider}`",
            f"- CPU transcription time: `{format_seconds(cpu.transcription_time_seconds)}` seconds",
            f"- GPU transcription time: `{format_seconds(gpu.transcription_time_seconds)}` seconds",
            f"- CPU real-time factor: `{format_seconds(cpu.real_time_factor)}`",
            f"- GPU real-time factor: `{format_seconds(gpu.real_time_factor)}`",
            f"- CPU segment count: `{cpu.segment_count}`",
            f"- GPU segment count: `{gpu.segment_count}`",
            f"- GPU fallback status: `{gpu.metadata.get('gpu_fallback_happened', gpu.diagnostics.get('Fallback happened'))}`",
            f"- GPU fallback reason: `{gpu.metadata.get('gpu_fallback_reason', gpu.diagnostics.get('Fallback reason'))}`",
            "",
            "## CPU Run",
            "",
            format_run_summary(cpu),
            "",
            "Diagnostics:",
            "",
            "```text",
            diagnostics_block(cpu),
            "```",
            "",
            "CPU transcript:",
            "",
            "```text",
            cpu.cleaned_transcript or cpu.raw_transcript or "[not produced]",
            "```",
            "",
            "## GPU Run",
            "",
            format_run_summary(gpu),
            "",
            "Diagnostics:",
            "",
            "```text",
            diagnostics_block(gpu),
            "```",
            "",
            "GPU transcript:",
            "",
            "```text",
            gpu.cleaned_transcript or gpu.raw_transcript or "[not produced]",
            "```",
            "",
            "## Errors And Warnings",
            "",
            f"- CPU error: `{cpu.error}`",
            f"- GPU error: `{gpu.error}`",
            f"- CPU warnings: `{cpu.warnings}`",
            f"- GPU warnings: `{gpu.warnings}`",
        ]
    ) + "\n"


def _build_not_run_report(audio_path: Path, model: str, status: str) -> str:
    return "\n".join(
        [
            "# CPU vs GPU ASR Benchmark Report",
            "",
            f"Date: {datetime.now(tz=UTC).date().isoformat()}",
            f"Status: `{status}`",
            "",
            f"Audio path: `{audio_path}`",
            f"Model: `{model}`",
            "",
            "No benchmark was run because the audio file was not found.",
        ]
    ) + "\n"


def _resolve_repo_path(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def _write_report(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
