"""Versioned, recoverable manifest storage for transcription annotation."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterable
import uuid
import wave

from realtime_backend.app.evaluation.transcription_metrics import NormalizationPolicy


CURRENT_SCHEMA_VERSION = "1.0"
ANNOTATION_STATUSES = ("pending", "reviewed", "unclear", "excluded")
CONDITION_TAGS = (
    "good_mic",
    "bad_mic",
    "far_field",
    "near_field",
    "noisy_room",
    "quiet_room",
    "low_volume",
    "clipping",
    "echo",
    "phone_recording",
    "laptop_microphone",
    "external_microphone",
    "overlapping_speech",
    "technical_meeting",
)


class DatasetIntegrityError(ValueError):
    """Raised when a manifest or requested edit would violate data integrity."""


class DuplicateAudioError(DatasetIntegrityError):
    def __init__(self, recording_id: str) -> None:
        super().__init__(f"Audio already exists in dataset as {recording_id}.")
        self.recording_id = recording_id


class AnnotationDataset:
    """Manage one local dataset with atomic writes and immutable ASR fields."""

    def __init__(self, root: Path, manifest: dict[str, Any]) -> None:
        self.root = root.expanduser().resolve()
        self.manifest_path = self.root / "dataset.json"
        self.manifest = manifest
        self.load_warnings: list[str] = []

    @classmethod
    def create(
        cls,
        root: Path,
        *,
        dataset_name: str,
        language: str = "tr",
        normalization_policy: NormalizationPolicy | None = None,
    ) -> "AnnotationDataset":
        resolved = root.expanduser().resolve()
        if (resolved / "dataset.json").exists():
            raise DatasetIntegrityError(f"Dataset already exists: {resolved}")
        for directory in (resolved, resolved / "recordings", resolved / "references", resolved / "exports", resolved / "reports"):
            directory.mkdir(parents=True, exist_ok=True)
        timestamp = _utc_now()
        manifest = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "dataset_name": dataset_name.strip() or resolved.name,
            "created_at": timestamp,
            "updated_at": timestamp,
            "language": language.strip() or "tr",
            "normalization_policy": (normalization_policy or NormalizationPolicy()).to_dict(),
            "recordings": [],
            "glossary_references": [],
            "annotation_statistics": _annotation_statistics([]),
        }
        dataset = cls(resolved, manifest)
        dataset.save()
        return dataset

    @classmethod
    def load(cls, root: Path, *, migrate: bool = True) -> "AnnotationDataset":
        resolved = root.expanduser().resolve()
        manifest_path = resolved if resolved.name == "dataset.json" else resolved / "dataset.json"
        resolved = manifest_path.parent
        if not manifest_path.exists():
            raise DatasetIntegrityError(f"Dataset manifest not found: {manifest_path}")
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise DatasetIntegrityError(f"Cannot read dataset manifest: {exc}") from exc
        version = str(payload.get("schema_version") or "0.9")
        if version != CURRENT_SCHEMA_VERSION:
            if not migrate:
                raise DatasetIntegrityError(
                    f"Unsupported dataset schema {version}; expected {CURRENT_SCHEMA_VERSION}."
                )
            payload = _migrate_manifest(payload, version, manifest_path)
        _validate_manifest(payload)
        for directory in (resolved / "recordings", resolved / "references", resolved / "exports", resolved / "reports"):
            directory.mkdir(parents=True, exist_ok=True)
        dataset = cls(resolved, payload)
        dataset.load_warnings = dataset.integrity_report(verify_hashes=False)["warnings"]
        return dataset

    @property
    def recordings(self) -> list[dict[str, Any]]:
        return self.manifest["recordings"]

    def get_recording(self, recording_id: str) -> dict[str, Any]:
        for recording in self.recordings:
            if recording.get("recording_id") == recording_id:
                return recording
        raise KeyError(f"Unknown recording: {recording_id}")

    def get_segment(self, recording_id: str, segment_id: str) -> dict[str, Any]:
        recording = self.get_recording(recording_id)
        for segment in recording.get("segments", []):
            if segment.get("segment_id") == segment_id:
                return segment
        raise KeyError(f"Unknown segment {segment_id} in {recording_id}")

    def resolve_audio_path(self, recording: str | dict[str, Any]) -> Path:
        item = self.get_recording(recording) if isinstance(recording, str) else recording
        stored = Path(str(item["audio_path"])).expanduser()
        return stored.resolve() if stored.is_absolute() else (self.root / stored).resolve()

    def find_recording_by_hash(self, sha256: str) -> dict[str, Any] | None:
        return next((item for item in self.recordings if item.get("audio_sha256") == sha256), None)

    def add_recording(
        self,
        audio_path: Path,
        transcript: Any,
        *,
        initial_profile: str = "balanced",
        copy_audio: bool = False,
        meeting_id: str | None = None,
        source_name: str | None = None,
        condition_tags: Iterable[str] = (),
        microphone_information: str = "",
        room_information: str = "",
        reviewer_notes: str = "",
    ) -> dict[str, Any]:
        source = audio_path.expanduser().resolve()
        if not source.is_file():
            raise DatasetIntegrityError(f"Audio file not found: {source}")
        audio_hash = sha256_file(source)
        duplicate = self.find_recording_by_hash(audio_hash)
        if duplicate:
            raise DuplicateAudioError(str(duplicate["recording_id"]))
        recording_id = _unique_recording_id(audio_hash, self.recordings)
        stored_audio = source
        if copy_audio:
            destination = self.root / "recordings" / f"{recording_id}{source.suffix.lower()}"
            if destination.exists():
                raise DatasetIntegrityError(f"Refusing to overwrite imported audio: {destination}")
            shutil.copy2(source, destination)
            stored_audio = destination

        transcript_payload = _model_payload(transcript)
        duration, sample_rate = _audio_facts(source, transcript_payload)
        timestamp = _utc_now()
        segments = _segments_from_transcript(transcript_payload, timestamp)
        _validate_unique_segment_ids(segments)
        tags = _normalize_tags(condition_tags)
        recording = {
            "recording_id": recording_id,
            "audio_path": _portable_path(stored_audio, self.root),
            "audio_sha256": audio_hash,
            "meeting_id": meeting_id or recording_id,
            "source_name": source_name or source.name,
            "duration": duration,
            "sample_rate": sample_rate,
            "annotation_status": "pending",
            "recording_condition_tags": tags,
            "microphone_information": microphone_information,
            "room_information": room_information,
            "reviewer_notes": reviewer_notes,
            "original_transcription_profile": initial_profile,
            "original_transcription_metadata": deepcopy(transcript_payload.get("metadata", {})),
            "transcription_candidates": [
                {
                    "candidate_id": f"candidate_{uuid.uuid4().hex[:12]}",
                    "created_at": timestamp,
                    "profile": initial_profile,
                    "transcript": transcript_payload,
                }
            ],
            "segments": segments,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        self.recordings.append(recording)
        self.save()
        return recording

    def add_transcription_candidate(
        self,
        recording_id: str,
        transcript: Any,
        *,
        profile: str,
        label: str | None = None,
    ) -> dict[str, Any]:
        """Store a new ASR candidate without changing human reference fields."""

        recording = self.get_recording(recording_id)
        candidate = {
            "candidate_id": f"candidate_{uuid.uuid4().hex[:12]}",
            "created_at": _utc_now(),
            "profile": profile,
            "label": label or profile,
            "transcript": _model_payload(transcript),
        }
        recording.setdefault("transcription_candidates", []).append(candidate)
        recording["updated_at"] = _utc_now()
        self.save()
        return candidate

    def update_segment(
        self,
        recording_id: str,
        segment_id: str,
        *,
        reference_text: str | None = None,
        reviewed_start: float | None = None,
        reviewed_end: float | None = None,
        annotation_status: str | None = None,
        reviewer_notes: str | None = None,
        exclusion_reason: str | None = None,
        speaker_id: str | None = None,
    ) -> list[str]:
        recording = self.get_recording(recording_id)
        segment = self.get_segment(recording_id, segment_id)
        if annotation_status is not None and annotation_status not in ANNOTATION_STATUSES:
            raise DatasetIntegrityError(f"Unknown annotation status: {annotation_status}")
        duration = max(0.0, float(recording.get("duration") or 0.0))
        start = float(segment["reviewed_start"] if reviewed_start is None else reviewed_start)
        end = float(segment["reviewed_end"] if reviewed_end is None else reviewed_end)
        if duration > 0.0:
            start = min(duration, max(0.0, start))
            end = min(duration, max(0.0, end))
        else:
            start = max(0.0, start)
            end = max(0.0, end)
        if end <= start:
            raise DatasetIntegrityError("Reviewed segment end must be greater than start.")
        warnings = self.boundary_warnings(recording_id, segment_id, start=start, end=end)

        segment["reviewed_start"] = round(start, 6)
        segment["reviewed_end"] = round(end, 6)
        if reference_text is not None:
            segment["reference_text"] = str(reference_text)
        if annotation_status is not None:
            segment["annotation_status"] = annotation_status
        if reviewer_notes is not None:
            segment["reviewer_notes"] = str(reviewer_notes)
        if exclusion_reason is not None:
            segment["exclusion_reason"] = str(exclusion_reason)
        if speaker_id is not None:
            segment["speaker_id"] = str(speaker_id).strip() or "unknown"
        if segment["annotation_status"] == "excluded" and not segment.get("exclusion_reason"):
            segment["exclusion_reason"] = "excluded by reviewer"
        segment["boundary_warnings"] = warnings
        segment["updated_at"] = _utc_now()
        recording["updated_at"] = segment["updated_at"]
        self.save()
        return warnings

    def boundary_warnings(
        self,
        recording_id: str,
        segment_id: str,
        *,
        start: float,
        end: float,
    ) -> list[str]:
        recording = self.get_recording(recording_id)
        ordered = sorted(recording.get("segments", []), key=lambda item: float(item["reviewed_start"]))
        index = next(index for index, item in enumerate(ordered) if item["segment_id"] == segment_id)
        warnings: list[str] = []
        if index > 0 and start < float(ordered[index - 1]["reviewed_end"]):
            warnings.append(f"overlaps previous segment {ordered[index - 1]['segment_id']}")
        if index + 1 < len(ordered) and end > float(ordered[index + 1]["reviewed_start"]):
            warnings.append(f"overlaps next segment {ordered[index + 1]['segment_id']}")
        return warnings

    def update_recording(
        self,
        recording_id: str,
        *,
        annotation_status: str | None = None,
        condition_tags: Iterable[str] | None = None,
        microphone_information: str | None = None,
        room_information: str | None = None,
        reviewer_notes: str | None = None,
        meeting_id: str | None = None,
        source_name: str | None = None,
    ) -> None:
        recording = self.get_recording(recording_id)
        if annotation_status is not None:
            if annotation_status not in ANNOTATION_STATUSES:
                raise DatasetIntegrityError(f"Unknown annotation status: {annotation_status}")
            recording["annotation_status"] = annotation_status
        if condition_tags is not None:
            recording["recording_condition_tags"] = _normalize_tags(condition_tags)
        if microphone_information is not None:
            recording["microphone_information"] = microphone_information
        if room_information is not None:
            recording["room_information"] = room_information
        if reviewer_notes is not None:
            recording["reviewer_notes"] = reviewer_notes
        if meeting_id is not None:
            recording["meeting_id"] = meeting_id.strip() or recording_id
        if source_name is not None:
            recording["source_name"] = source_name.strip() or recording["source_name"]
        recording["updated_at"] = _utc_now()
        self.save()

    def set_glossary_references(self, paths: Iterable[Path | str]) -> None:
        values: list[str] = []
        seen: set[str] = set()
        for path in paths:
            resolved = Path(path).expanduser().resolve()
            stored = _portable_path(resolved, self.root)
            key = stored.casefold()
            if key not in seen:
                seen.add(key)
                values.append(stored)
        self.manifest["glossary_references"] = values
        self.save()

    def save(self) -> None:
        _validate_manifest(self.manifest)
        self.manifest["updated_at"] = _utc_now()
        self.manifest["annotation_statistics"] = _annotation_statistics(self.recordings)
        atomic_write_json(self.manifest_path, self.manifest)
        for recording in self.recordings:
            self._write_reference_text(recording)

    def integrity_report(self, *, verify_hashes: bool = True) -> dict[str, Any]:
        warnings: list[str] = []
        errors: list[str] = []
        seen_hashes: dict[str, str] = {}
        for recording in self.recordings:
            recording_id = str(recording.get("recording_id"))
            audio_path = self.resolve_audio_path(recording)
            if not audio_path.exists():
                warnings.append(f"missing audio for {recording_id}: {audio_path}")
            elif verify_hashes:
                actual_hash = sha256_file(audio_path)
                if actual_hash != recording.get("audio_sha256"):
                    errors.append(f"audio hash mismatch for {recording_id}")
            audio_hash = str(recording.get("audio_sha256") or "")
            if audio_hash in seen_hashes:
                errors.append(f"duplicate audio hash: {seen_hashes[audio_hash]} and {recording_id}")
            elif audio_hash:
                seen_hashes[audio_hash] = recording_id
            segment_ids: set[str] = set()
            for segment in recording.get("segments", []):
                segment_id = str(segment.get("segment_id"))
                if segment_id in segment_ids:
                    errors.append(f"duplicate segment {segment_id} in {recording_id}")
                segment_ids.add(segment_id)
                start = float(segment.get("reviewed_start") or 0.0)
                end = float(segment.get("reviewed_end") or 0.0)
                if start < 0.0 or end <= start or (recording.get("duration") and end > float(recording["duration"])):
                    errors.append(f"invalid boundaries for {recording_id}/{segment_id}")
                if segment.get("annotation_status") == "reviewed" and not str(segment.get("reference_text") or "").strip():
                    warnings.append(f"empty reviewed reference for {recording_id}/{segment_id}")
        return {"valid": not errors, "errors": errors, "warnings": warnings}

    def _write_reference_text(self, recording: dict[str, Any]) -> None:
        lines = [
            str(segment.get("reference_text") or "").strip()
            for segment in sorted(recording.get("segments", []), key=lambda item: float(item["reviewed_start"]))
            if segment.get("annotation_status") == "reviewed"
            and str(segment.get("reference_text") or "").strip()
            and not segment.get("exclusion_reason")
        ]
        target = self.root / "references" / f"{recording['recording_id']}.txt"
        atomic_write_text(target, "\n".join(lines) + ("\n" if lines else ""))


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _model_payload(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return deepcopy(value)
    raise TypeError("Transcript must be a ConversationTranscript or mapping.")


def _segments_from_transcript(transcript: dict[str, Any], timestamp: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, item in enumerate(transcript.get("segments", []), start=1):
        metadata = deepcopy(item.get("metadata") or {})
        asr_metadata = metadata.get("asr") if isinstance(metadata.get("asr"), dict) else metadata
        selective = (
            metadata.get("selective_retranscription")
            or (asr_metadata.get("selective_retranscription") if isinstance(asr_metadata, dict) else None)
            or {}
        )
        raw_text = str(item.get("raw_text") or "")
        selected_text = str(
            (asr_metadata.get("selected_raw_transcript") if isinstance(asr_metadata, dict) else None)
            or raw_text
        )
        cleaned_text = str(item.get("corrected_text") or selected_text)
        original_start = float(item.get("start") or 0.0)
        original_end = float(item.get("end") or original_start)
        segment_id = str(item.get("segment_id") or f"segment_{index:06d}")
        result.append(
            {
                "segment_id": segment_id,
                "original_start": original_start,
                "original_end": original_end,
                "reviewed_start": original_start,
                "reviewed_end": original_end,
                "raw_asr_text": raw_text,
                "selected_asr_text": selected_text,
                "cleaned_asr_text": cleaned_text,
                "reference_text": selected_text,
                "annotation_status": "pending",
                "reviewer_notes": "",
                "confidence_metadata": {
                    "confidence": item.get("confidence"),
                    "words": deepcopy(item.get("words") or []),
                    "asr": deepcopy(asr_metadata) if isinstance(asr_metadata, dict) else {},
                },
                "selective_retranscription_metadata": deepcopy(selective),
                "warnings": list(item.get("notes") or []),
                "boundary_warnings": [],
                "exclusion_reason": "",
                "speaker_id": "unknown",
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
    return result


def _audio_facts(path: Path, transcript: dict[str, Any]) -> tuple[float, int | None]:
    try:
        with wave.open(str(path), "rb") as handle:
            sample_rate = handle.getframerate()
            frame_count = handle.getnframes()
        return (frame_count / sample_rate if sample_rate else 0.0), sample_rate or None
    except (wave.Error, OSError):
        diagnostics = transcript.get("diagnostics") or {}
        metadata = transcript.get("metadata") or {}
        input_audio = metadata.get("input_audio") or metadata.get("asr_input_audio") or {}
        duration = diagnostics.get("audio_duration") or input_audio.get("duration_seconds") or 0.0
        sample_rate = diagnostics.get("sample_rate_in") or input_audio.get("sample_rate")
        return float(duration or 0.0), int(sample_rate) if sample_rate else None


def _portable_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _normalize_tags(tags: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        normalized = "_".join(str(tag).strip().lower().split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _unique_recording_id(audio_hash: str, recordings: list[dict[str, Any]]) -> str:
    base = f"rec_{audio_hash[:12]}"
    existing = {str(item.get("recording_id")) for item in recordings}
    if base not in existing:
        return base
    suffix = 2
    while f"{base}_{suffix}" in existing:
        suffix += 1
    return f"{base}_{suffix}"


def _annotation_statistics(recordings: list[dict[str, Any]]) -> dict[str, Any]:
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
        "reviewed_segment_percentage": round(reviewed_count / segment_count * 100.0, 2)
        if segment_count
        else 0.0,
    }


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if str(manifest.get("schema_version")) != CURRENT_SCHEMA_VERSION:
        raise DatasetIntegrityError(
            f"Unsupported dataset schema {manifest.get('schema_version')}; expected {CURRENT_SCHEMA_VERSION}."
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
        missing_recording_fields = sorted(required_recording_fields - set(recording))
        if missing_recording_fields:
            raise DatasetIntegrityError(
                f"Recording is missing required fields: {', '.join(missing_recording_fields)}"
            )
        recording_id = str(recording.get("recording_id") or "")
        if not recording_id or recording_id in recording_ids:
            raise DatasetIntegrityError(f"Duplicate or empty recording_id: {recording_id}")
        recording_ids.add(recording_id)
        if recording.get("annotation_status", "pending") not in ANNOTATION_STATUSES:
            raise DatasetIntegrityError(f"Invalid recording status in {recording_id}.")
        _validate_unique_segment_ids(recording.get("segments", []))
        for segment in recording.get("segments", []):
            missing_segment_fields = sorted(required_segment_fields - set(segment))
            if missing_segment_fields:
                raise DatasetIntegrityError(
                    f"Segment {segment.get('segment_id')} is missing required fields: "
                    + ", ".join(missing_segment_fields)
                )
            if segment.get("annotation_status", "pending") not in ANNOTATION_STATUSES:
                raise DatasetIntegrityError(
                    f"Invalid segment status in {recording_id}/{segment.get('segment_id')}."
                )


def _validate_unique_segment_ids(segments: list[dict[str, Any]]) -> None:
    identifiers = [str(item.get("segment_id") or "") for item in segments]
    if any(not item for item in identifiers) or len(identifiers) != len(set(identifiers)):
        raise DatasetIntegrityError("Segment IDs must be non-empty and unique within a recording.")


def _migrate_manifest(payload: dict[str, Any], version: str, manifest_path: Path) -> dict[str, Any]:
    if version not in {"0.9", "1"}:
        raise DatasetIntegrityError(
            f"No safe migration is available from schema {version} to {CURRENT_SCHEMA_VERSION}."
        )
    backup = manifest_path.with_name(
        f"dataset.json.backup-{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
    )
    shutil.copy2(manifest_path, backup)
    migrated = deepcopy(payload)
    timestamp = _utc_now()
    migrated["schema_version"] = CURRENT_SCHEMA_VERSION
    migrated.setdefault("dataset_name", manifest_path.parent.name)
    migrated.setdefault("created_at", timestamp)
    migrated.setdefault("updated_at", timestamp)
    migrated.setdefault("language", "tr")
    migrated.setdefault("normalization_policy", NormalizationPolicy().to_dict())
    migrated.setdefault("glossary_references", [])
    migrated.setdefault("recordings", [])
    for recording_index, recording in enumerate(migrated["recordings"], start=1):
        recording.setdefault("recording_id", f"recording_{recording_index:06d}")
        recording.setdefault("audio_path", "")
        recording.setdefault("audio_sha256", "")
        recording.setdefault("meeting_id", recording["recording_id"])
        recording.setdefault("source_name", Path(str(recording.get("audio_path") or "audio")).name)
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
    migrated["annotation_statistics"] = _annotation_statistics(migrated["recordings"])
    _validate_manifest(migrated)
    atomic_write_json(manifest_path, migrated)
    return migrated


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()
