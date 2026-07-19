from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace
import wave

import pytest

from tools.transcript_annotation import dataset as dataset_module
from tools.transcript_annotation.dataset import (
    CURRENT_SCHEMA_VERSION,
    AnnotationDataset,
    DatasetIntegrityError,
    DuplicateAudioError,
    atomic_write_text,
    sha256_file,
)
from tools.transcript_annotation.pipeline import RealASRUnavailableError, transcribe_for_annotation


def test_dataset_creation_builds_versioned_directory_structure(tmp_path: Path):
    dataset = AnnotationDataset.create(tmp_path / "pilot", dataset_name="Bad Mic Pilot")

    assert dataset.manifest["schema_version"] == CURRENT_SCHEMA_VERSION
    assert dataset.manifest["dataset_name"] == "Bad Mic Pilot"
    assert dataset.manifest["language"] == "tr"
    assert dataset.manifest["annotation_statistics"]["recording_count"] == 0
    for directory in ("recordings", "references", "exports", "reports"):
        assert (dataset.root / directory).is_dir()


def test_add_edit_reload_preserves_original_asr_and_human_reference(tmp_path: Path):
    audio = tmp_path / "meeting.wav"
    _write_wav(audio, duration=3.0)
    dataset = AnnotationDataset.create(tmp_path / "pilot", dataset_name="Pilot")
    recording = dataset.add_recording(
        audio,
        _transcript_payload(),
        initial_profile="balanced",
        condition_tags=["bad_mic", "technical_meeting", "custom setup"],
    )
    first = recording["segments"][0]
    original = (first["original_start"], first["original_end"], first["raw_asr_text"])

    warnings = dataset.update_segment(
        recording["recording_id"],
        first["segment_id"],
        reference_text="Merhaba ekip.",
        reviewed_start=0.0,
        reviewed_end=1.3,
        annotation_status="reviewed",
        reviewer_notes="Dinlenerek düzeltildi.",
        speaker_id="speaker_a",
    )
    dataset.update_recording(
        recording["recording_id"],
        meeting_id="meeting_001",
        source_name="Pilot toplantısı",
    )
    reloaded = AnnotationDataset.load(dataset.root)
    saved = reloaded.get_segment(recording["recording_id"], first["segment_id"])

    assert warnings == [f"overlaps next segment {recording['segments'][1]['segment_id']}"]
    assert (saved["original_start"], saved["original_end"], saved["raw_asr_text"]) == original
    assert saved["reviewed_end"] == 1.3
    assert saved["reference_text"] == "Merhaba ekip."
    assert saved["annotation_status"] == "reviewed"
    assert saved["speaker_id"] == "speaker_a"
    assert reloaded.get_recording(recording["recording_id"])["meeting_id"] == "meeting_001"
    assert reloaded.get_recording(recording["recording_id"])["source_name"] == "Pilot toplantısı"
    assert reloaded.manifest["annotation_statistics"]["segments_by_status"]["reviewed"] == 1
    reference_file = reloaded.root / "references" / f"{recording['recording_id']}.txt"
    assert reference_file.read_text(encoding="utf-8") == "Merhaba ekip.\n"
    assert set(recording["recording_condition_tags"]) == {"bad_mic", "technical_meeting", "custom_setup"}


def test_boundary_validation_clamps_duration_and_rejects_invalid_order(tmp_path: Path):
    audio = tmp_path / "meeting.wav"
    _write_wav(audio, duration=3.0)
    dataset = AnnotationDataset.create(tmp_path / "pilot", dataset_name="Pilot")
    recording = dataset.add_recording(audio, _transcript_payload())
    segment_id = recording["segments"][1]["segment_id"]

    dataset.update_segment(
        recording["recording_id"],
        segment_id,
        reviewed_start=-2.0,
        reviewed_end=9.0,
    )
    segment = dataset.get_segment(recording["recording_id"], segment_id)

    assert segment["reviewed_start"] == 0.0
    assert segment["reviewed_end"] == 3.0
    with pytest.raises(DatasetIntegrityError, match="greater than start"):
        dataset.update_segment(
            recording["recording_id"],
            segment_id,
            reviewed_start=2.0,
            reviewed_end=1.0,
        )


