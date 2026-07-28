"""Shared domain-to-v1 response mapping."""

from .meeting_schemas import ProcessingJobResponse


def processing_job_response(job) -> ProcessingJobResponse:
    return ProcessingJobResponse(
        id=str(job.id),
        meeting_id=int(job.meeting_id) if job.meeting_id is not None else None,
        recording_id=str(job.recording_id) if job.recording_id is not None else None,
        parent_job_id=(str(job.parent_job_id) if job.parent_job_id is not None else None),
        result_transcript_id=(
            int(job.result_transcript_id) if job.result_transcript_id is not None else None
        ),
        kind=job.kind,
        status=job.status.value,
        progress=job.progress,
        message=job.message,
        error=job.error,
        retryable=job.retryable,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
