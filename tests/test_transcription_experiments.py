from __future__ import annotations

import json
import math
from pathlib import Path
import wave

import pytest

from tools.transcript_annotation.dataset import AnnotationDataset
from tools.transcript_annotation.experiments import (
    aggregate_experiment_results,
    build_experiment_report,
    build_experiment_configurations,
    choose_best_configuration,
    completed_experiment_ids,
    condition_regressions,
    experiment_identifier,
    filter_recordings,
    load_existing_results,
    parse_model_overrides,
    run_recording_experiment,
    write_experiment_outputs,
)


def test_experiment_configurations_capture_three_required_modes_and_models():
    configurations = build_experiment_configurations(
        ["balanced", "max_quality"],
        include_selective=True,
        model_overrides={"balanced": "large-v3-turbo", "max_quality": "large-v3", "selective_recovery": "large-v3"},
    )

    assert [item["mode"] for item in configurations] == [
        "balanced_first_pass",
        "full_max_quality",
        "balanced_plus_selective_recovery",
    ]
    assert configurations[0]["model_override"] == "large-v3-turbo"
    assert configurations[2]["selective_model_override"] == "large-v3"
    assert parse_model_overrides(["balanced=small", "selective_recovery=large-v3"]) == {
        "balanced": "small",
        "selective_recovery": "large-v3",
    }
    with pytest.raises(ValueError, match="PROFILE=MODEL"):
        parse_model_overrides(["invalid"])


def test_recording_filters_require_conditions_and_exclude_recordings(tmp_path: Path):
    dataset = _dataset_with_two_recordings(tmp_path)
    dataset.recordings[1]["annotation_status"] = "excluded"

    filtered = filter_recordings(dataset, condition_tags=["bad_mic"], maximum_count=5)

    assert [item["recording_id"] for item in filtered] == [dataset.recordings[0]["recording_id"]]
    assert filter_recordings(dataset, condition_tags=["quiet_room"]) == []


@pytest.mark.asyncio
async def test_experiment_run_uses_reviewed_regions_and_reference_metrics(tmp_path: Path):
    dataset = _dataset_with_two_recordings(tmp_path)
    recording = dataset.recordings[0]
    first = recording["segments"][0]
    dataset.update_segment(
        recording["recording_id"],
        first["segment_id"],
        reference_text="Collective MindGraph konuşuldu",
        annotation_status="reviewed",
    )
    configuration = build_experiment_configurations(["balanced"])[0]
    received: dict = {}

    async def fake_pipeline(audio_path: Path, **kwargs):
        received.update(kwargs)
        return _candidate_transcript(audio_path)

    result = await run_recording_experiment(
        dataset,
        recording,
        configuration,
        glossary_file=None,
        glossary_terms=["Collective MindGraph"],
        glossary_metadata={"accepted_count": 1},
        pipeline_runner=fake_pipeline,
        git_commit="abc123",
    )

    assert result["error"] is None
    assert result["git_commit"] == "abc123"
    assert result["reference_available"] is True
    assert result["reference_metrics"]["normalized"]["wer"] == 0.0
    assert result["domain_term_metrics"]["domain_term_accuracy"] == 1.0
    assert result["model"] == "small"
    assert result["device"] == "cpu"
    assert received["profile"] == "balanced"
    assert received["selective_enabled"] is False
    assert received["glossary_terms"] == ["Collective MindGraph"]


@pytest.mark.asyncio
async def test_experiment_failure_is_preserved_and_resume_retries_it(tmp_path: Path):
    dataset = _dataset_with_two_recordings(tmp_path)
    recording = dataset.recordings[0]
    configuration = build_experiment_configurations(["balanced"])[0]

    async def failing_pipeline(_audio_path: Path, **_kwargs):
        raise RuntimeError("model unavailable")

    result = await run_recording_experiment(
        dataset,
        recording,
        configuration,
        glossary_file=None,
        glossary_terms=[],
        glossary_metadata={},
        pipeline_runner=failing_pipeline,
    )

    assert "model unavailable" in result["error"]
    assert completed_experiment_ids([result]) == set()
    successful = {**result, "error": None}
    assert completed_experiment_ids([successful]) == {result["experiment_id"]}


