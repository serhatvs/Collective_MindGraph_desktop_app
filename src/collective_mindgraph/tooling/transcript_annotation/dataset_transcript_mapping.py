"""Map transcription contracts into editable annotation manifest segments."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def model_payload(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return deepcopy(value)
    raise TypeError("Transcript must be a ConversationTranscript or mapping.")


def segments_from_transcript(
    transcript: dict[str, Any],
    timestamp: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, item in enumerate(transcript.get("segments", []), start=1):
        metadata = deepcopy(item.get("metadata") or {})
        asr_metadata = metadata.get("asr") if isinstance(metadata.get("asr"), dict) else metadata
        selective = (
            metadata.get("selective_retranscription")
            or (
                asr_metadata.get("selective_retranscription")
                if isinstance(asr_metadata, dict)
                else None
            )
            or {}
        )
        raw_text = str(item.get("raw_text") or "")
        selected_text = str(
            (
                asr_metadata.get("selected_raw_transcript")
                if isinstance(asr_metadata, dict)
                else None
            )
            or raw_text
        )
        original_start = float(item.get("start") or 0.0)
        original_end = float(item.get("end") or original_start)
        result.append(
            {
                "segment_id": str(item.get("segment_id") or f"segment_{index:06d}"),
                "original_start": original_start,
                "original_end": original_end,
                "reviewed_start": original_start,
                "reviewed_end": original_end,
                "raw_asr_text": raw_text,
                "selected_asr_text": selected_text,
                "cleaned_asr_text": str(item.get("corrected_text") or selected_text),
                "reference_text": selected_text,
                "annotation_status": "pending",
                "reviewer_notes": "",
                "confidence_metadata": {
                    "confidence": item.get("confidence"),
                    "words": deepcopy(item.get("words") or []),
                    "asr": (deepcopy(asr_metadata) if isinstance(asr_metadata, dict) else {}),
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
