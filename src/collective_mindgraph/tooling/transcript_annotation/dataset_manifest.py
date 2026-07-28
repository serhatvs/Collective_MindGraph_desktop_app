"""Schema validation, migration and atomic persistence for annotation manifests."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from collective_mindgraph.application.transcription.evaluation.transcription_metrics import (
    NormalizationPolicy,
)

CURRENT_SCHEMA_VERSION = "1.0"
ANNOTATION_STATUSES = ("pending", "reviewed", "unclear", "excluded")


class DatasetIntegrityError(ValueError):
    """Raised when a manifest or requested edit would violate data integrity."""


class DuplicateAudioError(DatasetIntegrityError):
    def __init__(self, recording_id: str) -> None:
        super().__init__(f"Audio already exists in dataset as {recording_id}.")
        self.recording_id = recording_id


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def annotation_statistics(recordings: list[dict[str, Any]]) -> dict[str, Any]:
    recording_statuses = {status: 0 for status in ANNOTATION_STATUSES}
    segment_statuses = {status: 0 for status in ANNOTATION_STATUSES}
    for recording in recordings:
        status = str(recording.get("annotation_status") or "pending")
        recording_statuses[status] = recording_statuses.get(status, 0) + 1
        for segment in recording.get("segments", []):
            segment_status = str(segment.get("annotation_status") or "pending")
            segment_statuses[segment_status] = segment_statuses.get(segment_status, 0) + 1
    segment_count = sum(segment_statuses.values())
    reviewed_count = segment_statuses.get("reviewed", 0)
    return {
        "recording_count": len(recordings),
        "recordings_by_status": recording_statuses,
        "segment_count": segment_count,
        "segments_by_status": segment_statuses,
        "reviewed_segment_percentage": (
            round(reviewed_count / segment_count * 100.0, 2) if segment_count else 0.0
        ),
    }


def validate_manifest(manifest: dict[str, Any]) -> None:
    if str(manifest.get("schema_version")) != CURRENT_SCHEMA_VERSION:
        raise DatasetIntegrityError(
            f"Unsupported dataset schema {manifest.get('schema_version')}; "
            f"expected {CURRENT_SCHEMA_VERSION}."
        )
    if not str(manifest.get("dataset_name") or "").strip():
        raise DatasetIntegrityError("dataset_name is required.")
    if not isinstance(manifest.get("recordings"), list):
        raise DatasetIntegrityError("recordings must be a list.")
    recording_ids: set[str] = set()
    required_recording_fields = {
        "recording_id",
        "audio_path",
        "audio_sha256",
        "meeting_id",
        "source_name",
        "duration",
        "sample_rate",
        "annotation_status",
        "recording_condition_tags",
        "microphone_information",
        "room_information",
        "reviewer_notes",
        "original_transcription_profile",
        "original_transcription_metadata",
        "segments",
    }
    required_segment_fields = {
        "segment_id",
        "original_start",
        "original_end",
        "reviewed_start",
        "reviewed_end",
        "raw_asr_text",
        "selected_asr_text",
        "cleaned_asr_text",
        "reference_text",
        "annotation_status",
        "reviewer_notes",
        "confidence_metadata",
        "selective_retranscription_metadata",
        "exclusion_reason",
        "created_at",
        "updated_at",
        "speaker_id",
    }
    for recording in manifest["recordings"]:
        missing_fields = sorted(required_recording_fields - set(recording))
        if missing_fields:
            raise DatasetIntegrityError(
                "Recording is missing required fields: " + ", ".join(missing_fields)
            )
        recording_id = str(recording.get("recording_id") or "")
        if not recording_id or recording_id in recording_ids:
            raise DatasetIntegrityError(f"Duplicate or empty recording_id: {recording_id}")
        recording_ids.add(recording_id)
        if recording.get("annotation_status", "pending") not in ANNOTATION_STATUSES:
            raise DatasetIntegrityError(f"Invalid recording status in {recording_id}.")
        validate_unique_segment_ids(recording.get("segments", []))
        for segment in recording.get("segments", []):
            missing_fields = sorted(required_segment_fields - set(segment))
            if missing_fields:
                raise DatasetIntegrityError(
                    f"Segment {segment.get('segment_id')} is missing required fields: "
                    + ", ".join(missing_fields)
                )
            if segment.get("annotation_status", "pending") not in ANNOTATION_STATUSES:
                raise DatasetIntegrityError(
                    f"Invalid segment status in {recording_id}/{segment.get('segment_id')}."
                )


def validate_unique_segment_ids(segments: list[dict[str, Any]]) -> None:
    identifiers = [str(item.get("segment_id") or "") for item in segments]
    if any(not item for item in identifiers) or len(identifiers) != len(set(identifiers)):
        raise DatasetIntegrityError("Segment IDs must be non-empty and unique within a recording.")


def migrate_manifest(
    payload: dict[str, Any],
    version: str,
    manifest_path: Path,
) -> dict[str, Any]:
    if version not in {"0.9", "1"}:
        raise DatasetIntegrityError(
            f"No safe migration is available from schema {version} to {CURRENT_SCHEMA_VERSION}."
        )
    backup = manifest_path.with_name(
        f"dataset.json.backup-{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
    )
    shutil.copy2(manifest_path, backup)
    migrated = deepcopy(payload)
    timestamp = utc_now()
    migrated["schema_version"] = CURRENT_SCHEMA_VERSION
    migrated.setdefault("dataset_name", manifest_path.parent.name)
    migrated.setdefault("created_at", timestamp)
    migrated.setdefault("updated_at", timestamp)
    migrated.setdefault("language", "tr")
    migrated.setdefault("normalization_policy", NormalizationPolicy().to_dict())
    migrated.setdefault("glossary_references", [])
    migrated.setdefault("recordings", [])
    for recording_index, recording in enumerate(migrated["recordings"], start=1):
        _migrate_recording(recording, recording_index, timestamp)
    migrated["annotation_statistics"] = annotation_statistics(migrated["recordings"])
    validate_manifest(migrated)
    atomic_write_json(manifest_path, migrated)
    return migrated


def _migrate_recording(
    recording: dict[str, Any],
    recording_index: int,
    timestamp: str,
) -> None:
    recording.setdefault("recording_id", f"recording_{recording_index:06d}")
    recording.setdefault("audio_path", "")
    recording.setdefault("audio_sha256", "")
    recording.setdefault("meeting_id", recording["recording_id"])
    recording.setdefault(
        "source_name",
        Path(str(recording.get("audio_path") or "audio")).name,
    )
    recording.setdefault("annotation_status", "pending")
    recording.setdefault("duration", 0.0)
    recording.setdefault("sample_rate", None)
    recording.setdefault("recording_condition_tags", [])
    recording.setdefault("microphone_information", "")
    recording.setdefault("room_information", "")
    recording.setdefault("reviewer_notes", "")
    recording.setdefault("original_transcription_profile", "unknown")
    recording.setdefault("original_transcription_metadata", {})
    recording.setdefault("transcription_candidates", [])
    recording.setdefault("created_at", timestamp)
    recording.setdefault("updated_at", timestamp)
    recording.setdefault("segments", [])
    for segment_index, segment in enumerate(recording["segments"], start=1):
        _migrate_segment(segment, segment_index, timestamp)


def _migrate_segment(
    segment: dict[str, Any],
    segment_index: int,
    timestamp: str,
) -> None:
    start = float(segment.get("original_start", segment.get("start", 0.0)))
    end = float(segment.get("original_end", segment.get("end", start + 0.001)))
    raw = str(segment.get("raw_asr_text", segment.get("raw_text", "")))
    selected = str(segment.get("selected_asr_text", raw))
    segment.setdefault("segment_id", f"segment_{segment_index:06d}")
    segment["original_start"] = start
    segment["original_end"] = end
    segment.setdefault("reviewed_start", start)
    segment.setdefault("reviewed_end", end)
    segment["raw_asr_text"] = raw
    segment["selected_asr_text"] = selected
    segment.setdefault("cleaned_asr_text", selected)
    segment.setdefault("reference_text", selected)
    segment.setdefault("annotation_status", segment.get("status", "pending"))
    segment.setdefault("reviewer_notes", "")
    segment.setdefault("confidence_metadata", {})
    segment.setdefault("selective_retranscription_metadata", {})
    segment.setdefault("warnings", [])
    segment.setdefault("boundary_warnings", [])
    segment.setdefault("exclusion_reason", "")
    segment.setdefault("speaker_id", "unknown")
    segment.setdefault("created_at", timestamp)
    segment.setdefault("updated_at", timestamp)


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()
