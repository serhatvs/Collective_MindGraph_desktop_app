"""Tracked recording-ingest workflow."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from collective_mindgraph.application.ports import JobStore
from collective_mindgraph.domain import (
    JobId,
    MeetingId,
    ProcessingJob,
    ProcessingStatus,
    RecordingId,
    TranscriptId,
)

from .contracts import ConversationTranscript
from .transcribe_recording import TranscribeRecording


class ProcessRecording:
    def __init__(self, transcription: TranscribeRecording, jobs: JobStore) -> None:
        self._transcription = transcription
        self._jobs = jobs

    def create_job(
        self,
        *,
        meeting_id: MeetingId,
        recording_id: RecordingId | None = None,
        parent_job_id: JobId | None = None,
        attributes: dict[str, object] | None = None,
    ) -> ProcessingJob:
        now = datetime.now(tz=UTC)
        job = ProcessingJob(
            id=JobId(str(uuid4())),
            meeting_id=meeting_id,
            recording_id=recording_id,
            parent_job_id=parent_job_id,
            kind="recording_transcription",
            status=ProcessingStatus.PENDING,
            progress=0,
            message="Recording queued.",
            created_at=now,
            updated_at=now,
            attributes=dict(attributes or {}),
        )
        self._jobs.create(job)
        return job

    async def run(
        self,
        job: ProcessingJob,
        source_path: Path,
        *,
        language: str | None = None,
        quality_mode: str | None = None,
        session_glossary_terms: list[str] | None = None,
        user_hotwords: list[str] | None = None,
        recording_source_uri: str | None = None,
        finalize_job: bool = True,
    ) -> tuple[ProcessingJob, ConversationTranscript]:
        if job.meeting_id is None:
            raise ValueError("Recording jobs require a meeting.")
        self._update_progress(job.id, "preparing", 1)
        try:
            result = await self._transcription.transcribe_file(
                source_path,
                meeting_id=job.meeting_id,
                language=language,
                quality_mode=quality_mode,
                session_glossary_terms=session_glossary_terms,
                user_hotwords=user_hotwords,
                source="upload",
                recording_source_uri=recording_source_uri,
                recording_id=job.recording_id,
                progress_callback=lambda stage, progress: self._update_progress(
                    job.id, stage, progress
                ),
            )
        except asyncio.CancelledError:
            self._jobs.update(
                job.id,
                status=ProcessingStatus.CANCELLED,
                message="Recording processing cancelled.",
                retryable=True,
                now=datetime.now(tz=UTC),
            )
            raise
        except Exception as exc:
            self._jobs.update(
                job.id,
                status=ProcessingStatus.FAILED,
                message="Recording processing failed.",
                error=str(exc),
                retryable=True,
                now=datetime.now(tz=UTC),
            )
            raise
        transcript_id = _result_transcript_id(result)
        completed = self._jobs.update(
            job.id,
            status=(ProcessingStatus.SUCCEEDED if finalize_job else ProcessingStatus.RUNNING),
            progress=100 if finalize_job else 95,
            message=(
                "Recording processing completed."
                if finalize_job
                else "Recording persistence completed."
            ),
            retryable=not finalize_job,
            result_transcript_id=transcript_id,
            now=datetime.now(tz=UTC),
        )
        if completed is None:
            raise RuntimeError("Processing job disappeared before completion.")
        return completed, result

    async def __call__(
        self,
        source_path: Path,
        *,
        meeting_id: MeetingId,
        language: str | None = None,
        quality_mode: str | None = None,
        session_glossary_terms: list[str] | None = None,
        user_hotwords: list[str] | None = None,
        recording_source_uri: str | None = None,
        recording_id: RecordingId | None = None,
        parent_job_id: JobId | None = None,
    ) -> tuple[ProcessingJob, ConversationTranscript]:
        job = self.create_job(
            meeting_id=meeting_id,
            recording_id=recording_id,
            parent_job_id=parent_job_id,
        )
        return await self.run(
            job,
            source_path,
            language=language,
            quality_mode=quality_mode,
            session_glossary_terms=session_glossary_terms,
            user_hotwords=user_hotwords,
            recording_source_uri=recording_source_uri,
            finalize_job=True,
        )

    def _update_progress(self, job_id: JobId, stage: str, progress: int) -> None:
        self._jobs.update(
            job_id,
            status=ProcessingStatus.RUNNING,
            progress=progress,
            message=stage,
            now=datetime.now(tz=UTC),
        )


def _result_transcript_id(result: ConversationTranscript) -> TranscriptId | None:
    value = result.metadata.get("transcript_id")
    return TranscriptId(value) if isinstance(value, int) and value > 0 else None
