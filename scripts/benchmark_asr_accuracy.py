"""Compute WER/CER for CMG ASR only when a real reference transcript is provided."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from asr_benchmark_common import (
    REPO_ROOT,
    character_error_rate,
    diagnostics_block,
    format_run_summary,
    format_seconds,
    run_pipeline_sync,
    should_score_accuracy,
    word_error_rate,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark CMG ASR accuracy against a human reference transcript.")
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--profile", choices=["cpu", "gpu_asr"], default="gpu_asr")
    parser.add_argument("--model", default="small")
    parser.add_argument("--vad-provider", default="energy")
    parser.add_argument("--language", default="tr")
    parser.add_argument("--quality-mode", default="max_quality")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/dev/ASR_ACCURACY_BENCHMARK_REPORT.md"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = _resolve_repo_path(args.output)
    audio_path = args.audio.expanduser().resolve()
    reference_path = args.reference.expanduser().resolve() if args.reference else None

    if not audio_path.exists():
        _write_report(
            output_path,
            _not_run_report("ASR_ACCURACY_BENCHMARK_NOT_RUN_NO_AUDIO", audio_path, reference_path),
        )
        print(f"Audio file not found: {audio_path}")
        print(f"Report written to {output_path}")
        return 1

    reference_text = None
    scoring_enabled = should_score_accuracy(reference_path)
    if scoring_enabled and reference_path is not None:
        reference_text = reference_path.read_text(encoding="utf-8").strip()

    run = run_pipeline_sync(
        audio_path=audio_path,
        label="accuracy",
        profile=args.profile,
        model=args.model,
        vad_provider=args.vad_provider,
        language=args.language,
        quality_mode=args.quality_mode,
        require_gpu=args.profile == "gpu_asr",
    )

    wer = None
    cer = None
    if scoring_enabled and reference_text is not None:
        hypothesis = run.cleaned_transcript or run.raw_transcript
        wer = word_error_rate(reference_text, hypothesis)
        cer = character_error_rate(reference_text, hypothesis)

    status = "ASR_ACCURACY_BENCHMARK_RUN"
    if run.error:
        status = "ASR_ACCURACY_BENCHMARK_RUN_WITH_ERRORS"
    elif not scoring_enabled:
        status = "ASR_ACCURACY_BENCHMARK_RUNTIME_ONLY_NO_REFERENCE"

    report = _build_report(
        status=status,
        run=run,
        reference_path=reference_path,
        reference_text=reference_text,
        wer=wer,
        cer=cer,
        scoring_enabled=scoring_enabled,
    )
    _write_report(output_path, report)
    print(f"Report written to {output_path}")
    return 0 if not run.error else 2


def _build_report(
    *,
    status: str,
    run,
    reference_path: Path | None,
    reference_text: str | None,
    wer: float | None,
    cer: float | None,
    scoring_enabled: bool,
) -> str:
    return "\n".join(
        [
            "# ASR Accuracy Benchmark Report",
            "",
            f"Date: {datetime.now(tz=UTC).date().isoformat()}",
            f"Status: `{status}`",
            "",
            "## Claim Boundary",
            "",
            "WER/CER are computed only when a real human reference transcript is provided. No keyword-overlap accuracy percentage is produced.",
            "",
            "## Runtime Metrics",
            "",
            format_run_summary(run),
            f"- Audio path: `{run.audio_path}`",
            f"- Audio duration: `{format_seconds(run.audio_duration)}` seconds",
            f"- Reference path: `{reference_path}`",
            f"- Reference transcript provided: `{scoring_enabled}`",
            f"- WER: `{_format_metric(wer)}`",
            f"- CER: `{_format_metric(cer)}`",
            "",
            "Diagnostics:",
            "",
            "```text",
            diagnostics_block(run),
            "```",
            "",
            "## Reference Transcript",
            "",
            "```text",
            reference_text or "[not provided]",
            "```",
            "",
            "## Raw Transcript",
            "",
            "```text",
            run.raw_transcript or "[not produced]",
            "```",
            "",
            "## Cleaned Transcript",
            "",
            "```text",
            run.cleaned_transcript or "[not produced]",
            "```",
            "",
            "## Accuracy Scoring Status",
            "",
            (
                "WER/CER were computed against the provided reference transcript."
                if scoring_enabled
                else "WER/CER were not computed because no real reference transcript was provided."
            ),
        ]
    ) + "\n"


def _not_run_report(status: str, audio_path: Path, reference_path: Path | None) -> str:
    return "\n".join(
        [
            "# ASR Accuracy Benchmark Report",
            "",
            f"Date: {datetime.now(tz=UTC).date().isoformat()}",
            f"Status: `{status}`",
            "",
            f"Audio path: `{audio_path}`",
            f"Reference path: `{reference_path}`",
            "",
            "No benchmark was run because the audio file was not found.",
        ]
    ) + "\n"


def _format_metric(value: float | None) -> str:
    return "not computed" if value is None else f"{value:.4f}"


def _resolve_repo_path(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def _write_report(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
