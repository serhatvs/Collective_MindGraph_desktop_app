"""Atomic JSON, CSV and Markdown output for transcription experiments."""

from __future__ import annotations

import csv
import os
import tempfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .dataset import AnnotationDataset, atomic_write_json, atomic_write_text
from .experiment_analysis import experiment_plan_ids

EXPERIMENT_RESULTS_SCHEMA_VERSION = "1.0"


def write_experiment_outputs(
    output_directory: Path,
    dataset: AnnotationDataset,
    configurations: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    planned_recording_ids: Iterable[str] | None = None,
) -> None:
    from .experiments import build_experiment_report

    output = output_directory.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    planned_ids = (
        sorted({str(recording_id) for recording_id in planned_recording_ids})
        if planned_recording_ids is not None
        else None
    )
    planned_run_ids = (
        sorted(experiment_plan_ids(configurations, planned_ids))
        if planned_ids is not None
        else None
    )
    payload = {
        "schema_version": EXPERIMENT_RESULTS_SCHEMA_VERSION,
        "dataset_name": dataset.manifest["dataset_name"],
        "dataset_path": str(dataset.root),
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "configurations": configurations,
        "planned_recording_ids": planned_ids,
        "planned_experiment_ids": planned_run_ids,
        "results": results,
    }
    atomic_write_json(output / "experiment_results.json", payload)
    _write_results_csv(output / "experiment_results.csv", results)
    atomic_write_text(
        output / "TRANSCRIPTION_EXPERIMENT_REPORT.md",
        build_experiment_report(
            dataset,
            configurations,
            results,
            planned_recording_ids=planned_ids,
        ),
    )


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
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for result in results:
                normalized = (result.get("reference_metrics") or {}).get("normalized") or {}
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
                        "selective_regions": selective.get(
                            "number_of_second_pass_regions",
                            0,
                        ),
                        "percentage_audio_retranscribed": selective.get(
                            "percentage_of_audio_retranscribed",
                            0.0,
                        ),
                        "error": result.get("error"),
                    }
                )
        temporary_path.replace(path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
