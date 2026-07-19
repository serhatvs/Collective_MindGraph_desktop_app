"""Export reviewed annotation segments without modifying source audio."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Iterable
import uuid
import wave

from .dataset import AnnotationDataset, atomic_write_json, atomic_write_text, sha256_file


EXPORT_FORMATS = ("csv", "jsonl", "hf")


def export_reviewed_dataset(
    dataset: AnnotationDataset,
    output_directory: Path,
    *,
    formats: Iterable[str] = EXPORT_FORMATS,
) -> dict[str, Any]:
    selected_formats = tuple(dict.fromkeys(str(item).lower() for item in formats))
    invalid_formats = sorted(set(selected_formats) - set(EXPORT_FORMATS))
    if invalid_formats:
        raise ValueError(f"Unsupported export formats: {', '.join(invalid_formats)}")
    output = output_directory.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    use_hf_layout = "hf" in selected_formats
    clips_root = output / "huggingface" / "audio" if use_hf_layout else output / "clips"
    clips_root.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    skipped: list[dict[str, str]] = []
    seen_segment_ids: set[tuple[str, str]] = set()
    verified_audio: dict[str, bool] = {}

    for recording in dataset.recordings:
        recording_id = str(recording["recording_id"])
        if recording.get("annotation_status") == "excluded":
            skipped.append({"recording_id": recording_id, "reason": "recording excluded"})
            continue
        audio_path = dataset.resolve_audio_path(recording)
        if not audio_path.is_file():
            warnings.append(f"Missing audio for {recording_id}: {audio_path}")
            continue
        if recording_id not in verified_audio:
            verified_audio[recording_id] = sha256_file(audio_path) == recording.get("audio_sha256")
        if not verified_audio[recording_id]:
            warnings.append(f"Audio hash mismatch for {recording_id}; recording skipped.")
            continue

        for segment in recording.get("segments", []):
            segment_id = str(segment.get("segment_id") or "")
            identity = (recording_id, segment_id)
            reason = _segment_skip_reason(segment, float(recording.get("duration") or 0.0))
            if identity in seen_segment_ids:
                reason = "duplicate segment"
            if reason:
                skipped.append(
                    {"recording_id": recording_id, "segment_id": segment_id, "reason": reason}
                )
                continue
            seen_segment_ids.add(identity)
            clip_name = f"{recording_id}__{_safe_name(segment_id)}.wav"
            clip_path = clips_root / clip_name
            cut_reviewed_audio_clip(
                audio_path,
                clip_path,
                start=float(segment["reviewed_start"]),
                end=float(segment["reviewed_end"]),
            )
            relative_audio = clip_path.relative_to(output).as_posix()
            row = {
                "audio": relative_audio,
                "sentence": str(segment["reference_text"]).strip(),
                "recording_id": recording_id,
                "meeting_id": str(recording.get("meeting_id") or recording_id),
                "segment_id": segment_id,
                "start": float(segment["reviewed_start"]),
                "end": float(segment["reviewed_end"]),
                "condition_tags": list(recording.get("recording_condition_tags") or []),
                "speaker_id": str(segment.get("speaker_id") or "unknown"),
                "audio_sha256": sha256_file(clip_path),
                "source_audio_sha256": recording.get("audio_sha256"),
                "source_audio": str(audio_path),
                "original_start": float(segment["original_start"]),
                "original_end": float(segment["original_end"]),
                "microphone_information": recording.get("microphone_information") or "",
                "room_information": recording.get("room_information") or "",
            }
            rows.append(row)

    generated_files: list[str] = []
    if "csv" in selected_formats:
        csv_path = output / "transcription.csv"
        _write_csv(csv_path, rows)
        generated_files.append(str(csv_path))
    if "jsonl" in selected_formats:
        jsonl_path = output / "transcription.jsonl"
        _write_jsonl(jsonl_path, rows)
        generated_files.append(str(jsonl_path))
    if "hf" in selected_formats:
        hf_path = output / "huggingface" / "metadata.csv"
        _write_huggingface_csv(hf_path, rows, output / "huggingface")
        generated_files.append(str(hf_path))

    summary = {
        "schema_version": "1.0",
        "dataset_name": dataset.manifest["dataset_name"],
        "requested_formats": list(selected_formats),
        "exported_segment_count": len(rows),
        "skipped_segment_count": len(skipped),
        "skipped": skipped,
        "warnings": warnings,
        "generated_files": generated_files,
        "audio_format": {"container": "WAV", "channels": 1, "sample_rate": 16000, "encoding": "PCM_S16LE"},
        "source_audio_modified": False,
    }
    summary_path = output / "export_validation.json"
    atomic_write_json(summary_path, summary)
    summary["generated_files"].append(str(summary_path))
    return summary


def cut_reviewed_audio_clip(source: Path, target: Path, *, start: float, end: float) -> None:
    if start < 0.0 or end <= start:
        raise ValueError("Audio clip boundaries are invalid.")
    target.parent.mkdir(parents=True, exist_ok=True)
    if _cut_standard_pcm_wav(source, target, start=start, end=end):
        return
    _cut_with_ffmpeg(source, target, start=start, end=end)


def _segment_skip_reason(segment: dict[str, Any], duration: float) -> str | None:
    if segment.get("annotation_status") != "reviewed":
        return f"status is {segment.get('annotation_status', 'pending')}"
    if segment.get("exclusion_reason"):
        return "segment has exclusion reason"
    if not str(segment.get("reference_text") or "").strip():
        return "empty reference"
    start = float(segment.get("reviewed_start") or 0.0)
    end = float(segment.get("reviewed_end") or 0.0)
    if start < 0.0 or end <= start or (duration > 0.0 and end > duration):
        return "invalid boundaries"
    return None


def _cut_standard_pcm_wav(source: Path, target: Path, *, start: float, end: float) -> bool:
    try:
        with wave.open(str(source), "rb") as reader:
            if (
                reader.getcomptype() != "NONE"
                or reader.getnchannels() != 1
                or reader.getframerate() != 16000
                or reader.getsampwidth() != 2
            ):
                return False
            total_frames = reader.getnframes()
            start_frame = max(0, min(total_frames, int(round(start * 16000))))
            end_frame = max(start_frame + 1, min(total_frames, int(round(end * 16000))))
            reader.setpos(start_frame)
            frames = reader.readframes(end_frame - start_frame)
    except (OSError, wave.Error):
        return False
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.stem}.", suffix=".tmp.wav", dir=target.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with wave.open(str(temporary), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(16000)
            writer.writeframes(frames)
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return True


def _cut_with_ffmpeg(source: Path, target: Path, *, start: float, end: float) -> None:
    ffmpeg = (os.getenv("CMG_RT_FFMPEG_PATH") or os.getenv("CMG_FFMPEG_EXE") or "ffmpeg").strip()
    temporary = target.with_name(f".{target.stem}.{uuid.uuid4().hex}.tmp.wav")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{start:.6f}",
        "-i",
        str(source),
        "-t",
        f"{end - start:.6f}",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(temporary),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        os.replace(temporary, target)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "ffmpeg is required to export non-16 kHz/mono/PCM WAV audio. Set CMG_RT_FFMPEG_PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffmpeg clip export failed: {exc.stderr.strip()}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = (
        "audio",
        "sentence",
        "recording_id",
        "meeting_id",
        "segment_id",
        "start",
        "end",
        "condition_tags",
        "speaker_id",
    )
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                projected = {key: row[key] for key in fields}
                projected["condition_tags"] = ",".join(row["condition_tags"])
                writer.writerow(projected)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    atomic_write_text(path, "\n".join(lines) + ("\n" if lines else ""))


def _write_huggingface_csv(path: Path, rows: list[dict[str, Any]], hf_root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ("file_name", "transcription", "recording_id", "meeting_id", "segment_id", "condition_tags", "speaker_id", "audio_sha256")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                clip = (hf_root.parent / row["audio"]).resolve()
                writer.writerow(
                    {
                        "file_name": clip.relative_to(hf_root).as_posix(),
                        "transcription": row["sentence"],
                        "recording_id": row["recording_id"],
                        "meeting_id": row["meeting_id"],
                        "segment_id": row["segment_id"],
                        "condition_tags": ",".join(row["condition_tags"]),
                        "speaker_id": row["speaker_id"],
                        "audio_sha256": row["audio_sha256"],
                    }
                )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