def test_duplicate_audio_and_segment_detection(tmp_path: Path):
    audio = tmp_path / "meeting.wav"
    _write_wav(audio, duration=2.0)
    dataset = AnnotationDataset.create(tmp_path / "pilot", dataset_name="Pilot")
    recording = dataset.add_recording(audio, _transcript_payload())

    with pytest.raises(DuplicateAudioError) as error:
        dataset.add_recording(audio, _transcript_payload())
    assert error.value.recording_id == recording["recording_id"]

    duplicate_segments = _transcript_payload()
    duplicate_segments["segments"][1]["segment_id"] = duplicate_segments["segments"][0]["segment_id"]
    other_audio = tmp_path / "other.wav"
    _write_wav(other_audio, duration=2.0, frequency=330)
    with pytest.raises(DatasetIntegrityError, match="unique"):
        dataset.add_recording(other_audio, duplicate_segments)


def test_new_transcription_candidate_never_overwrites_human_reference(tmp_path: Path):
    audio = tmp_path / "meeting.wav"
    _write_wav(audio, duration=2.0)
    dataset = AnnotationDataset.create(tmp_path / "pilot", dataset_name="Pilot")
    recording = dataset.add_recording(audio, _transcript_payload())
    segment = recording["segments"][0]
    dataset.update_segment(
        recording["recording_id"],
        segment["segment_id"],
        reference_text="İnsan tarafından düzeltildi.",
        annotation_status="reviewed",
    )

    dataset.add_transcription_candidate(
        recording["recording_id"],
        _transcript_payload(raw_first="tamamen yeni asr"),
        profile="max_quality",
    )

    assert dataset.get_segment(recording["recording_id"], segment["segment_id"])["reference_text"] == "İnsan tarafından düzeltildi."
    assert len(dataset.get_recording(recording["recording_id"])["transcription_candidates"]) == 2


def test_audio_copy_is_explicit_and_original_is_not_modified(tmp_path: Path):
    audio = tmp_path / "meeting.wav"
    _write_wav(audio, duration=2.0)
    original_hash = sha256_file(audio)
    dataset = AnnotationDataset.create(tmp_path / "pilot", dataset_name="Pilot")

    external = dataset.add_recording(audio, _transcript_payload(), copy_audio=False)
    assert Path(external["audio_path"]).is_absolute()
    assert sha256_file(audio) == original_hash

    second_audio = tmp_path / "other.wav"
    _write_wav(second_audio, duration=2.0, frequency=330)
    copied = dataset.add_recording(second_audio, _transcript_payload(), copy_audio=True)
    assert copied["audio_path"].startswith("recordings/")
    assert dataset.resolve_audio_path(copied).is_file()
    assert sha256_file(second_audio) == copied["audio_sha256"]


def test_schema_migration_creates_backup_and_preserves_legacy_fields(tmp_path: Path):
    root = tmp_path / "legacy"
    root.mkdir()
    audio = root / "legacy.wav"
    _write_wav(audio, duration=1.0)
    legacy = {
        "schema_version": "0.9",
        "dataset_name": "Legacy",
        "recordings": [
            {
                "recording_id": "legacy_recording",
                "audio_path": "legacy.wav",
                "audio_sha256": sha256_file(audio),
                "duration": 1.0,
                "segments": [{"segment_id": "legacy_segment", "start": 0.0, "end": 1.0, "raw_text": "ham metin"}],
            }
        ],
    }
    (root / "dataset.json").write_text(json.dumps(legacy), encoding="utf-8")

    dataset = AnnotationDataset.load(root)

    assert dataset.manifest["schema_version"] == CURRENT_SCHEMA_VERSION
    assert dataset.recordings[0]["segments"][0]["raw_asr_text"] == "ham metin"
    assert dataset.recordings[0]["segments"][0]["reference_text"] == "ham metin"
    assert list(root.glob("dataset.json.backup-*"))


def test_unknown_schema_is_rejected_without_overwriting_manifest(tmp_path: Path):
    root = tmp_path / "future"
    root.mkdir()
    manifest = root / "dataset.json"
    manifest.write_text('{"schema_version":"99","dataset_name":"Future","recordings":[]}', encoding="utf-8")
    original = manifest.read_bytes()

    with pytest.raises(DatasetIntegrityError, match="No safe migration"):
        AnnotationDataset.load(root)

    assert manifest.read_bytes() == original


