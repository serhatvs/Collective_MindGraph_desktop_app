"""Dataset filtering, CMG experiment execution, and reproducible reports."""

from __future__ import annotations

import asyncio
import csv
from datetime import UTC, datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
from typing import Any, Awaitable, Callable, Iterable

from realtime_backend.app.config import Settings
from realtime_backend.app.evaluation.transcription_metrics import (
    NormalizationPolicy,
    evaluate_domain_terms,
    evaluate_transcription,
)
from realtime_backend.app.pipeline.transcription_glossary import parse_term_input, resolve_transcription_glossary

from .dataset import AnnotationDataset, atomic_write_json, atomic_write_text
from .pipeline import transcribe_for_annotation


EXPERIMENT_RESULTS_SCHEMA_VERSION = "1.0"


def build_experiment_configurations(
    profiles: Iterable[str],
    *,
    include_selective: bool = False,
    only_selective: bool = False,
    selective_base_profile: str = "balanced",
    second_pass_profile: str = "selective_recovery",
    model_overrides: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    overrides = dict(model_overrides or {})
    configurations: list[dict[str, Any]] = []
    if not only_selective:
        for profile in dict.fromkeys(item.strip().lower() for item in profiles if item.strip()):
            mode = "balanced_first_pass" if profile == "balanced" else f"full_{profile}"
            configurations.append(
                {
                    "mode": mode,
                    "profile": profile,
                    "selective_retranscription_enabled": False,
                    "second_pass_profile": second_pass_profile,
                    "model_override": overrides.get(profile),
                    "selective_model_override": overrides.get(second_pass_profile),
                }
            )
    if include_selective or only_selective:
        base = selective_base_profile.strip().lower() or "balanced"
        configurations.append(
            {
                "mode": f"{base}_plus_selective_recovery",
                "profile": base,
                "selective_retranscription_enabled": True,
                "second_pass_profile": second_pass_profile,
                "model_override": overrides.get(base),
                "selective_model_override": overrides.get(second_pass_profile),
            }
        )
    return configurations


def parse_model_overrides(values: Iterable[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Model override must use PROFILE=MODEL: {value}")
        profile, model = value.split("=", 1)
        if not profile.strip() or not model.strip():
            raise ValueError(f"Model override must use PROFILE=MODEL: {value}")
        result[profile.strip().lower()] = model.strip()
    return result


def filter_recordings(
    dataset: AnnotationDataset,
    *,
    recording_ids: Iterable[str] = (),
    condition_tags: Iterable[str] = (),
    maximum_count: int | None = None,
) -> list[dict[str, Any]]:
    identifiers = {item for item in recording_ids if item}
    required_tags = {item.strip().lower() for item in condition_tags if item.strip()}
    selected: list[dict[str, Any]] = []
    for recording in dataset.recordings:
        if recording.get("annotation_status") == "excluded":
            continue
        if identifiers and recording.get("recording_id") not in identifiers:
            continue
        tags = {str(item).lower() for item in recording.get("recording_condition_tags", [])}
        if required_tags and not required_tags.issubset(tags):
            continue
        selected.append(recording)
        if maximum_count is not None and maximum_count >= 0 and len(selected) >= maximum_count:
            break
    return selected


def reviewed_reference_text(recording: dict[str, Any]) -> str | None:
    lines = [
        str(segment.get("reference_text") or "").strip()
        for segment in sorted(recording.get("segments", []), key=lambda item: float(item["reviewed_start"]))
        if segment.get("annotation_status") == "reviewed"
        and str(segment.get("reference_text") or "").strip()
        and not segment.get("exclusion_reason")
        and float(segment.get("reviewed_end") or 0.0) > float(segment.get("reviewed_start") or 0.0)
    ]
    return " ".join(lines) if lines else None


def hypothesis_for_reviewed_regions(recording: dict[str, Any], transcript: Any) -> tuple[str, str]:
    payload = transcript.model_dump(mode="json") if hasattr(transcript, "model_dump") else transcript
    reviewed_intervals = [
        (float(segment["reviewed_start"]), float(segment["reviewed_end"]))
        for segment in recording.get("segments", [])
        if segment.get("annotation_status") == "reviewed"
        and str(segment.get("reference_text") or "").strip()
        and not segment.get("exclusion_reason")
    ]
    raw: list[str] = []
    cleaned: list[str] = []
    for segment in payload.get("segments", []):
        start = float(segment.get("start") or 0.0)
        end = float(segment.get("end") or start)
        if reviewed_intervals and not any(max(start, left) < min(end, right) for left, right in reviewed_intervals):
            continue
        raw_text = str(segment.get("raw_text") or "").strip()
        cleaned_text = str(segment.get("corrected_text") or raw_text).strip()
        if raw_text:
            raw.append(raw_text)
        if cleaned_text:
            cleaned.append(cleaned_text)
    return " ".join(raw), " ".join(cleaned)


async def run_recording_experiment(
    dataset: AnnotationDataset,
    recording: dict[str, Any],
    configuration: dict[str, Any],
    *,
    glossary_file: Path | None,
    glossary_terms: list[str],
    glossary_metadata: dict[str, Any],
    pipeline_runner: Callable[..., Awaitable[Any]] = transcribe_for_annotation,
    git_commit: str | None = None,
) -> dict[str, Any]:
    experiment_id = experiment_identifier(recording["recording_id"], configuration)
    started_at = datetime.now(tz=UTC).isoformat()
    started = time.perf_counter()
    audio_path = dataset.resolve_audio_path(recording)
    reference = reviewed_reference_text(recording)
    result: dict[str, Any] = {
        "experiment_id": experiment_id,
        "recording_id": recording["recording_id"],
        "meeting_id": recording.get("meeting_id"),
        "recording_condition_tags": list(recording.get("recording_condition_tags") or []),
        "git_commit": git_commit or current_git_commit(dataset.root),
        "started_at": started_at,
        "completed_at": None,
        "environment": environment_information(),
        "configuration": dict(configuration),
        "audio_path": str(audio_path),
        "audio_duration_seconds": recording.get("duration"),
        "processing_time_seconds": None,
        "real_time_factor": None,
        "transcript_output": None,
        "reference_available": bool(reference),
        "reference_metrics": None,
        "domain_term_metrics": None,
        "model": configuration.get("model_override"),
        "device": None,
        "compute_type": None,
        "profile": configuration["profile"],
        "preprocessing_settings": {},
        "vad_settings": {},
        "selective_retranscription_settings": {},
        "glossary_information": glossary_metadata,
        "warnings": [],
        "error": None,
    }
    try:
        transcript = await pipeline_runner(
            audio_path,
            profile=configuration["profile"],
            model_override=configuration.get("model_override"),
            selective_model_override=configuration.get("selective_model_override"),
            selective_enabled=configuration["selective_retranscription_enabled"],
            selective_profile=configuration["second_pass_profile"],
            glossary_file=glossary_file,
            glossary_terms=glossary_terms,
        )
        payload = transcript.model_dump(mode="json") if hasattr(transcript, "model_dump") else transcript
        metadata = dict(payload.get("metadata") or {})
        diagnostics = dict(payload.get("diagnostics") or {})
        raw_text, cleaned_text = hypothesis_for_reviewed_regions(recording, payload)
        result["transcript_output"] = {
            "raw_text": raw_text,
            "cleaned_text": cleaned_text,
            "segments": payload.get("segments", []),
            "metadata": metadata,
        }
        result["model"] = metadata.get("model_name") or result["model"]
        result["device"] = metadata.get("device") or diagnostics.get("device")
        result["compute_type"] = metadata.get("compute_type") or diagnostics.get("compute_type")
        result["preprocessing_settings"] = {
            "status": metadata.get("preprocessing_status"),
            "strength": metadata.get("preprocessing_strength"),
            "steps": metadata.get("preprocessing_steps", []),
        }
        result["vad_settings"] = diagnostics.get("vad_settings", {})
        result["selective_retranscription_settings"] = metadata.get("selective_retranscription", {})
        result["warnings"] = list(metadata.get("warnings") or diagnostics.get("warnings") or [])
        if reference:
            policy = NormalizationPolicy.from_dict(dataset.manifest.get("normalization_policy"))
            evaluation = evaluate_transcription(reference, cleaned_text or raw_text, policy=policy)
            domain = evaluate_domain_terms(reference, cleaned_text or raw_text, glossary_terms, policy=policy)
            result["reference_metrics"] = evaluation.to_dict() if evaluation else None
            result["domain_term_metrics"] = domain.to_dict() if domain else None
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started
    result["processing_time_seconds"] = elapsed
    duration = float(recording.get("duration") or 0.0)
    result["real_time_factor"] = elapsed / duration if duration > 0.0 else None
    result["completed_at"] = datetime.now(tz=UTC).isoformat()
    return result


def experiment_identifier(recording_id: str, configuration: dict[str, Any]) -> str:
    payload = json.dumps(
        {"recording_id": recording_id, "configuration": configuration},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "exp_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def completed_experiment_ids(results: Iterable[dict[str, Any]]) -> set[str]:
    return {
        str(item["experiment_id"])
        for item in results
        if item.get("experiment_id") and not item.get("error")
    }


def load_existing_results(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if str(payload.get("schema_version")) != EXPERIMENT_RESULTS_SCHEMA_VERSION:
        raise ValueError(f"Unsupported experiment results schema: {payload.get('schema_version')}")
    return list(payload.get("results") or [])


def load_experiment_glossary(
    dataset: AnnotationDataset,
    experiment_glossary: Path | None,
) -> tuple[list[str], dict[str, Any]]:
    dataset_terms: list[str] = []
    warnings: list[str] = []
    for stored_path in dataset.manifest.get("glossary_references", []):
        path = Path(str(stored_path)).expanduser()
        if not path.is_absolute():
            path = dataset.root / path
        terms, warning = _read_glossary(path)
        dataset_terms.extend(terms)
        if warning:
            warnings.append(warning)
    experiment_terms: list[str] = []
    if experiment_glossary:
        experiment_terms, warning = _read_glossary(experiment_glossary)
        if warning:
            warnings.append(warning)
    settings = Settings(
        transcription_glossary_max_terms=10_000,
        transcription_glossary_max_prompt_chars=1_000_000,
        transcription_glossary_max_term_length=500,
    )
    resolved = resolve_transcription_glossary(
        settings,
        user_hotwords=experiment_terms,
        session_terms=dataset_terms,
    )
    metadata = resolved.to_metadata()
    metadata["dataset_glossary_references"] = list(dataset.manifest.get("glossary_references", []))
    metadata["experiment_glossary"] = str(experiment_glossary) if experiment_glossary else None
    metadata["warnings"] = warnings
    return list(resolved.terms), metadata


def write_experiment_outputs(
    output_directory: Path,
    dataset: AnnotationDataset,
    configurations: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> None:
    output = output_directory.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": EXPERIMENT_RESULTS_SCHEMA_VERSION,
        "dataset_name": dataset.manifest["dataset_name"],
        "dataset_path": str(dataset.root),
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "configurations": configurations,
        "results": results,
    }
    atomic_write_json(output / "experiment_results.json", payload)
    _write_results_csv(output / "experiment_results.csv", results)
    atomic_write_text(
        output / "TRANSCRIPTION_EXPERIMENT_REPORT.md",
        build_experiment_report(dataset, configurations, results),
    )


def build_experiment_report(
    dataset: AnnotationDataset,
    configurations: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> str:
    aggregates = aggregate_experiment_results(results)
    best = choose_best_configuration(aggregates)
    condition_counts: dict[str, int] = {}
    for recording in dataset.recordings:
        for tag in recording.get("recording_condition_tags", []):
            condition_counts[tag] = condition_counts.get(tag, 0) + 1
    excluded_recordings = [
        str(item["recording_id"])
        for item in dataset.recordings
        if item.get("annotation_status") == "excluded"
    ]
    lines = [
        "# Transcription Experiment Report",
        "",
        "Metrics in this report are computed only for recordings with reviewed human references. Confidence estimates are not used to select the best configuration.",
        "",
        "## Dataset Summary",
        "",
        f"- Dataset: `{dataset.manifest['dataset_name']}`",
        f"- Dataset path: `{dataset.root}`",
        f"- Recordings: `{len(dataset.recordings)}`",
        f"- Reviewed segments: `{dataset.manifest.get('annotation_statistics', {}).get('segments_by_status', {}).get('reviewed', 0)}`",
        f"- Excluded recordings: `{len(excluded_recordings)}`",
        "",
        "Recording-condition distribution:",
        "",
    ]
    if condition_counts:
        lines.extend(f"- `{condition}`: {count}" for condition, count in sorted(condition_counts.items()))
    else:
        lines.append("- No condition tags recorded.")

    lines.extend(["", "## Experiment Configuration", ""])
    for configuration in configurations:
        lines.append(f"- `{configuration['mode']}`: `{json.dumps(configuration, ensure_ascii=False, sort_keys=True)}`")

    lines.extend(
        [
            "",
            "## Per-Recording Metrics",
            "",
            "| Recording | Conditions | Mode | Profile | Model | WER | CER | Domain Terms | Time | RTF | Regions | Audio Retranscribed | Error |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for result in results:
        normalized = ((result.get("reference_metrics") or {}).get("normalized") or {})
        domain = result.get("domain_term_metrics") or {}
        selective = result.get("selective_retranscription_settings") or {}
        lines.append(
            f"| `{result.get('recording_id')}` | {', '.join(result.get('recording_condition_tags') or []) or '-'} | "
            f"`{result.get('configuration', {}).get('mode')}` | `{result.get('profile')}` | `{result.get('model')}` | "
            f"{_metric(normalized.get('wer'))} | {_metric(normalized.get('cer'))} | "
            f"{_metric(domain.get('domain_term_accuracy'))} | {_metric(result.get('processing_time_seconds'))} | "
            f"{_metric(result.get('real_time_factor'))} | {selective.get('number_of_second_pass_regions', 0)} | "
            f"{_metric(selective.get('percentage_of_audio_retranscribed'))} | {result.get('error') or '-'} |"
        )

    lines.extend(
        [
            "",
            "## Aggregate Metrics",
            "",
            "| Configuration | Referenced Recordings | WER | CER | Domain Terms | Time | RTF | Failures |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for aggregate in aggregates:
        lines.append(
            f"| `{aggregate['configuration_key']}` | {aggregate['referenced_recordings']} | "
            f"{_metric(aggregate.get('wer'))} | {_metric(aggregate.get('cer'))} | "
            f"{_metric(aggregate.get('domain_term_accuracy'))} | {_metric(aggregate.get('processing_time_seconds'))} | "
            f"{_metric(aggregate.get('real_time_factor'))} | {aggregate['failure_count']} |"
        )

    lines.extend(["", "## Best-Performing Configuration", ""])
    if best:
        lines.append(
            f"`{best['configuration_key']}` ranks first by normalized WER, then CER, domain-term accuracy, and processing cost. "
            f"WER=`{_metric(best.get('wer'))}`, CER=`{_metric(best.get('cer'))}`, "
            f"domain-term accuracy=`{_metric(best.get('domain_term_accuracy'))}`, average time=`{_metric(best.get('processing_time_seconds'))}` seconds."
        )
    else:
        lines.append("No best configuration is declared because no valid human-reference metrics were available.")

    lines.extend(["", "## Regressions by Condition", ""])
    regressions = condition_regressions(results)
    if regressions:
        lines.extend(
            [
                "| Condition | Configuration | WER | Delta From Best Condition WER |",
                "| --- | --- | ---: | ---: |",
            ]
        )
        lines.extend(
            f"| `{item['condition']}` | `{item['configuration_key']}` | {_metric(item['wer'])} | {_metric(item['wer_delta'])} |"
            for item in regressions
        )
    else:
        lines.append("No condition-level regressions can be calculated without tagged, reviewed references.")

    failures = [item for item in results if item.get("error")]
    lines.extend(["", "## Failed and Excluded Recordings", ""])
    lines.append(f"- Failed experiment runs: `{len(failures)}`")
    for item in failures:
        lines.append(f"  - `{item.get('recording_id')}` / `{item.get('configuration', {}).get('mode')}`: {item['error']}")
    lines.append(f"- Excluded recordings: `{', '.join(excluded_recordings) if excluded_recordings else 'none'}`")

    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "Results apply only to reviewed references in this dataset. Condition groups with few recordings are unstable; WER/CER do not measure meaning preservation, and domain-term accuracy covers only configured glossary occurrences. Keep future training recordings separate from held-out evaluation meetings.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def aggregate_experiment_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        key = configuration_key(result.get("configuration") or {})
        groups.setdefault(key, []).append(result)
    aggregates: list[dict[str, Any]] = []
    for key, items in sorted(groups.items()):
        metric_items = [
            (item.get("reference_metrics") or {}).get("normalized")
            for item in items
            if not item.get("error") and (item.get("reference_metrics") or {}).get("normalized")
        ]
        word_count = sum(int(item.get("reference_word_count") or 0) for item in metric_items)
        character_count = sum(int(item.get("reference_character_count") or 0) for item in metric_items)
        word_distance = sum(int(item.get("word_distance") or 0) for item in metric_items)
        character_distance = sum(int(item.get("character_distance") or 0) for item in metric_items)
        domain_items = [item.get("domain_term_metrics") or {} for item in items if not item.get("error")]
        domain_total = sum(int(item.get("total_reference_term_occurrences") or 0) for item in domain_items)
        domain_correct = sum(int(item.get("correctly_recognized_occurrences") or 0) for item in domain_items)
        valid_times = [float(item["processing_time_seconds"]) for item in items if not item.get("error")]
        valid_rtfs = [float(item["real_time_factor"]) for item in items if not item.get("error") and item.get("real_time_factor") is not None]
        aggregates.append(
            {
                "configuration_key": key,
                "referenced_recordings": len(metric_items),
                "wer": word_distance / word_count if word_count else None,
                "cer": character_distance / character_count if character_count else None,
                "domain_term_accuracy": domain_correct / domain_total if domain_total else None,
                "processing_time_seconds": sum(valid_times) / len(valid_times) if valid_times else None,
                "real_time_factor": sum(valid_rtfs) / len(valid_rtfs) if valid_rtfs else None,
                "failure_count": sum(bool(item.get("error")) for item in items),
            }
        )
    return aggregates


def choose_best_configuration(aggregates: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [item for item in aggregates if item.get("wer") is not None]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda item: (
            float(item["wer"]),
            float(item["cer"]) if item.get("cer") is not None else float("inf"),
            -float(item["domain_term_accuracy"]) if item.get("domain_term_accuracy") is not None else 0.0,
            float(item["processing_time_seconds"])
            if item.get("processing_time_seconds") is not None
            else float("inf"),
        ),
    )


def condition_regressions(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for result in results:
        metrics = (result.get("reference_metrics") or {}).get("normalized")
        if result.get("error") or not metrics:
            continue
        key = configuration_key(result.get("configuration") or {})
        for condition in result.get("recording_condition_tags") or []:
            grouped.setdefault((condition, key), []).append(metrics)
    by_condition: dict[str, list[dict[str, Any]]] = {}
    for (condition, key), items in grouped.items():
        words = sum(int(item.get("reference_word_count") or 0) for item in items)
        distance = sum(int(item.get("word_distance") or 0) for item in items)
        if words:
            by_condition.setdefault(condition, []).append(
                {"condition": condition, "configuration_key": key, "wer": distance / words}
            )
    rows: list[dict[str, Any]] = []
    for condition, items in sorted(by_condition.items()):
        best_wer = min(item["wer"] for item in items)
        for item in sorted(items, key=lambda value: value["configuration_key"]):
            rows.append({**item, "wer_delta": item["wer"] - best_wer})
    return rows


def configuration_key(configuration: dict[str, Any]) -> str:
    return "/".join(
        str(value or "default")
        for value in (
            configuration.get("mode"),
            configuration.get("profile"),
            configuration.get("model_override"),
            configuration.get("selective_model_override"),
        )
    )


def current_git_commit(_path: Path | None = None) -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def environment_information() -> dict[str, Any]:
    packages: dict[str, str | None] = {}
    for package in ("faster-whisper", "ctranslate2", "PySide6"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": packages,
    }


def _read_glossary(path: Path) -> tuple[list[str], str | None]:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        return [], f"glossary not found: {resolved}"
    try:
        text = resolved.read_text(encoding="utf-8")
        if resolved.suffix.lower() == ".json":
            payload = json.loads(text)
            if isinstance(payload, list):
                return [str(item) for item in payload], None
            if isinstance(payload, dict):
                values: list[str] = []
                for item in payload.values():
                    if isinstance(item, list):
                        values.extend(str(value) for value in item)
                    elif isinstance(item, str):
                        values.append(item)
                return values, None
        return parse_term_input(text), None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [], f"cannot read glossary {resolved}: {type(exc).__name__}: {exc}"


def _write_results_csv(path: Path, results: list[dict[str, Any]]) -> None:
    fields = (
        "experiment_id",
        "recording_id",
        "conditions",
        "mode",
        "profile",
        "model",
        "device",
        "compute_type",
        "wer",
        "cer",
        "domain_term_accuracy",
        "processing_time_seconds",
        "real_time_factor",
        "selective_regions",
        "percentage_audio_retranscribed",
        "error",
    )
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        import os

        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for result in results:
                normalized = ((result.get("reference_metrics") or {}).get("normalized") or {})
                domain = result.get("domain_term_metrics") or {}
                selective = result.get("selective_retranscription_settings") or {}
                writer.writerow(
                    {
                        "experiment_id": result.get("experiment_id"),
                        "recording_id": result.get("recording_id"),
                        "conditions": ",".join(result.get("recording_condition_tags") or []),
                        "mode": result.get("configuration", {}).get("mode"),
                        "profile": result.get("profile"),
                        "model": result.get("model"),
                        "device": result.get("device"),
                        "compute_type": result.get("compute_type"),
                        "wer": normalized.get("wer"),
                        "cer": normalized.get("cer"),
                        "domain_term_accuracy": domain.get("domain_term_accuracy"),
                        "processing_time_seconds": result.get("processing_time_seconds"),
                        "real_time_factor": result.get("real_time_factor"),
                        "selective_regions": selective.get("number_of_second_pass_regions", 0),
                        "percentage_audio_retranscribed": selective.get("percentage_of_audio_retranscribed", 0.0),
                        "error": result.get("error"),
                    }
                )
        Path(temporary_name).replace(path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _metric(value: Any) -> str:
    try:
        return "-" if value is None else f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "-"
