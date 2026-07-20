"""Compare first-pass, full strong-pass, and selective retranscription modes."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "realtime_backend"
for import_path in (str(ROOT), str(BACKEND_ROOT)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from app.config import Settings  # noqa: E402
from app.evaluation.transcription_metrics import (  # noqa: E402
    compare_to_reference,
    evaluate_domain_terms,
)
from app.pipeline.orchestrator import TranscriptionPipeline  # noqa: E402
from app.pipeline.transcription_glossary import resolve_transcription_glossary  # noqa: E402


AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac"}
DEFAULT_OUTPUT = ROOT / "docs" / "dev" / "SELECTIVE_RETRANSCRIPTION_REPORT.md"


@dataclass(slots=True)
class BenchmarkRun:
    audio_path: Path
    mode: str
    profile: str
    reference_path: Path | None
    reference_text: str | None
    raw_text: str = ""
    selected_text: str = ""
    processing_time_seconds: float = 0.0
    audio_duration_seconds: float | None = None
    real_time_factor: float | None = None
    confidence_estimate: int | None = None
    candidate_scores: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    retranscribed_regions: int = 0
    percentage_audio_retranscribed: float = 0.0
    metrics: dict[str, Any] | None = None
    domain_term_accuracy: float | None = None
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path, help="One audio file or a directory of audio files.")
    parser.add_argument(
        "--reference",
        type=Path,
        help="Optional reference transcript file, or directory containing same-stem .txt files.",
    )
    parser.add_argument("--first-pass-profile", default="balanced")
    parser.add_argument("--second-pass-profile", default="selective_recovery")
    parser.add_argument("--glossary-file", type=Path)
    parser.add_argument("--language", default="tr")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    audio_paths = discover_audio(args.audio)
    if not audio_paths:
        raise SystemExit(f"No supported audio files found at: {args.audio}")
    glossary_path = args.glossary_file.expanduser().resolve() if args.glossary_file else None
    if glossary_path and not glossary_path.exists():
        raise SystemExit(f"Glossary file not found: {glossary_path}")

    runs: list[BenchmarkRun] = []
    for audio_path in audio_paths:
        reference_path = resolve_reference(audio_path, args.reference, single_audio=len(audio_paths) == 1)
        reference_text = reference_path.read_text(encoding="utf-8").strip() if reference_path else None
        domain_terms = resolve_domain_terms(glossary_path)
        configurations = [
            ("first_pass_only", args.first_pass_profile, False),
            ("full_recording_strong_pass", args.second_pass_profile, False),
            ("selective_retranscription", args.first_pass_profile, True),
        ]
        for mode, profile, selective_enabled in configurations:
            runs.append(
                await run_configuration(
                    audio_path=audio_path,
                    mode=mode,
                    profile=profile,
                    second_pass_profile=args.second_pass_profile,
                    selective_enabled=selective_enabled,
                    language=args.language,
                    glossary_path=glossary_path,
                    reference_path=reference_path,
                    reference_text=reference_text,
                    domain_terms=domain_terms,
                )
            )

    output_path = args.output.expanduser()
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_report(runs), encoding="utf-8")
    print(f"Wrote report: {output_path.resolve()}")
    return 1 if any(run.error for run in runs) else 0


async def run_configuration(
    *,
    audio_path: Path,
    mode: str,
    profile: str,
    second_pass_profile: str,
    selective_enabled: bool,
    language: str,
    glossary_path: Path | None,
    reference_path: Path | None,
    reference_text: str | None,
    domain_terms: list[str],
) -> BenchmarkRun:
    run = BenchmarkRun(
        audio_path=audio_path,
        mode=mode,
        profile=profile,
        reference_path=reference_path,
        reference_text=reference_text,
    )
    settings = Settings()
    settings.asr_provider = "faster_whisper"
    settings.default_language = language
    settings.transcription_quality_mode = profile
    settings.selective_retranscription_enabled = selective_enabled
    settings.selective_retranscription_profile = second_pass_profile
    settings.transcription_project_glossary_path = glossary_path
    settings.allow_remote_download = False
    settings.diarization_enabled = False
    settings.diarizer_provider = "fallback"
    settings.llm_provider = "disabled"
    settings.enable_summary = False

    started = time.perf_counter()
    try:
        pipeline = TranscriptionPipeline(settings)
        transcript = await pipeline.process_audio_path(
            audio_path,
            source=f"benchmark_selective_retranscription_{mode}",
            language=language,
            quality_mode=profile,
            include_summary=False,
            debug=False,
        )
        run.raw_text = "\n".join(segment.raw_text for segment in transcript.segments).strip()
        run.selected_text = "\n".join(segment.corrected_text for segment in transcript.segments).strip()
        metadata = dict(transcript.metadata)
        if metadata.get("mock_fallback_used"):
            raise RuntimeError("ASR_STATUS=MOCK_FALLBACK invalidates this benchmark run")
        run.confidence_estimate = _optional_int(metadata.get("transcription_confidence_estimate"))
        run.warnings = [str(item) for item in metadata.get("warnings", [])]
        audio_metadata = metadata.get("asr_input_audio")
        if isinstance(audio_metadata, dict):
            run.audio_duration_seconds = _optional_float(audio_metadata.get("duration_seconds"))
        selective_metadata = metadata.get("selective_retranscription")
        if isinstance(selective_metadata, dict):
            run.retranscribed_regions = int(selective_metadata.get("number_of_second_pass_regions") or 0)
            run.percentage_audio_retranscribed = float(
                selective_metadata.get("percentage_of_audio_retranscribed") or 0.0
            )
            regions = selective_metadata.get("regions")
            if isinstance(regions, list):
                run.candidate_scores = [
                    {
                        "first_pass_score": item.get("first_pass_score"),
                        "second_pass_score": item.get("second_pass_score"),
                        "score_difference": item.get("score_difference"),
                        "selected_pass": item.get("selected_pass"),
                        "selection_reason": item.get("selection_reason"),
                    }
                    for item in regions
                    if isinstance(item, dict)
                ]
        if reference_text is not None:
            run.metrics = compare_to_reference(reference_text, run.selected_text)
            run.domain_term_accuracy = calculate_domain_term_accuracy(
                reference_text,
                run.selected_text,
                domain_terms,
            )
    except Exception as exc:
        run.error = f"{type(exc).__name__}: {exc}"
    run.processing_time_seconds = time.perf_counter() - started
    if run.audio_duration_seconds and run.audio_duration_seconds > 0.0:
        run.real_time_factor = run.processing_time_seconds / run.audio_duration_seconds
    return run


def discover_audio(path: Path) -> list[Path]:
    resolved = path.expanduser().resolve()
    if resolved.is_file() and resolved.suffix.lower() in AUDIO_EXTENSIONS:
        return [resolved]
    if not resolved.is_dir():
        return []
    return sorted(item for item in resolved.rglob("*") if item.is_file() and item.suffix.lower() in AUDIO_EXTENSIONS)


def resolve_reference(audio_path: Path, reference: Path | None, *, single_audio: bool) -> Path | None:
    if reference is not None:
        resolved = reference.expanduser().resolve()
        if resolved.is_file() and single_audio:
            return resolved
        if resolved.is_dir():
            candidate = resolved / f"{audio_path.stem}.txt"
            return candidate if candidate.exists() else None
    candidate = audio_path.with_suffix(".txt")
    return candidate if candidate.exists() else None


def resolve_domain_terms(glossary_path: Path | None) -> list[str]:
    if glossary_path is None:
        return []
    settings = Settings(
        transcription_project_glossary_path=glossary_path,
        transcription_glossary_max_terms=10_000,
        transcription_glossary_max_prompt_chars=1_000_000,
    )
    resolved = resolve_transcription_glossary(settings)
    return list(resolved.terms)


def calculate_domain_term_accuracy(reference: str, hypothesis: str, terms: list[str]) -> float | None:
    result = evaluate_domain_terms(reference, hypothesis, terms)
    return result.accuracy if result else None


def build_report(runs: list[BenchmarkRun]) -> str:
    references_available = any(run.reference_text is not None for run in runs)
    lines = [
        "# Selective Retranscription Benchmark Report",
        "",
        (
            "Candidate scores and confidence estimates are not accuracy. Reference-based WER/CER are included for runs with a human transcript."
            if references_available
            else "Candidate scores and confidence estimates are not accuracy. No reference-based metrics are reported because no human transcript was supplied."
        ),
        "",
    ]
    if references_available:
        lines.extend(
            [
                "| File | Mode | Profile | Time | RTF | Regions | Audio Retranscribed | WER | CER | Domain Terms | Error |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for run in runs:
            metrics = run.metrics or {}
            lines.append(
                f"| `{run.audio_path.name}` | `{run.mode}` | `{run.profile}` | "
                f"{run.processing_time_seconds:.3f}s | {_metric(run.real_time_factor)} | "
                f"{run.retranscribed_regions} | {run.percentage_audio_retranscribed:.2f}% | "
                f"{_metric(metrics.get('wer'))} | {_metric(metrics.get('cer'))} | "
                f"{_metric(run.domain_term_accuracy)} | {run.error or '-'} |"
            )
    else:
        lines.extend(
            [
                "| File | Mode | Profile | Time | RTF | Regions | Audio Retranscribed | Confidence Estimate | Warnings | Error |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
            ]
        )
        for run in runs:
            lines.append(
                f"| `{run.audio_path.name}` | `{run.mode}` | `{run.profile}` | "
                f"{run.processing_time_seconds:.3f}s | {_metric(run.real_time_factor)} | "
                f"{run.retranscribed_regions} | {run.percentage_audio_retranscribed:.2f}% | "
                f"{run.confidence_estimate if run.confidence_estimate is not None else '-'} | "
                f"{', '.join(run.warnings[:4]) or '-'} | {run.error or '-'} |"
            )

    lines.extend(["", "## Detailed Runs", ""])
    for run in runs:
        lines.extend(
            [
                f"### {run.audio_path.name} / {run.mode}",
                "",
                f"- Profile: `{run.profile}`",
                f"- Reference: `{run.reference_path}`",
                f"- Processing time: `{run.processing_time_seconds:.3f}s`",
                f"- Real-time factor: `{_metric(run.real_time_factor)}`",
                f"- Retranscribed regions: `{run.retranscribed_regions}`",
                f"- Percentage of audio retranscribed: `{run.percentage_audio_retranscribed:.2f}%`",
                f"- Confidence estimate: `{run.confidence_estimate}`",
                f"- Candidate scores: `{json.dumps(run.candidate_scores, ensure_ascii=False)}`",
                f"- Warnings: `{run.warnings}`",
                f"- Error: `{run.error}`",
            ]
        )
        if run.reference_text is not None:
            metrics = run.metrics or {}
            lines.extend(
                [
                    f"- WER: `{_metric(metrics.get('wer'))}`",
                    f"- CER: `{_metric(metrics.get('cer'))}`",
                    f"- Domain term accuracy: `{_metric(run.domain_term_accuracy)}`",
                    f"- Substitutions: `{metrics.get('notable_substitutions', [])}`",
                    f"- Deletions: `{metrics.get('notable_deletions', [])}`",
                    f"- Insertions: `{metrics.get('notable_insertions', [])}`",
                ]
            )
        lines.extend(["", "Selected candidate text:", "", "```text", run.selected_text, "```", ""])
    return "\n".join(lines).rstrip() + "\n"


def _metric(value: object) -> str:
    numeric = _optional_float(value)
    return "-" if numeric is None else f"{numeric:.4f}"


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    numeric = _optional_float(value)
    return None if numeric is None else int(round(numeric))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
