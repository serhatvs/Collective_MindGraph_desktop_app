"""Engine-owned asyncio tasks for recording processing."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from collective_mindgraph.application import PageRequest
from collective_mindgraph.domain import (
    JobId,
    MeetingStatus,
    ProcessingJob,
    ProcessingStatus,
    Recording,
    RecordingStorageStatus,
)
from collective_mindgraph.infrastructure.audio.recording_storage import (
    ManagedRecordingStorage,
)
from collective_mindgraph.infrastructure.persistence import (
    SqliteJobStore,
    SqliteMeetingStore,
    SqliteRecordingStore,
)

from .runtime_manager import EngineRuntimeManager


class RecordingJobCoordinator:
    """Tracks actual tasks, cancellation, retry lineage, and audio retention."""

    def __init__(
        self,
        *,
        runtime: EngineRuntimeManager,
        jobs: SqliteJobStore,
        meetings: SqliteMeetingStore,
        recordings: SqliteRecordingStore,
        storage: ManagedRecordingStorage,
    ) -> None:
        self._runtime = runtime
        self._jobs = jobs
        self._meetings = meetings
        self._recordings = recordings
        self._storage = storage
        self._tasks: dict[JobId, asyncio.Task[None]] = {}
        self._meeting_locks: dict[int, asyncio.Lock] = {}
        self._live_meetings: dict[int, int] = {}

    def meeting_lock(self, meeting_id) -> asyncio.Lock:
        key = int(meeting_id)
        lock = self._meeting_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._meeting_locks[key] = lock
        return lock

    def begin_live_capture(self, meeting_id) -> None:
        key = int(meeting_id)
        self._live_meetings[key] = self._live_meetings.get(key, 0) + 1

    def end_live_capture(self, meeting_id) -> None:
        key = int(meeting_id)
        remaining = self._live_meetings.get(key, 0) - 1
        if remaining > 0:
            self._live_meetings[key] = remaining
        else:
            self._live_meetings.pop(key, None)

    def meeting_is_busy(self, meeting_id) -> bool:
        key = int(meeting_id)
        if self._live_meetings.get(key, 0) > 0:
            return True
        for job_id, task in self._tasks.items():
            if task.done():
                continue
            job = self._jobs.get(job_id)
            if job is not None and job.meeting_id == meeting_id:
                return True
        return False

    def recover_interrupted(self) -> int:
        recovered = 0
        while True:
            page = self._jobs.list(
                PageRequest(limit=200),
                active_only=True,
            )
            if not page.items:
                break
            for job in page.items:
                self._jobs.update(
                    job.id,
                    status=ProcessingStatus.FAILED,
                    message="Engine restarted before processing completed.",
                    error="engine_restarted",
                    retryable=job.recording_id is not None,
                    now=datetime.now(tz=UTC),
                )
                if job.recording_id is not None:
                    self._recordings.update_storage(
                        job.recording_id,
                        status=RecordingStorageStatus.RETAINED,
                    )
                if job.meeting_id is not None:
                    self._meetings.set_status(
                        job.meeting_id,
                        status=MeetingStatus.FAILED,
                        now=datetime.now(tz=UTC),
                    )
                recovered += 1
        return recovered

    def enqueue(
        self,
        recording: Recording,
        *,
        language: str | None = None,
        quality_mode: str | None = None,
        session_glossary_terms: list[str] | None = None,
        user_hotwords: list[str] | None = None,
        parent_job_id: JobId | None = None,
    ) -> ProcessingJob:
        options: dict[str, object] = {
            "language": language,
            "quality_mode": quality_mode,
            "session_glossary_terms": list(session_glossary_terms or []),
            "user_hotwords": list(user_hotwords or []),
        }
        job = self._runtime.snapshot().process_recording.create_job(
            meeting_id=recording.meeting_id,
            recording_id=recording.id,
            parent_job_id=parent_job_id,
            attributes=options,
        )
        self._meetings.set_status(
            recording.meeting_id,
            status=MeetingStatus.PROCESSING,
            now=datetime.now(tz=UTC),
        )
        task = asyncio.create_task(
            self._run(job, recording),
            name=f"recording-job-{job.id}",
        )
        self._tasks[job.id] = task
        return job

    def enqueue_reindex(
        self,
        *,
        parent_job_id: JobId | None = None,
    ) -> ProcessingJob:
        now = datetime.now(tz=UTC)
        job = ProcessingJob(
            id=JobId(str(uuid4())),
            kind="knowledge_reindex",
            status=ProcessingStatus.PENDING,
            progress=0,
            message="Knowledge reindex queued.",
            retryable=False,
            parent_job_id=parent_job_id,
            created_at=now,
            updated_at=now,
        )
        self._jobs.create(job)
        task = asyncio.create_task(
            self._run_reindex(job),
            name=f"knowledge-reindex-{job.id}",
        )
        self._tasks[job.id] = task
        return job

    async def cancel(self, job_id: JobId) -> ProcessingJob | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        if job.status not in {ProcessingStatus.PENDING, ProcessingStatus.RUNNING}:
            return job
        cancelled = self._jobs.update(
            job.id,
            status=ProcessingStatus.CANCELLED,
            message="Recording processing cancelled.",
            retryable=job.recording_id is not None,
            now=datetime.now(tz=UTC),
        )
        task = self._tasks.get(job.id)
        if task is not None and not task.done():
            task.cancel()
        if job.recording_id is not None:
            self._recordings.update_storage(
                job.recording_id,
                status=RecordingStorageStatus.RETAINED,
            )
        if job.meeting_id is not None:
            self._meetings.set_status(
                job.meeting_id,
                status=MeetingStatus.FAILED,
                now=datetime.now(tz=UTC),
            )
        return cancelled

    def retry(self, job_id: JobId) -> ProcessingJob:
        original = self._jobs.get(job_id)
        if original is None:
            raise LookupError("Processing job not found.")
        if original.status not in {
            ProcessingStatus.FAILED,
            ProcessingStatus.CANCELLED,
        }:
            raise ValueError("Only failed or cancelled jobs can be retried.")
        if original.kind == "knowledge_reindex" and original.retryable:
            return self.enqueue_reindex(parent_job_id=original.id)
        if not original.retryable or original.recording_id is None:
            raise ValueError("The recording for this job is not available for retry.")
        recording = self._recordings.get(original.recording_id)
        if recording is None:
            raise ValueError("The recording for this job no longer exists.")
        path = self._storage.resolve(recording.source_uri)
        if not path.is_file():
            self._recordings.update_storage(
                recording.id,
                status=RecordingStorageStatus.MISSING,
            )
            raise ValueError("The retained recording file is missing.")
        attributes = original.attributes
        return self.enqueue(
            recording,
            language=_optional_text(attributes.get("language")),
            quality_mode=_optional_text(attributes.get("quality_mode")),
            session_glossary_terms=_string_list(attributes.get("session_glossary_terms")),
            user_hotwords=_string_list(attributes.get("user_hotwords")),
            parent_job_id=original.id,
        )

    async def shutdown(self) -> None:
        tasks = [task for task in self._tasks.values() if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    async def _run(self, job: ProcessingJob, recording: Recording) -> None:
        try:
            path = self._storage.resolve(recording.source_uri)
            if not path.is_file():
                raise FileNotFoundError("Managed recording file is missing.")
            bundle = self._runtime.snapshot()
            attributes = job.attributes
            processed_job, _result = await bundle.process_recording.run(
                job,
                path,
                language=_optional_text(attributes.get("language")),
                quality_mode=_optional_text(attributes.get("quality_mode")),
                session_glossary_terms=_string_list(attributes.get("session_glossary_terms")),
                user_hotwords=_string_list(attributes.get("user_hotwords")),
                recording_source_uri=recording.source_uri,
                finalize_job=False,
            )
            await asyncio.to_thread(
                bundle.index_knowledge,
                recording.meeting_id,
            )
            self._apply_success_retention(recording)
            self._jobs.update(
                job.id,
                status=ProcessingStatus.SUCCEEDED,
                progress=100,
                message="Recording processing completed.",
                retryable=False,
                result_transcript_id=processed_job.result_transcript_id,
                now=datetime.now(tz=UTC),
            )
        except asyncio.CancelledError:
            self._recordings.update_storage(
                recording.id,
                status=RecordingStorageStatus.RETAINED,
            )
            self._meetings.set_status(
                recording.meeting_id,
                status=MeetingStatus.FAILED,
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
            self._recordings.update_storage(
                recording.id,
                status=RecordingStorageStatus.RETAINED,
            )
            self._meetings.set_status(
                recording.meeting_id,
                status=MeetingStatus.FAILED,
                now=datetime.now(tz=UTC),
            )
        finally:
            self._tasks.pop(job.id, None)

    async def _run_reindex(self, job: ProcessingJob) -> None:
        self._jobs.update(
            job.id,
            status=ProcessingStatus.RUNNING,
            progress=10,
            message="Indexing canonical knowledge.",
            now=datetime.now(tz=UTC),
        )
        try:
            count = await asyncio.to_thread(self._runtime.snapshot().index_knowledge)
        except asyncio.CancelledError:
            self._jobs.update(
                job.id,
                status=ProcessingStatus.CANCELLED,
                message="Knowledge reindex cancelled.",
                retryable=True,
                now=datetime.now(tz=UTC),
            )
            raise
        except Exception as exc:
            self._jobs.update(
                job.id,
                status=ProcessingStatus.FAILED,
                message="Knowledge reindex failed.",
                error=str(exc),
                retryable=True,
                now=datetime.now(tz=UTC),
            )
        else:
            self._jobs.update(
                job.id,
                status=ProcessingStatus.SUCCEEDED,
                progress=100,
                message=f"Indexed {count} knowledge nodes.",
                retryable=False,
                now=datetime.now(tz=UTC),
            )
        finally:
            self._tasks.pop(job.id, None)

    def _apply_success_retention(self, recording: Recording) -> None:
        if recording.keep_audio:
            self._recordings.update_storage(
                recording.id,
                status=RecordingStorageStatus.RETAINED,
            )
            return
        self._storage.delete(recording.source_uri)
        self._recordings.update_storage(
            recording.id,
            status=RecordingStorageStatus.DELETED,
            deleted_at=datetime.now(tz=UTC),
        )


def _optional_text(value: object) -> str | None:
    rendered = str(value).strip() if value is not None else ""
    return rendered or None


def _string_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = [str(item).strip() for item in value if str(item).strip()]
    return items or None
