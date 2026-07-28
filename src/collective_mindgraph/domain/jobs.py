"""Background processing job contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .identifiers import JobId, MeetingId, RecordingId, TranscriptId


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ProcessingJob:
    id: JobId
    kind: str
    status: ProcessingStatus
    progress: int
    created_at: datetime
    updated_at: datetime
    meeting_id: MeetingId | None = None
    recording_id: RecordingId | None = None
    parent_job_id: JobId | None = None
    result_transcript_id: TranscriptId | None = None
    message: str = ""
    error: str | None = None
    retryable: bool = False
    attributes: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0 <= self.progress <= 100:
            raise ValueError("Job progress must be between 0 and 100.")
