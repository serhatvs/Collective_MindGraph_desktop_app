"""Coverage-safe aggregation and ranking for transcription experiments."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any


def experiment_identifier(
    recording_id: str,
    configuration: dict[str, Any],
) -> str:
    payload = json.dumps(
        {"recording_id": recording_id, "configuration": configuration},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "exp_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def configuration_key(configuration: dict[str, Any]) -> str:
    return "/".join(
        str(value or "default")
        for value in (
            configuration.get("mode"),
            configuration.get("profile"),
            configuration.get("selective_retranscription_enabled"),
            configuration.get("second_pass_profile"),
            configuration.get("model_override"),
            configuration.get("selective_model_override"),
        )
    )


def experiment_plan_ids(
    configurations: Iterable[dict[str, Any]],
    recording_ids: Iterable[str],
) -> set[str]:
    configuration_items = tuple(configurations)
    recording_id_items = tuple(str(item) for item in recording_ids)
    return {
        experiment_identifier(recording_id, configuration)
        for configuration in configuration_items
        for recording_id in recording_id_items
    }


def filter_results_for_plan(
    results: Iterable[dict[str, Any]],
    planned_experiment_ids: Iterable[str],
) -> list[dict[str, Any]]:
    planned = {str(value) for value in planned_experiment_ids}
    return [item for item in results if result_experiment_id(item) in planned]


def result_experiment_id(result: dict[str, Any]) -> str:
    identifier = result.get("experiment_id")
    if identifier:
        return str(identifier)
    return experiment_identifier(
        str(result.get("recording_id") or ""),
        result.get("configuration") or {},
    )


def aggregate_experiment_results(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        groups.setdefault(
            configuration_key(result.get("configuration") or {}),
            [],
        ).append(result)
    aggregates: list[dict[str, Any]] = []
    for key, items in sorted(groups.items()):
        referenced = [
            item
            for item in items
            if not item.get("error") and (item.get("reference_metrics") or {}).get("normalized")
        ]
        metrics = [(item.get("reference_metrics") or {}).get("normalized") for item in referenced]
        words = sum(int(item.get("reference_word_count") or 0) for item in metrics)
        characters = sum(int(item.get("reference_character_count") or 0) for item in metrics)
        word_distance = sum(int(item.get("word_distance") or 0) for item in metrics)
        character_distance = sum(int(item.get("character_distance") or 0) for item in metrics)
        domains = [item.get("domain_term_metrics") or {} for item in items if not item.get("error")]
        domain_total = sum(
            int(item.get("total_reference_term_occurrences") or 0) for item in domains
        )
        domain_correct = sum(
            int(item.get("correctly_recognized_occurrences") or 0) for item in domains
        )
        valid_times = [
            float(item["processing_time_seconds"]) for item in items if not item.get("error")
        ]
        valid_rtfs = [
            float(item["real_time_factor"])
            for item in items
            if not item.get("error") and item.get("real_time_factor") is not None
        ]
        attempted_ids = sorted(
            {str(item["recording_id"]) for item in items if item.get("recording_id")}
        )
        referenced_ids = sorted(
            {str(item["recording_id"]) for item in referenced if item.get("recording_id")}
        )
        aggregates.append(
            {
                "configuration_key": key,
                "experiment_ids": [result_experiment_id(item) for item in items],
                "result_count": len(items),
                "attempted_recording_ids": attempted_ids,
                "referenced_recording_ids": referenced_ids,
                "referenced_recordings": len(referenced_ids),
                "wer": word_distance / words if words else None,
                "cer": character_distance / characters if characters else None,
                "domain_term_accuracy": (domain_correct / domain_total if domain_total else None),
                "processing_time_seconds": (
                    sum(valid_times) / len(valid_times) if valid_times else None
                ),
                "real_time_factor": (sum(valid_rtfs) / len(valid_rtfs) if valid_rtfs else None),
                "failure_count": sum(bool(item.get("error")) for item in items),
            }
        )
    return aggregates


def choose_best_configuration(
    aggregates: list[dict[str, Any]],
    *,
    expected_configuration_keys: Iterable[str] | None = None,
    expected_recording_ids: Iterable[str] | None = None,
    expected_experiment_ids: Iterable[str] | None = None,
) -> dict[str, Any] | None:
    candidates = [item for item in aggregates if item.get("wer") is not None]
    if not candidates:
        return None
    if expected_configuration_keys is not None:
        expected = {str(value) for value in expected_configuration_keys}
        observed = {str(item.get("configuration_key") or "") for item in aggregates}
        if not expected or observed != expected:
            return None
    if len(candidates) != len(aggregates) or any(item.get("failure_count") for item in aggregates):
        return None
    if expected_recording_ids is not None:
        expected_recordings = tuple(sorted({str(value) for value in expected_recording_ids}))
        if not expected_recordings or any(
            tuple(str(value) for value in item.get("attempted_recording_ids") or ())
            != expected_recordings
            for item in aggregates
        ):
            return None
    if expected_experiment_ids is not None:
        expected_runs = sorted({str(value) for value in expected_experiment_ids})
        observed_runs = sorted(
            str(run_id) for item in aggregates for run_id in item.get("experiment_ids") or ()
        )
        if not expected_runs or observed_runs != expected_runs:
            return None
    attempted_coverage = {
        tuple(str(value) for value in item.get("attempted_recording_ids") or ())
        for item in aggregates
    }
    referenced_coverage = {
        tuple(str(value) for value in item.get("referenced_recording_ids") or ())
        for item in aggregates
    }
    if len(attempted_coverage) != 1 or len(referenced_coverage) != 1:
        return None
    return min(candidates, key=_ranking_key)


def _ranking_key(item: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        float(item["wer"]),
        float(item["cer"]) if item.get("cer") is not None else float("inf"),
        (
            -float(item["domain_term_accuracy"])
            if item.get("domain_term_accuracy") is not None
            else 0.0
        ),
        (
            float(item["processing_time_seconds"])
            if item.get("processing_time_seconds") is not None
            else float("inf")
        ),
    )


def condition_regressions(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
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
                {
                    "condition": condition,
                    "configuration_key": key,
                    "wer": distance / words,
                }
            )
    rows: list[dict[str, Any]] = []
    for _condition, items in sorted(by_condition.items()):
        best_wer = min(item["wer"] for item in items)
        for item in sorted(items, key=lambda value: value["configuration_key"]):
            rows.append({**item, "wer_delta": item["wer"] - best_wer})
    return rows
