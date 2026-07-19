from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import wave

from realtime_backend.app.evaluation.transcription_metrics import evaluate_transcription
from tools.transcript_annotation.dataset import AnnotationDataset, sha256_file
from tools.transcript_annotation.experiments import build_experiment_report
from tools.transcript_annotation.exporter import export_reviewed_dataset


def test_reviewed_export_writes_csv_jsonl_and_huggingface_audiofolder(tmp_path: Path):
    audio = tmp_path / "meeting.wav"
    _write_wav(audio, duration=2.0)
    original_hash = sha256_file(audio)
    dataset = AnnotationDataset.create(tmp_path / "dataset", dataset_name="Export Pilot")
    recording = dataset.add_recording(audio, _transcript())
    first = recording["segments"][0]
    dataset.update_segment(
        recording["recording_id"],
        first["segment_id"],
        reference_text="Collective MindGraph konuşuldu.",
        annotation_status="reviewed",
        speaker_id="speaker_a",
    )
    dataset.update_recording(recording["recording_id"], meeting_id="meeting_001")
    dataset.update_segment(
        recording["recording_id"],
        recording["segments"][1]["segment_id"],
        annotation_status="unclear",
    )

    output = tmp_path / "export"
    summary = export_reviewed_dataset(dataset, output, formats=("csv", "jsonl", "hf"))

    assert summary["exported_segment_count"] == 1
    assert summary["skipped_segment_count"] == 1
    assert summary["source_audio_modified"] is False
    assert sha256_file(audio) == original_hash
    with (output / "transcription.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["sentence"] == "Collective MindGraph konuşuldu."
    assert rows[0]["speaker_id"] == "speaker_a"
    assert rows[0]["meeting_id"] == "meeting_001"
    assert set(rows[0]) == {
        "audio",
        "sentence",
        "recording_id",
        "meeting_id",
        "segment_id",
        "start",
        "end",
        "condition_tags",
        "speaker_id",
    }
    jsonl = [json.loads(line) for line in (output / "transcription.jsonl").read_text(encoding="utf-8").splitlines()]
    assert jsonl[0]["source_audio_sha256"] == original_hash
    hf_rows = list(csv.DictReader((output / "huggingface" / "metadata.csv").open(encoding="utf-8")))
    assert hf_rows[0]["file_name"].startswith("audio/")
    clip = output / "huggingface" / hf_rows[0]["file_name"]
    with wave.open(str(clip), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getframerate() == 16000
        assert handle.getsampwidth() == 2
        assert handle.getnframes() > 0


def test_export_skips_excluded_empty_and_invalid_segments(tmp_path: Path):
    audio = tmp_path / "meeting.wav"
    _write_wav(audio, duration=2.0)
    dataset = AnnotationDataset.create(tmp_path / "dataset", dataset_name="Skip Pilot")
    recording = dataset.add_recording(audio, _transcript())
    first, second = recording["segments"]
    first["annotation_status"] = "excluded"
    first["exclusion_reason"] = "unintelligible"
    second["annotation_status"] = "reviewed"
    second["reference_text"] = ""
    dataset.save()

    summary = export_reviewed_dataset(dataset, tmp_path / "export", formats=("jsonl",))

    assert summary["exported_segment_count"] == 0
    assert summary["skipped_segment_count"] == 2
    assert (tmp_path / "export" / "transcription.jsonl").read_text(encoding="utf-8") == ""


def test_integration_edit_reload_export_evaluate_and_report(tmp_path: Path):
    audio = tmp_path / "fixture.wav"
    _write_wav(audio, duration=2.0)
    dataset = AnnotationDataset.create(tmp_path / "dataset", dataset_name="Integration Pilot")
    recording = dataset.add_recording(
        audio,
        _transcript(),
        condition_tags=["bad_mic", "technical_meeting"],
    )
    first = recording["segments"][0]
    dataset.update_segment(
        recording["recording_id"],
        first["segment_id"],
        reference_text="Collective MindGraph konuşuldu",
        annotation_status="reviewed",
    )

    reloaded = AnnotationDataset.load(dataset.root)
    export_summary = export_reviewed_dataset(reloaded, tmp_path / "export", formats=("csv", "jsonl"))
    evaluation = evaluate_transcription(
        reloaded.get_segment(recording["recording_id"], first["segment_id"])["reference_text"],
        "Collective MindGraph konuşuldu",
    )
    result = _experiment_result(recording["recording_id"], evaluation.to_dict())
    report = build_experiment_report(
        reloaded,
        [result["configuration"]],
        [result],
    )

    assert export_summary["exported_segment_count"] == 1
    assert evaluation.normalized.wer == 0.0
    assert "Best-Performing Configuration" in report
    assert "balanced_first_pass" in report
    assert "bad_mic" in report


def _experiment_result(recording_id: str, metrics: dict) -> dict:
    return {
        "experiment_id": "exp_test",
        "recording_id": recording_id,
        "recording_condition_tags": ["bad_mic", "technical_meeting"],
        "configuration": {
            "mode": "balanced_first_pass",
            "profile": "balanced",
            "model_override": None,
            "selective_model_override": None,
        },
        "profile": "balanced",
        "model": "small",
        "reference_metrics": metrics,
        "domain_term_metrics": {
            "total_reference_term_occurrences": 1,
            "correctly_recognized_occurrences": 1,
            "domain_term_accuracy": 1.0,
        },
        "processing_time_seconds": 0.5,
        "real_time_factor": 0.25,
        "selective_retranscription_settings": {},
        "error": None,
    }


def _transcript() -> dict:
    return {
        "conversation_id": "export_fixture",
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


def _write_wav(path: Path, *, duration: float, sample_rate: int = 16000) -> None:
    frames = bytearray()
    for index in range(int(duration * sample_rate)):
        value = int(math.sin(2 * math.pi * 220 * index / sample_rate) * 0.1 * 32767)
        frames.extend(value.to_bytes(2, byteorder="little", signed=True))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(bytes(frames))