def test_output_generation_resume_and_best_configuration_use_reference_metrics(tmp_path: Path):
    dataset = _dataset_with_two_recordings(tmp_path)
    configurations = build_experiment_configurations(["balanced", "max_quality"])
    balanced = _result(dataset.recordings[0]["recording_id"], configurations[0], wer=0.3, cer=0.2, domain=0.8, seconds=1.0)
    strong = _result(dataset.recordings[0]["recording_id"], configurations[1], wer=0.2, cer=0.15, domain=0.7, seconds=4.0)
    output = tmp_path / "reports"

    write_experiment_outputs(output, dataset, configurations, [balanced, strong])
    loaded = load_existing_results(output / "experiment_results.json")
    aggregates = aggregate_experiment_results(loaded)
    best = choose_best_configuration(aggregates)

    assert {item["experiment_id"] for item in loaded} == {balanced["experiment_id"], strong["experiment_id"]}
    assert best["configuration_key"].startswith("full_max_quality")
    assert (output / "experiment_results.csv").is_file()
    report = (output / "TRANSCRIPTION_EXPERIMENT_REPORT.md").read_text(encoding="utf-8")
    assert "Aggregate Metrics" in report
    assert "Best-Performing Configuration" in report
    assert "Confidence estimates are not used" in report
    assert condition_regressions(loaded)


def test_no_best_configuration_without_human_reference_metrics():
    configuration = build_experiment_configurations(["balanced"])[0]
    result = {
        "configuration": configuration,
        "reference_metrics": None,
        "domain_term_metrics": None,
        "processing_time_seconds": 1.0,
        "real_time_factor": 0.5,
        "error": None,
    }

    assert choose_best_configuration(aggregate_experiment_results([result])) is None


def test_best_configuration_requires_failure_free_identical_recording_coverage(tmp_path: Path):
    dataset = _dataset_with_two_recordings(tmp_path)
    configurations = build_experiment_configurations(["balanced", "max_quality"])
    first_id = dataset.recordings[0]["recording_id"]
    second_id = dataset.recordings[1]["recording_id"]
    incomplete = _result(first_id, configurations[0], wer=0.0, cer=0.0, domain=1.0, seconds=0.5)
    failed = {
        **_result(second_id, configurations[0], wer=1.0, cer=1.0, domain=0.0, seconds=0.1),
        "reference_metrics": None,
        "domain_term_metrics": None,
        "error": "RuntimeError: model failed",
    }
    complete = [
        _result(first_id, configurations[1], wer=0.1, cer=0.1, domain=0.9, seconds=2.0),
        _result(second_id, configurations[1], wer=0.1, cer=0.1, domain=0.9, seconds=2.0),
    ]
    results = [incomplete, failed, *complete]
    aggregates = aggregate_experiment_results(results)

    assert choose_best_configuration(aggregates) is None
    assert all(
        item["attempted_recording_ids"] == sorted([first_id, second_id])
        for item in aggregates
    )
    report = build_experiment_report(dataset, configurations, results)
    assert "No best configuration is declared" in report
    assert "failures or unequal recording coverage" in report


def test_best_configuration_requires_identical_reference_coverage():
    configurations = build_experiment_configurations(["balanced", "max_quality"])
    results = [
        _result("recording_1", configurations[0], wer=0.0, cer=0.0, domain=1.0, seconds=0.5),
        _result("recording_1", configurations[1], wer=0.1, cer=0.1, domain=0.9, seconds=2.0),
        _result("recording_2", configurations[1], wer=0.1, cer=0.1, domain=0.9, seconds=2.0),
    ]

    assert choose_best_configuration(aggregate_experiment_results(results)) is None


def test_experiment_identifier_is_stable_for_resume():
    configuration = build_experiment_configurations(["balanced"])[0]

    assert experiment_identifier("recording", configuration) == experiment_identifier("recording", dict(configuration))


