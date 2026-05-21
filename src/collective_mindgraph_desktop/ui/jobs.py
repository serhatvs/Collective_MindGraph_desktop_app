"""Production job registry for tracking background tasks."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Dict, Optional, List, Any

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Job:
    id: str
    type: str
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    message: str = ""
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

class JobRegistry:
    """In-memory registry for tracking UI background jobs."""
    
    def __init__(self):
        self._jobs: Dict[str, Job] = {}

    def create_job(self, job_type: str, message: str = "Starting...") -> Job:
        job_id = str(uuid.uuid4())
        job = Job(id=job_id, type=job_type, message=message)
        self._jobs[job_id] = job
        return job

    def update_job(self, job_id: str, status: Optional[JobStatus] = None, progress: Optional[int] = None, message: Optional[str] = None, error: Optional[str] = None):
        if job_id not in self._jobs:
            return
        
        job = self._jobs[job_id]
        if status: job.status = status
        if progress is not None: job.progress = progress
        if message: job.message = message
        if error: job.error = error
        
        job.updated_at = datetime.now(UTC)

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list_active_jobs(self) -> List[Job]:
        return [j for j in self._jobs.values() if j.status in (JobStatus.PENDING, JobStatus.RUNNING)]

    def list_all_jobs(self) -> List[Job]:
        return list(self._jobs.values())

# Global registry instance
JOB_REGISTRY = JobRegistry()
