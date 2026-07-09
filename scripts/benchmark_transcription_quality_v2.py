"""Benchmark transcription quality profiles on local audio files.

The report contains confidence estimates only. It does not calculate WER/CER
unless a future version is given human reference transcripts.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "realtime_backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings  # noqa: E402
from app.pipeline.asr import resolve_asr_quality_profile  # noqa: E402
from app.pipeline.orchestrator import TranscriptionPipeline  # noqa: E402
from app.pipeline.transcript_formatter import format_transcript  # noqa: E402


PROFILES = ("fast", "balanced", "max_quality", "bad_mic_recovery")
DEFAULT_OUTPUT = ROOT / "docs" / "dev" / "TRANSCRIPTION_QUALITY_V2_REPORT.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local transcription quality profile benchmarks.")
    parser.add_argument("audio", nargs="+", type=Path, help="One or more local audio files.")
    parser.add_argument(
        "--profiles",
        nargs="+",
        choices=PROFILES,
        default=list(PROFILES),
        help="Profiles to run. Defaults to all V2 profiles.",
    )
    parser.add_argument("--language", default=None, help="Language override, for example tr.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--include-summary", action="store_true", help="Also run summary generation.")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    audio_paths = [path.expanduser().resolve() for path in args.audio]
    missing = [path for path in audio_paths if not path.exists()]
    if missing:
        raise SystemExit("Audio file not found: " + ", ".join(str(path) for path in missing))

    results: list[dict[str, Any]] = []
    for audio_path in audio_paths:
        for profile in args.profiles:
            results.append(await run_profile(audio_path, profile, args.language, args.include_summary))

    report = build_report(results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Wrote report: {args.output}")
    return 0


async def run_profile(
    audio_path: Path,
    profile_name: str,
    language: str | None,
    include_summary: bool,
) -> dict[str, Any]:
    settings = Settings()
    settings.transcription_quality_mode = profile_name
    settings.enable_summary = bool(include_summary)
    settings.llm_provider = "disabled"
    resolved_profile = resolve_asr_quality_profile(settings, profile_name)
    started = time.perf_counter()
    error: str | None = None
    transcript_text = ""
    metadata: dict[str, Any] = {}
    try:
        pipeline = TranscriptionPipeline(settings)
        transcript = await pipeline.process_audio_path(
            audio_path,
            source="benchmark_transcription_quality_v2",
            language=language,
            quality_mode=profile_name,
            include_summary=include_summary,
        )
        metadata = dict(transcript.metadata)
        transcript_text = format_transcript(transcript, corrected=True)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started
    return {
        "audio_path": audio_path,
        "duration": _metadata_duration(metadata),
        "profile": profile_name,
        "settings": {
            "model_name": metadata.get("model_name") or resolved_profile.model_name,
            "beam_size": metadata.get("beam_size") or resolved_profile.beam_size,
            "compute_type": metadata.get("compute_type") or resolved_profile.compute_type,
            "word_timestamps": metadata.get("word_timestamps", resolved_profile.word_timestamps),
            "vad_filter": metadata.get("internal_faster_whisper_vad", resolved_profile.vad_filter),
            "condition_on_previous_text": metadata.get(
                "condition_on_previous_text",
                resolved_profile.condition_on_previous_text,
            ),
            "temperature_fallback": metadata.get("temperature_fallback") or list(resolved_profile.temperature),
            "preprocessing_strength": metadata.get("preprocessing_strength") or resolved_profile.preprocessing_strength,
        },
        "processing_time": elapsed,
        "transcript": transcript_text,
        "confidence": metadata.get("transcription_confidence_estimate"),
        "audio_quality_score": metadata.get("audio_quality_score"),
        "audio_quality_label": metadata.get("audio_quality_label"),
        "warnings": metadata.get("warnings") if isinstance(metadata.get("warnings"), list) else [],
        "metadata": metadata,
        "error": error,
    }


def build_report(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Transcription Quality V2 Report",
        "",
        "This report contains local confidence estimates only. It does not report real accuracy, WER, or CER.",
        "",
        "| File | Duration | Profile | Model | Beam | Preprocessing | Time | Confidence | Audio Quality | Warnings |",
        "| --- | ---: | --- | --- | ---: | --- | ---: | ---: | --- | --- |",
    ]
    for result in results:
        settings = result["settings"]
        warnings = ", ".join(str(item) for item in result["warnings"][:4])
        lines.append(
            "| "
            f"`{Path(result['audio_path']).name}` | "
            f"{_format_duration(result['duration'])} | "
            f"`{result['profile']}` | "
            f"`{settings['model_name']}` | "
            f"{settings['beam_size']} | "
            f"`{settings['preprocessing_strength']}` | "
            f"{result['processing_time']:.2f}s | "
            f"{_display_value(result['confidence'])} | "
            f"{_display_audio_quality(result)} | "
            f"{warnings or '-'} |"
        )
    lines.extend(["", "## Detailed Runs", ""])
    for result in results:
        lines.extend(_detailed_run_lines(result))
    return "\n".join(lines).rstrip() + "\n"


def _detailed_run_lines(result: dict[str, Any]) -> list[str]:
    settings = result["settings"]
    lines = [
        f"### {Path(result['audio_path']).name} - {result['profile']}",
        "",
        f"- File name: `{Path(result['audio_path']).name}`",
        f"- Duration: {_format_duration(result['duration'])}",
        f"- Profile: `{result['profile']}`",
        f"- Model/settings: `{settings['model_name']}`, beam `{settings['beam_size']}`, "
        f"compute `{settings['compute_type']}`, word timestamps `{settings['word_timestamps']}`, "
        f"VAD filter `{settings['vad_filter']}`, condition previous text `{settings['condition_on_previous_text']}`, "
        f"temperature fallback `{settings['temperature_fallback']}`, preprocessing `{settings['preprocessing_strength']}`",
        f"- Processing time: {result['processing_time']:.2f}s",
        f"- Confidence estimate: {_display_value(result['confidence'])}/100",
        f"- Audio quality score: {_display_value(result['audio_quality_score'])}/100",
        f"- Audio quality label: {result['audio_quality_label'] or '-'}",
        f"- Warnings: {', '.join(str(item) for item in result['warnings']) or '-'}",
        f"- Notes for manual review: {_manual_review_note(result)}",
        "",
    ]
    if result["error"]:
        lines.extend([f"Error: `{result['error']}`", ""])
    lines.extend(["Transcript:", "", "```text", result["transcript"] or "", "```", ""])
    return lines


def _metadata_duration(metadata: dict[str, Any]) -> float | None:
    audio_quality = metadata.get("audio_quality")
    if isinstance(audio_quality, dict):
        value = audio_quality.get("duration_seconds")
        if value is not None:
            return float(value)
    asr_input = metadata.get("asr_input_audio")
    if isinstance(asr_input, dict) and asr_input.get("duration_seconds") is not None:
        return float(asr_input["duration_seconds"])
    return None


def _manual_review_note(result: dict[str, Any]) -> str:
    if result["error"]:
        return "Run failed; inspect environment and audio path."
    confidence = result.get("confidence")
    audio_score = result.get("audio_quality_score")
    warnings = [str(item) for item in result.get("warnings", [])]
    if (isinstance(confidence, (int, float)) and confidence < 70) or (
        isinstance(audio_score, (int, float)) and audio_score < 70
    ):
        return "Review against the source audio before using this transcript."
    if warnings:
        return "Spot-check warning regions against the source audio."
    return "Spot-check is still recommended; no reference transcript was used."


def _display_audio_quality(result: dict[str, Any]) -> str:
    label = result.get("audio_quality_label")
    score = result.get("audio_quality_score")
    if label and score is not None:
        return f"{label} ({score})"
    return _display_value(score)


def _display_value(value: object) -> str:
    return "-" if value is None else str(value)


def _format_duration(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}s"


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
