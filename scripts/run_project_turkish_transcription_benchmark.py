"""Run a local Turkish project transcription benchmark.

This script compares Faster-Whisper model/profile combinations on one local
audio file and writes a Markdown report. It intentionally does not call cloud
APIs and treats MockASR fallback as invalid benchmark output.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import wave
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REALTIME_BACKEND_ROOT = REPO_ROOT / "realtime_backend"
sys.path.insert(0, str(REALTIME_BACKEND_ROOT))

from app.evaluation.transcription_metrics import (  # noqa: E402
    NormalizationPolicy,
    compare_to_reference as _shared_compare_to_reference,
    edit_distance_with_operations,
    normalize_text as _shared_normalize_text,
)

MOCK_FALLBACK_STATUS = "ASR_STATUS=MOCK_FALLBACK"
TURKISH_CHARS = ["\u00e7", "\u011f", "\u0131", "\u0130", "\u00f6", "\u015f", "\u00fc"]
AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus", ".aac", ".wma"}
REFERENCE_EXTENSIONS = [".txt", ".transcript.txt", ".reference.txt", ".lab", ".srt", ".vtt"]
TECHNICAL_TERMS = [
    "Collective MindGraph",
    "FastAPI",
    "SQLite",
    "PySide6",
    "VAD",
    "transcript",
    "aksiyon",
    "karar",
]


@dataclass(frozen=True, slots=True)
class BenchmarkSample:
    sample_id: str
    audio_path: Path
    reference_path: Path | None
    reference_text: str | None


@dataclass(slots=True)
class BenchmarkResult:
    sample_id: str
    audio_path: Path
    reference_path: Path | None
    reference_text: str | None
    model_name: str
    profile: str
    asr_status: str | None
    mock_fallback_used: bool
    preprocessing_status: str | None
    vad_provider: str | None
    beam_size: int | None
    compute_type: str | None
    processing_time_seconds: float | None
    raw_transcript: str
    cleaned_transcript: str
    metadata: dict[str, Any]
    raw_metrics: dict[str, Any] | None
    cleaned_metrics: dict[str, Any] | None
    turkish_chars: dict[str, dict[str, bool]]
    technical_terms: dict[str, dict[str, bool]]
    vad_clipping_notes: list[str]
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark local Faster-Whisper Turkish transcription on project audio."
    )
    parser.add_argument("--audio", type=Path, help="Path to one local Turkish audio file.")
    parser.add_argument("--dataset-root", type=Path, help="External dataset root to scan for Turkish audio.")
    parser.add_argument("--max-files", type=int, default=5, help="Maximum dataset files to benchmark.")
    parser.add_argument("--dataset-name", default="project_turkish", help="Dataset label for report output.")
    parser.add_argument("--reference", type=Path, help="Optional human reference transcript.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Markdown report output path.",
    )
    parser.add_argument("--models", nargs="+", default=["large-v3", "large-v3-turbo"])
    parser.add_argument("--profiles", nargs="+", default=["max_quality", "balanced"])
    parser.add_argument(
        "--audio-kind",
        choices=["real_meeting_room", "test_speech", "noisy_room", "overlap_sample", "unknown"],
        default="unknown",
        help="Describe whether the audio is a real meeting-room recording or test speech.",
    )
    parser.add_argument("--device", default=os.getenv("CMG_RT_ASR_DEVICE", "cuda"))
    parser.add_argument("--compute-type", default=os.getenv("CMG_RT_ASR_COMPUTE_TYPE", "float16"))
    parser.add_argument("--vad-provider", default="silero")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failed config.")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    _force_local_only_environment()
    configure_logging = _load_configure_logging()
    configure_logging("INFO")

    if args.dataset_root and args.audio:
        raise SystemExit("Use either --dataset-root or --audio, not both.")
    if not args.dataset_root and not args.audio:
        raise SystemExit("Provide --dataset-root for a dataset subset or --audio for one file.")

    dataset_root = args.dataset_root.resolve() if args.dataset_root else None
    dataset_audio_count = 1
    if dataset_root:
        if not dataset_root.exists():
            raise SystemExit(f"Dataset root not found: {dataset_root}")
        all_samples = discover_dataset_samples(dataset_root)
        dataset_audio_count = len(all_samples)
        samples = all_samples[: max(args.max_files, 0)]
        if not samples:
            raise SystemExit(f"No supported audio files found under dataset root: {dataset_root}")
        default_output = Path("docs/reports/2026-06-30/transcription-benchmarks/MEDIASPEECH_TR_TRANSCRIPTION_BENCHMARK.md")
        default_audio_kind = args.audio_kind if args.audio_kind != "unknown" else "test_speech"
    else:
        audio_path = args.audio.resolve()
        reference_path = args.reference.resolve() if args.reference else None
        if not audio_path.exists():
            raise SystemExit(f"Audio file not found: {audio_path}")
        if reference_path and not reference_path.exists():
            raise SystemExit(f"Reference transcript not found: {reference_path}")
        reference_text = reference_path.read_text(encoding="utf-8").strip() if reference_path else None
        samples = [
            BenchmarkSample(
                sample_id=audio_path.stem,
                audio_path=audio_path,
                reference_path=reference_path,
                reference_text=reference_text,
            )
        ]
        default_output = Path("docs/reports/2026-06-30/transcription-benchmarks/PROJECT_TURKISH_TRANSCRIPTION_BENCHMARK.md")
        default_audio_kind = args.audio_kind

    output_arg = args.output or default_output
    output_path = (REPO_ROOT / output_arg).resolve() if not output_arg.is_absolute() else output_arg
    results: list[BenchmarkResult] = []

    for model_name in args.models:
        for profile in args.profiles:
            for sample in samples:
                try:
                    result = await run_single_config(
                        sample=sample,
                        model_name=model_name,
                        profile=profile,
                        device=args.device,
                        compute_type=args.compute_type,
                        vad_provider=args.vad_provider,
                    )
                except Exception as exc:
                    result = build_error_result(
                        sample=sample,
                        model_name=model_name,
                        profile=profile,
                        compute_type=args.compute_type,
                        error=exc,
                    )
                    if args.fail_fast:
                        results.append(result)
                        write_report(
                            output_path=output_path,
                            dataset_name=args.dataset_name,
                            dataset_root=dataset_root,
                            dataset_audio_count=dataset_audio_count,
                            samples=samples,
                            audio_kind=default_audio_kind,
                            results=results,
                        )
                        raise
                results.append(result)

    write_report(
        output_path=output_path,
        dataset_name=args.dataset_name,
        dataset_root=dataset_root,
        dataset_audio_count=dataset_audio_count,
        samples=samples,
        audio_kind=default_audio_kind,
        results=results,
    )
    print(f"Benchmark report written to {output_path}")
    if any(result.mock_fallback_used or result.asr_status == MOCK_FALLBACK_STATUS for result in results):
        return 2
    if any(result.error and MOCK_FALLBACK_STATUS in result.error for result in results):
        return 2
    if any(result.error for result in results):
        return 1
    return 0


async def run_single_config(
    *,
    sample: BenchmarkSample,
    model_name: str,
    profile: str,
    device: str,
    compute_type: str,
    vad_provider: str,
) -> BenchmarkResult:
    Settings, TranscriptionPipeline = _load_backend_types()
    settings = Settings()
    settings.asr_provider = "faster_whisper"
    settings.asr_model_name = model_name
    settings.asr_device = device
    settings.asr_compute_type = compute_type
    settings.transcription_quality_mode = profile
    settings.default_language = "tr"
    settings.transcript_cleanup_mode = "conservative"
    settings.asr_internal_vad_enabled = False
    settings.asr_word_timestamps = True
    settings.asr_condition_on_previous_text = False
    settings.vad_provider = vad_provider
    settings.llm_provider = "none"
    settings.enable_summary = False
    settings.diarization_enabled = False
    settings.allow_remote_access = False
    settings.allow_remote_download = False
    settings.ensure_directories()

    pipeline = TranscriptionPipeline(settings)
    transcript = await pipeline.process_audio_path(
        sample.audio_path,
        source="project_turkish_benchmark",
        language="tr",
        quality_mode=profile,
        include_summary=False,
        debug=True,
    )

    metadata = dict(transcript.metadata)
    asr_status = metadata.get("asr_status")
    mock_fallback_used = bool(metadata.get("mock_fallback_used"))
    if asr_status == MOCK_FALLBACK_STATUS or mock_fallback_used:
        raise RuntimeError(f"Invalid benchmark output: {MOCK_FALLBACK_STATUS}")

    raw_transcript = "\n".join(segment.raw_text for segment in transcript.segments).strip()
    cleaned_transcript = "\n".join(segment.corrected_text for segment in transcript.segments).strip()

    return BenchmarkResult(
        sample_id=sample.sample_id,
        audio_path=sample.audio_path,
        reference_path=sample.reference_path,
        reference_text=sample.reference_text,
        model_name=model_name,
        profile=profile,
        asr_status=asr_status,
        mock_fallback_used=mock_fallback_used,
        preprocessing_status=metadata.get("preprocessing_status"),
        vad_provider=metadata.get("vad_provider"),
        beam_size=_as_int(metadata.get("beam_size")),
        compute_type=metadata.get("compute_type"),
        processing_time_seconds=_as_float(metadata.get("processing_time_seconds")),
        raw_transcript=raw_transcript,
        cleaned_transcript=cleaned_transcript,
        metadata=metadata,
        raw_metrics=compare_to_reference(sample.reference_text, raw_transcript) if sample.reference_text else None,
        cleaned_metrics=compare_to_reference(sample.reference_text, cleaned_transcript) if sample.reference_text else None,
        turkish_chars=check_turkish_characters(raw_transcript, cleaned_transcript),
        technical_terms=check_technical_terms(raw_transcript, cleaned_transcript),
        vad_clipping_notes=build_vad_clipping_notes(transcript, metadata),
    )


def discover_dataset_samples(dataset_root: Path) -> list[BenchmarkSample]:
    audio_files = sorted(
        path
        for path in dataset_root.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )
    samples: list[BenchmarkSample] = []
    for audio_path in audio_files:
        reference_path = find_reference_for_audio(audio_path)
        reference_text = reference_path.read_text(encoding="utf-8").strip() if reference_path else None
        try:
            sample_id = str(audio_path.relative_to(dataset_root).with_suffix(""))
        except ValueError:
            sample_id = audio_path.stem
        samples.append(
            BenchmarkSample(
                sample_id=sample_id.replace("\\", "/"),
                audio_path=audio_path.resolve(),
                reference_path=reference_path.resolve() if reference_path else None,
                reference_text=reference_text,
            )
        )
    return samples


def find_reference_for_audio(audio_path: Path) -> Path | None:
    candidates = [audio_path.with_suffix(".txt")]
    candidates.extend(audio_path.with_suffix(suffix) for suffix in REFERENCE_EXTENSIONS)
    candidates.extend(audio_path.parent.glob(f"{audio_path.stem}*.txt"))
    for candidate in candidates:
        if candidate.exists() and candidate.is_file() and candidate != audio_path:
            return candidate
    return None


def build_error_result(
    *,
    sample: BenchmarkSample,
    model_name: str,
    profile: str,
    compute_type: str,
    error: Exception,
) -> BenchmarkResult:
    return BenchmarkResult(
        sample_id=sample.sample_id,
        audio_path=sample.audio_path,
        reference_path=sample.reference_path,
        reference_text=sample.reference_text,
        model_name=model_name,
        profile=profile,
        asr_status=None,
        mock_fallback_used=False,
        preprocessing_status=None,
        vad_provider=None,
        beam_size=None,
        compute_type=compute_type,
        processing_time_seconds=None,
        raw_transcript="",
        cleaned_transcript="",
        metadata={},
        raw_metrics=None,
        cleaned_metrics=None,
        turkish_chars={},
        technical_terms={},
        vad_clipping_notes=[],
        error=f"{type(error).__name__}: {error}",
    )


def compare_to_reference(reference: str | None, candidate: str) -> dict[str, Any] | None:
    return _shared_compare_to_reference(reference, candidate)


def tokenize_words(text: str) -> list[str]:
    normalized = normalize_for_metric(text)
    return normalized.split() if normalized else []


def normalize_for_metric(text: str) -> str:
    return _shared_normalize_text(text, NormalizationPolicy())


def edit_distance_with_ops(reference: list[str], candidate: list[str]) -> tuple[int, dict[str, list[Any]]]:
    return edit_distance_with_operations(reference, candidate)


def check_turkish_characters(raw_text: str, cleaned_text: str) -> dict[str, dict[str, bool]]:
    return {
        char: {
            "raw": char in raw_text,
            "cleaned": char in cleaned_text,
        }
        for char in TURKISH_CHARS
    }


def check_technical_terms(raw_text: str, cleaned_text: str) -> dict[str, dict[str, bool]]:
    raw_folded = raw_text.casefold()
    cleaned_folded = cleaned_text.casefold()
    return {
        term: {
            "raw": term.casefold() in raw_folded,
            "cleaned": term.casefold() in cleaned_folded,
        }
        for term in TECHNICAL_TERMS
    }


def build_vad_clipping_notes(transcript: Any, metadata: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    duration = None
    input_audio = metadata.get("asr_input_audio")
    if isinstance(input_audio, dict):
        duration = _as_float(input_audio.get("duration_seconds"))
    if duration is None and transcript.diagnostics is not None:
        duration = transcript.diagnostics.audio_duration

    vad_regions = transcript.debug.vad_regions if transcript.debug else []
    if not vad_regions:
        return ["No VAD speech regions were returned; inspect audio manually."]

    first_region = vad_regions[0]
    last_region = vad_regions[-1]
    if first_region.start > 0.5:
        notes.append(f"First VAD region starts at {first_region.start:.2f}s; verify no opening word was clipped.")
    if duration is not None and duration - last_region.end > 0.5:
        notes.append(
            f"Last VAD region ends {duration - last_region.end:.2f}s before audio end; verify no closing word was clipped."
        )
    if len(vad_regions) > 20:
        notes.append(f"VAD produced {len(vad_regions)} regions; inspect for over-segmentation.")
    if not notes:
        notes.append("No obvious clipping signal from simple VAD boundary heuristics; manual listening still required.")
    return notes


def audio_duration_seconds(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as handle:
            frame_rate = handle.getframerate()
            return handle.getnframes() / frame_rate if frame_rate else None
    except (wave.Error, OSError):
        pass

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return _as_float(result.stdout.strip())


def write_report(
    *,
    output_path: Path,
    dataset_name: str,
    dataset_root: Path | None,
    dataset_audio_count: int,
    samples: list[BenchmarkSample],
    audio_kind: str,
    results: list[BenchmarkResult],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(
        dataset_name=dataset_name,
        dataset_root=dataset_root,
        dataset_audio_count=dataset_audio_count,
        samples=samples,
        audio_kind=audio_kind,
        results=results,
    )
    output_path.write_text(report, encoding="utf-8")


def build_report(
    *,
    dataset_name: str,
    dataset_root: Path | None,
    dataset_audio_count: int,
    samples: list[BenchmarkSample],
    audio_kind: str,
    results: list[BenchmarkResult],
) -> str:
    reference_count = sum(1 for sample in samples if sample.reference_text)
    reference_exists = reference_count > 0
    status = "BENCHMARK_RUN" if results and any(not result.error for result in results) else "BENCHMARK_ATTEMPTED_WITH_ERRORS"
    best_config = choose_recommended_config(results, reference_exists)
    lines = [
        f"# {dataset_name} Turkish Transcription Benchmark",
        "",
        f"Date: {datetime.now(tz=UTC).date().isoformat()}",
        "",
        f"Status: {status}",
        "",
        f"Dataset root path: `{dataset_root}`" if dataset_root else f"Dataset root path: single-file mode",
        f"Files discovered: {dataset_audio_count}",
        f"Files tested: {len(samples)}",
        f"Audio type: `{audio_kind}`",
        f"Human reference transcripts matched: {reference_count}/{len(samples)}",
        "",
        "Tested files:",
        "",
    ]
    for sample in samples:
        lines.append(
            f"- `{sample.audio_path}`"
            + (f" -> `{sample.reference_path}`" if sample.reference_path else " -> reference not found")
        )
    lines.extend(
        [
            "",
            "Claim boundary:",
            "",
            "- This dataset can support Turkish ASR/media-speech benchmarking.",
            "- This dataset must not be treated as proof of real meeting-room readiness.",
            "- Project-specific real meeting-room audio remains a separate required benchmark.",
            "",
            "Local-first controls:",
            "",
            "- Faster-Whisper only; no cloud STT.",
            "- `language=tr`.",
            "- `transcript_cleanup_mode=conservative`.",
            "- Faster-Whisper internal VAD disabled.",
            "- External VAD requested as `silero`.",
            "- `ASR_STATUS=MOCK_FALLBACK` invalidates the benchmark.",
            "",
            "## Configuration Summary",
            "",
            "| Model | Profile | Tested Files | Valid Results | Avg Time | Avg WER | Avg CER | Errors |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in aggregate_config_rows(results):
        lines.append(
            "| "
            f"{row['model']} | {row['profile']} | {row['tested']} | {row['valid']} | "
            f"{_format_seconds(row['avg_time'])} | {_format_metric(row['avg_wer'])} | "
            f"{_format_metric(row['avg_cer'])} | {row['errors']} |"
        )
    lines.extend(
        [
            "",
            "## Per-File Summary Table",
            "",
            "| Sample | Model | Profile | ASR Status | Mock Fallback | VAD | Beam | Compute | Preprocessing | Time | WER | CER | Error |",
            "|---|---|---|---|---|---|---:|---|---|---:|---:|---:|---|",
        ]
    )
    for result in results:
        metrics = result.cleaned_metrics or {}
        lines.append(
            "| "
            f"{result.sample_id} | {result.model_name} | {result.profile} | {result.asr_status or ''} | "
            f"{result.mock_fallback_used} | {result.vad_provider or ''} | {result.beam_size or ''} | "
            f"{result.compute_type or ''} | {result.preprocessing_status or ''} | "
            f"{_format_seconds(result.processing_time_seconds)} | {_format_metric(metrics.get('wer'))} | "
            f"{_format_metric(metrics.get('cer'))} | {result.error or ''} |"
        )

    lines.extend(
        [
            "",
            "## Recommended Default Configuration",
            "",
            recommended_configuration_text(best_config, reference_exists),
            "",
            "## Per-Configuration And Per-File Results",
            "",
        ]
    )
    for result in results:
        lines.extend(render_result(result))

    lines.extend(
        [
            "## Unresolved Issues",
            "",
            "- Media-speech results do not prove real meeting-room readiness.",
            "- If references were missing or failed to match, WER/CER for those files are unavailable.",
            "- VAD clipping notes are heuristic and require manual listening review.",
            "- Proper-noun/technical-term errors need manual review beyond the fixed term checklist.",
            "",
        ]
    )
    return "\n".join(lines)


def render_result(result: BenchmarkResult) -> list[str]:
    lines = [
        f"### {result.sample_id} / {result.model_name} + {result.profile}",
        "",
        f"- Audio path: `{result.audio_path}`",
        f"- Reference path: `{result.reference_path}`" if result.reference_path else "- Reference path: not found",
        f"- ASR status: `{result.asr_status}`",
        f"- Mock fallback used: `{result.mock_fallback_used}`",
        f"- Preprocessing status: `{result.preprocessing_status}`",
        f"- VAD provider: `{result.vad_provider}`",
        f"- Beam size: `{result.beam_size}`",
        f"- Compute type: `{result.compute_type}`",
        f"- Processing time: `{_format_seconds(result.processing_time_seconds)}`",
    ]
    if result.error:
        lines.extend(["", f"Error: `{result.error}`"])
        if result.reference_text:
            lines.extend(
                [
                    "",
                    "Reference transcript:",
                    "",
                    "```text",
                    result.reference_text,
                    "```",
                ]
            )
        lines.extend(
            [
                "",
                "Raw transcript:",
                "",
                "```text",
                "[not produced]",
                "```",
                "",
                "Cleaned transcript:",
                "",
                "```text",
                "[not produced]",
                "```",
                "",
            ]
        )
        return lines

    if result.reference_text:
        lines.extend(["", "Reference metrics:", ""])
        lines.extend(render_metrics("Raw", result.raw_metrics))
        lines.extend(render_metrics("Cleaned", result.cleaned_metrics))
    else:
        lines.extend(["", "Reference metrics: not available; no WER/CER computed."])

    lines.extend(["", "Turkish character preservation:", ""])
    lines.append("| Character | Raw Present | Cleaned Present |")
    lines.append("|---|---|---|")
    for char, status in result.turkish_chars.items():
        lines.append(f"| {char} | {status['raw']} | {status['cleaned']} |")

    lines.extend(["", "Technical term preservation:", ""])
    lines.append("| Term | Raw Present | Cleaned Present |")
    lines.append("|---|---|---|")
    for term, status in result.technical_terms.items():
        lines.append(f"| {term} | {status['raw']} | {status['cleaned']} |")

    lines.extend(["", "VAD clipping notes:", ""])
    for note in result.vad_clipping_notes:
        lines.append(f"- {note}")

    if result.reference_text:
        lines.extend(
            [
                "",
                "Reference transcript:",
                "",
                "```text",
                result.reference_text,
                "```",
            ]
        )

    lines.extend(
        [
            "",
            "Raw transcript:",
            "",
            "```text",
            result.raw_transcript or "[empty]",
            "```",
            "",
            "Cleaned transcript:",
            "",
            "```text",
            result.cleaned_transcript or "[empty]",
            "```",
            "",
        ]
    )
    return lines


def render_metrics(label: str, metrics: dict[str, Any] | None) -> list[str]:
    if metrics is None:
        return [f"- {label}: not available"]
    lines = [
        f"- {label} WER: {_format_metric(metrics.get('wer'))}",
        f"- {label} CER: {_format_metric(metrics.get('cer'))}",
        f"- {label} notable substitutions: {metrics.get('notable_substitutions', [])}",
        f"- {label} notable deletions: {metrics.get('notable_deletions', [])}",
        f"- {label} notable insertions: {metrics.get('notable_insertions', [])}",
    ]
    return lines


def aggregate_config_rows(results: list[BenchmarkResult]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[BenchmarkResult]] = {}
    for result in results:
        groups.setdefault((result.model_name, result.profile), []).append(result)

    rows: list[dict[str, Any]] = []
    for (model, profile), items in sorted(groups.items()):
        valid = [item for item in items if not item.error and not item.mock_fallback_used]
        metric_items = [
            item
            for item in valid
            if item.cleaned_metrics is not None and item.cleaned_metrics.get("wer") is not None
        ]
        rows.append(
            {
                "model": model,
                "profile": profile,
                "tested": len(items),
                "valid": len(valid),
                "errors": len([item for item in items if item.error]),
                "avg_time": _average(
                    item.processing_time_seconds for item in valid if item.processing_time_seconds is not None
                ),
                "avg_wer": _average(item.cleaned_metrics["wer"] for item in metric_items),
                "avg_cer": _average(item.cleaned_metrics["cer"] for item in metric_items),
            }
        )
    return rows


def choose_recommended_config(results: list[BenchmarkResult], reference_exists: bool) -> dict[str, Any] | None:
    rows = [row for row in aggregate_config_rows(results) if row["valid"] > 0]
    if not rows:
        return None
    if reference_exists:
        metric_rows = [row for row in rows if row["avg_wer"] is not None]
        if metric_rows:
            return min(
                metric_rows,
                key=lambda row: (
                    row["avg_wer"],
                    row["avg_cer"] if row["avg_cer"] is not None else float("inf"),
                    row["avg_time"] if row["avg_time"] is not None else float("inf"),
                ),
            )
    preference = [
        ("large-v3", "max_quality"),
        ("large-v3-turbo", "max_quality"),
        ("large-v3", "balanced"),
        ("large-v3-turbo", "balanced"),
    ]
    for model, profile in preference:
        for row in rows:
            if row["model"] == model and row["profile"] == profile:
                return row
    return rows[0]


def recommended_configuration_text(best: dict[str, Any] | None, reference_exists: bool) -> str:
    if best is None:
        return (
            "No valid benchmark result was produced. Keep the current provisional default "
            "`large-v3 + max_quality` only if local Faster-Whisper loads without mock fallback."
        )
    if not reference_exists:
        return (
            "No reference transcript was provided, so the recommendation remains provisional: "
            "`large-v3 + max_quality`. Do not claim it is more accurate than alternatives until WER/CER are measured."
        )
    return (
        f"Reference-based recommendation from this subset: `{best['model']} + {best['profile']}` "
        f"(avg cleaned WER={_format_metric(best['avg_wer'])}, avg cleaned CER={_format_metric(best['avg_cer'])}). "
        "This applies only to the tested media-speech subset and must not be treated as real meeting-room readiness."
    )


def _average(values: Any) -> float | None:
    items = [float(value) for value in values if value is not None]
    if not items:
        return None
    return sum(items) / len(items)


def _force_local_only_environment() -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["CMG_ALLOW_REMOTE_ACCESS"] = "false"
    os.environ["CMG_RT_ALLOW_REMOTE_ACCESS"] = "false"
    os.environ["CMG_RT_ALLOW_REMOTE_DOWNLOAD"] = "false"


def _load_configure_logging() -> Any:
    try:
        from app.utils.logging import configure_logging
    except ModuleNotFoundError as exc:
        import logging

        def configure_logging_fallback(level: str = "INFO") -> None:
            logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))

        print(
            "Warning: using fallback logging because realtime backend logging import failed: "
            f"{exc}",
            file=sys.stderr,
        )
        return configure_logging_fallback
    return configure_logging


def _load_backend_types() -> tuple[Any, Any]:
    try:
        from app.config import Settings
        from app.pipeline.orchestrator import TranscriptionPipeline
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing realtime backend dependencies. Install/use the project backend environment "
            f"before running the benchmark. Import failed: {exc}"
        ) from exc
    return Settings, TranscriptionPipeline


def _format_seconds(value: float | None) -> str:
    if value is None:
        return "unknown"
    return f"{value:.3f}s"


def _format_metric(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "n/a"


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