def _dataset_with_two_recordings(tmp_path: Path) -> AnnotationDataset:
    dataset = AnnotationDataset.create(tmp_path / "dataset", dataset_name="Experiments")
    first_audio = tmp_path / "first.wav"
    second_audio = tmp_path / "second.wav"
    _write_wav(first_audio, frequency=220)
    _write_wav(second_audio, frequency=330)
    dataset.add_recording(first_audio, _annotation_transcript(), condition_tags=["bad_mic", "technical_meeting"])
    dataset.add_recording(second_audio, _annotation_transcript(), condition_tags=["good_mic", "quiet_room"])
    return dataset


def _annotation_transcript() -> dict:
    return {
        "conversation_id": "annotation",
        "source": "test",
        "metadata": {"asr_status": "ASR_STATUS=OK"},
        "segments": [
            {
                "segment_id": "segment_1",
                "start": 0.0,
                "end": 0.9,
                "raw_text": "collective mindgraph konuşuldu",
                "corrected_text": "Collective MindGraph konuşuldu.",
                "metadata": {},
            },
            {
                "segment_id": "segment_2",
                "start": 1.0,
                "end": 1.8,
                "raw_text": "ikinci bölüm",
                "corrected_text": "İkinci bölüm.",
                "metadata": {},
            },
        ],
    }


def _candidate_transcript(_audio_path: Path) -> dict:
    return {
        "conversation_id": "candidate",
        "source": "experiment",
        "diagnostics": {"device": "cpu", "compute_type": "int8", "vad_settings": {"provider": "energy"}},
        "metadata": {
            "asr_status": "ASR_STATUS=OK",
            "model_name": "small",
            "device": "cpu",
            "compute_type": "int8",
            "preprocessing_status": "ffmpeg_safe_loudness",
            "preprocessing_strength": "safe_loudness",
            "preprocessing_steps": ["loudnorm"],
            "selective_retranscription": {"number_of_second_pass_regions": 0, "percentage_of_audio_retranscribed": 0.0},
            "warnings": [],
        },
        "segments": [
            {
                "segment_id": "candidate_1",
                "start": 0.0,
                "end": 0.9,
                "raw_text": "collective mindgraph konuşuldu",
                "corrected_text": "Collective MindGraph konuşuldu",
                "metadata": {},
            },
            {
                "segment_id": "candidate_2",
                "start": 1.0,
                "end": 1.8,
                "raw_text": "ikinci bölüm",
                "corrected_text": "İkinci bölüm",
                "metadata": {},
            },
        ],
    }


def _result(recording_id: str, configuration: dict, *, wer: float, cer: float, domain: float, seconds: float) -> dict:
    reference_words = 10
    reference_characters = 50
    return {
        "experiment_id": experiment_identifier(recording_id, configuration),
        "recording_id": recording_id,
        "recording_condition_tags": ["bad_mic"],
        "configuration": configuration,
        "profile": configuration["profile"],
        "model": configuration.get("model_override") or "default",
        "reference_metrics": {
            "normalized": {
                "reference_word_count": reference_words,
                "reference_character_count": reference_characters,
                "word_distance": int(wer * reference_words),
                "character_distance": int(cer * reference_characters),
                "wer": wer,
                "cer": cer,
            }
        },
        "domain_term_metrics": {
            "total_reference_term_occurrences": 10,
            "correctly_recognized_occurrences": int(domain * 10),
            "domain_term_accuracy": domain,
        },
        "processing_time_seconds": seconds,
        "real_time_factor": seconds / 2,
        "selective_retranscription_settings": {},
        "error": None,
    }


def _write_wav(path: Path, *, frequency: int, duration: float = 2.0, sample_rate: int = 16000) -> None:
    frames = bytearray()
    for index in range(int(duration * sample_rate)):
        value = int(math.sin(2 * math.pi * frequency * index / sample_rate) * 0.1 * 32767)
        frames.extend(value.to_bytes(2, byteorder="little", signed=True))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(bytes(frames))
