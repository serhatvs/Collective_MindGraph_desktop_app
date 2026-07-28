"""Processing-job persistence port."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from collective_mindgraph.application.pagination import Page, PageRequest
from collective_mindgraph.domain import (
    JobId,
    ProcessingJob,
    ProcessingStatus,
    TranscriptId,
)


class JobStore(Protocol):
    def create(self, job: ProcessingJob) -> None: ...

    def get(self, job_id: JobId) -> ProcessingJob | None: ...

    def list(self, request: PageRequest, *, active_only: bool = False) -> Page[ProcessingJob]: ...

    def update(
        self,
        job_id: JobId,
        *,
        status: ProcessingStatus | None = None,
        progress: int | None = None,
        message: str | None = None,
        error: str | None = None,
        retryable: bool | None = None,
        result_transcript_id: TranscriptId | None = None,
        now: datetime,
    ) -> ProcessingJob | None: ...