def test_atomic_write_failure_leaves_previous_file_and_cleans_temporary(tmp_path: Path, monkeypatch):
    target = tmp_path / "dataset.json"
    target.write_text("original", encoding="utf-8")

    def fail_replace(_source, _target):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(dataset_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        atomic_write_text(target, "replacement")

    assert target.read_text(encoding="utf-8") == "original"
    assert not list(tmp_path.glob(".dataset.json.*.tmp"))


def test_integrity_report_detects_audio_hash_mismatch_and_empty_review(tmp_path: Path):
    audio = tmp_path / "meeting.wav"
    _write_wav(audio, duration=2.0)
    dataset = AnnotationDataset.create(tmp_path / "pilot", dataset_name="Pilot")
    recording = dataset.add_recording(audio, _transcript_payload())
    recording["segments"][0]["annotation_status"] = "reviewed"
    recording["segments"][0]["reference_text"] = ""
    with audio.open("ab") as handle:
        handle.write(b"changed")

    report = dataset.integrity_report(verify_hashes=True)

    assert not report["valid"]
    assert any("hash mismatch" in item for item in report["errors"])
    assert any("empty reviewed reference" in item for item in report["warnings"])


@pytest.mark.asyncio
async def test_annotation_pipeline_rejects_mock_result(tmp_path: Path):
    audio = tmp_path / "meeting.wav"
    _write_wav(audio, duration=1.0)

    class FakePipeline:
        async def process_audio_path(self, *_args, **_kwargs):
            return type("Transcript", (), {"metadata": {"mock_fallback_used": True, "asr_status": "ASR_STATUS=MOCK_FALLBACK"}})()

    with pytest.raises(RealASRUnavailableError, match="mock ASR"):
        await transcribe_for_annotation(
            audio,
            settings_factory=lambda: _settings(tmp_path),
            pipeline_factory=lambda _settings_value: FakePipeline(),
        )


@pytest.mark.asyncio
async def test_annotation_pipeline_forces_local_asr_and_preserves_configured_glossary(tmp_path: Path):
    audio = tmp_path / "meeting.wav"
    glossary = tmp_path / "project_terms.txt"
    _write_wav(audio, duration=1.0)
    glossary.write_text("Collective MindGraph\n", encoding="utf-8")
    settings = _settings(tmp_path)
    settings.transcription_project_glossary_path = glossary
    captured: dict = {}

    class FakePipeline:
        def __init__(self, configured_settings):
            captured["settings"] = configured_settings

        async def process_audio_path(self, path, **kwargs):
            captured["path"] = path
            captured["kwargs"] = kwargs
            return SimpleNamespace(metadata={"asr_status": "ASR_STATUS=OK"})

    result = await transcribe_for_annotation(
        audio,
        profile="balanced",
        settings_factory=lambda: settings,
        pipeline_factory=FakePipeline,
    )

    assert result.metadata["asr_status"] == "ASR_STATUS=OK"
    assert captured["settings"].asr_provider == "faster_whisper"
    assert captured["settings"].allow_remote_download is False
    assert captured["settings"].transcription_project_glossary_path == glossary
    assert captured["settings"].diarization_enabled is False
    assert captured["kwargs"]["quality_mode"] == "balanced"
    assert captured["kwargs"]["language"] == "tr"


def _settings(tmp_path: Path):
    from realtime_backend.app.config import Settings

    return Settings(data_dir=tmp_path / "data", temp_dir=tmp_path / "temp")


def _transcript_payload(*, raw_first: str = "merhaba ekip") -> dict:
    return {
        "conversation_id": "annotation_fixture",
        "source": "test",
        "language": "tr",
        "quality_mode": "balanced",
        "metadata": {"asr_status": "ASR_STATUS=OK", "model_name": "small"},
        "diagnostics": {"audio_duration": 3.0, "sample_rate_in": 16000},
        "segments": [
            {
                "segment_id": "segment_1",
                "start": 0.1,
                "end": 1.0,
                "speaker": "Speaker_1",
                "raw_text": raw_first,
                "corrected_text": "Merhaba ekip.",
                "confidence": 0.7,
                "words": [],
                "notes": ["low confidence"],
                "metadata": {
                    "asr": {
                        "avg_logprob": -0.7,
                        "selected_raw_transcript": raw_first,
                        "selective_retranscription": {"selected_pass": "first"},
                    }
                },
            },
            {
                "segment_id": "segment_2",
                "start": 1.1,
                "end": 2.0,
                "speaker": "Speaker_1",
                "raw_text": "ikinci bölüm",
                "corrected_text": "İkinci bölüm.",
                "confidence": 0.9,
                "words": [],
                "notes": [],
                "metadata": {"asr": {"avg_logprob": -0.2}},
            },
        ],
    }


def _write_wav(path: Path, *, duration: float, frequency: int = 220, sample_rate: int = 16000) -> None:
    frames = bytearray()
    for index in range(int(duration * sample_rate)):
        value = int(math.sin(2 * math.pi * frequency * index / sample_rate) * 0.1 * 32767)
        frames.extend(value.to_bytes(2, byteorder="little", signed=True))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(bytes(frames))
