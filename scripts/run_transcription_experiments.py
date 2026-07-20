"""Run reproducible CMG transcription experiments against an annotation dataset."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.transcript_annotation.dataset import AnnotationDataset  # noqa: E402
from tools.transcript_annotation.experiments import (  # noqa: E402
    build_experiment_configurations,
    completed_experiment_ids,
    experiment_plan_ids,
    experiment_identifier,
    filter_results_for_plan,
    filter_recordings,
    load_existing_results,
    load_experiment_glossary,
    parse_model_overrides,
    run_recording_experiment,
    write_experiment_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--profiles", nargs="+", default=["balanced", "max_quality"])
    parser.add_argument("--include-selective", action="store_true")
    parser.add_argument("--only-selective", action="store_true")
    parser.add_argument("--selective-base-profile", default="balanced")
    parser.add_argument("--second-pass-profile", default="selective_recovery")
    parser.add_argument("--model-override", action="append", default=[], metavar="PROFILE=MODEL")
    parser.add_argument("--recording-id", action="append", default=[])
    parser.add_argument("--condition", action="append", default=[])
    parser.add_argument("--glossary-file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-recordings", type=int)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    dataset = AnnotationDataset.load(args.dataset)
    output = (args.output or (dataset.root / "reports")).expanduser().resolve()
    configurations = build_experiment_configurations(
        args.profiles,
        include_selective=args.include_selective,
        only_selective=args.only_selective,
        selective_base_profile=args.selective_base_profile,
        second_pass_profile=args.second_pass_profile,
        model_overrides=parse_model_overrides(args.model_override),
    )
    if not configurations:
        raise SystemExit("No experiment configuration selected.")
    recordings = filter_recordings(
        dataset,
        recording_ids=args.recording_id,
        condition_tags=args.condition,
        maximum_count=args.max_recordings,
    )
    if not recordings:
        raise SystemExit("No non-excluded recordings matched the requested filters.")
    planned_recording_ids = [str(recording["recording_id"]) for recording in recordings]
    planned_run_ids = experiment_plan_ids(configurations, planned_recording_ids)
    glossary_file = args.glossary_file.expanduser().resolve() if args.glossary_file else None
    glossary_terms, glossary_metadata = load_experiment_glossary(dataset, glossary_file)
    results_path = output / "experiment_results.json"
    results = (
        filter_results_for_plan(load_existing_results(results_path), planned_run_ids)
        if args.resume
        else []
    )
    completed = completed_experiment_ids(results)

    for configuration in configurations:
        for recording in recordings:
            identifier = experiment_identifier(recording["recording_id"], configuration)
            if identifier in completed:
                continue
            results = [item for item in results if item.get("experiment_id") != identifier]
            result = await run_recording_experiment(
                dataset,
                recording,
                configuration,
                glossary_file=glossary_file,
                glossary_terms=glossary_terms,
                glossary_metadata=glossary_metadata,
            )
            results.append(result)
            write_experiment_outputs(
                output,
                dataset,
                configurations,
                results,
                planned_recording_ids=planned_recording_ids,
            )

    write_experiment_outputs(
        output,
        dataset,
        configurations,
        results,
        planned_recording_ids=planned_recording_ids,
    )
    failures = [item for item in results if item.get("error")]
    print(f"Wrote {len(results)} experiment result(s) to {output}")
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
