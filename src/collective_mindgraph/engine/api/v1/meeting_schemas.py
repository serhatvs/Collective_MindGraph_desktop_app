"""Transport schemas for meetings, transcripts, and the dashboard."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MeetingResponse(BaseModel):
    id: int
    title: str
    status: str
    input_device: str | None = None
    created_at: datetime
    updated_at: datetime


class MeetingPageResponse(BaseModel):
    items: list[MeetingResponse] = Field(default_factory=list)
    total: int
    next_cursor: str | None = None


class CreateMeetingRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    input_device: str | None = Field(default=None, max_length=240)


class UpdateMeetingRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    archived: bool | None = None


class TranscriptSegmentResponse(BaseModel):
    id: str
    position: int
    start_seconds: float
    end_seconds: float
    speaker_label: str | None = None
    raw_text: str
    corrected_text: str
    confidence: float | None = None
    needs_review: bool = False


class TranscriptResponse(BaseModel):
    id: int
    meeting_id: int
    conversation_id: str | None = None
    provider: str
    language: str | None = None
    raw_text: str
    corrected_text: str
    confidence: float | None = None
    created_at: datetime
    updated_at: datetime
    segments: list[TranscriptSegmentResponse] = Field(default_factory=list)


class UpdateTranscriptSegmentRequest(BaseModel):
    corrected_text: str = Field(min_length=1)


class ProcessingJobResponse(BaseModel):
    id: str
    meeting_id: int | None = None
    recording_id: str | None = None
    parent_job_id: str | None = None
    result_transcript_id: int | None = None
    kind: str
    status: str
    progress: int
    message: str
    error: str | None = None
    retryable: bool = False
    created_at: datetime
    updated_at: datetime


class ProcessingJobPageResponse(BaseModel):
    items: list[ProcessingJobResponse] = Field(default_factory=list)
    total: int
    next_cursor: str | None = None


class DashboardResponse(BaseModel):
    total_meetings: int
    total_transcripts: int
    total_knowledge_nodes: int
    pending_reviews: int
    recent_meetings: list[MeetingResponse] = Field(default_factory=list)
