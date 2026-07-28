"""Recording and transcript domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .identifiers import MeetingId, RecordingId, SegmentId, TranscriptId


class RecordingStorageStatus(StrEnum):
    MANAGED = "managed"
    RETAINED = "retained"
    DELETED = "deleted"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class Recording:
    """Audio input associated with one meeting."""

    id: RecordingId
    meeting_id: MeetingId
    source_uri: str
    duration_seconds: float | None
    captured_at: datetime
    input_device: str | None = None
    storage_status: RecordingStorageStatus = RecordingStorageStatus.MANAGED
    keep_audio: bool = False
    deleted_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    """Source-preserving segment with raw and user-correctable text."""

    id: SegmentId
    transcript_id: TranscriptId
    position: int
    start_seconds: float
    end_seconds: float
    raw_text: str
    corrected_text: str
    speaker_label: str | None = None
    confidence: float | None = None
    speaker_confidence: float | None = None
    overlaps_speech: bool = False
    notes: tuple[str, ...] = ()
    diagnostics: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.position < 0:
            raise ValueError("Transcript segment position cannot be negative.")
        if self.start_seconds < 0 or self.end_seconds < self.start_seconds:
            raise ValueError("Transcript segment timestamps are invalid.")


@dataclass(frozen=True, slots=True)
class Transcript:
    """A transcript whose raw and corrected representations remain distinct."""

    id: TranscriptId
    meeting_id: MeetingId
    provider: str
    language: str | None
    raw_text: str
    corrected_text: str
    created_at: datetime
    updated_at: datetime
    conversation_id: str | None = None
    confidence: float | None = None
    segments: tuple[TranscriptSegment, ...] = ()
    diagnostics: dict[str, object] = field(default_factory=dict)
