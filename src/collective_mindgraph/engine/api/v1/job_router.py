"""Background job status, cancellation, and retry endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from collective_mindgraph.application import PageRequest
from collective_mindgraph.domain import JobId, ProcessingStatus

from .errors import ERROR_RESPONSES
from .meeting_schemas import ProcessingJobPageResponse, ProcessingJobResponse
from .response_mapping import processing_job_response

router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


@router.get("/jobs", response_model=ProcessingJobPageResponse)
async def list_processing_jobs(
    request: Request,
    active_only: bool = False,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> ProcessingJobPageResponse:
    page = request.app.state.engine_context.jobs.list(
        PageRequest(cursor=cursor, limit=limit),
        active_only=active_only,
    )
    return ProcessingJobPageResponse(
        items=[processing_job_response(job) for job in page.items],
        total=page.total,
        next_cursor=page.next_cursor,
    )


@router.get("/jobs/{job_id}", response_model=ProcessingJobResponse)
async def get_job(request: Request, job_id: str) -> ProcessingJobResponse:
    job = request.app.state.engine_context.jobs.get(JobId(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Processing job not found.")
    return processing_job_response(job)


@router.post("/jobs/{job_id}/cancel", response_model=ProcessingJobResponse)
async def cancel_job(request: Request, job_id: str) -> ProcessingJobResponse:
    context = request.app.state.engine_context
    job = context.jobs.get(JobId(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Processing job not found.")
    if job.status not in {ProcessingStatus.PENDING, ProcessingStatus.RUNNING}:
        raise HTTPException(status_code=409, detail="Processing job is already terminal.")
    cancelled = await context.recording_jobs.cancel(job.id)
    if cancelled is None:
        raise HTTPException(status_code=404, detail="Processing job not found.")
    return processing_job_response(cancelled)


@router.post(
    "/jobs/{job_id}/retry",
    response_model=ProcessingJobResponse,
    status_code=202,
)
async def retry_job(request: Request, job_id: str) -> ProcessingJobResponse:
    try:
        retried = request.app.state.engine_context.recording_jobs.retry(JobId(job_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return processing_job_response(retried)
