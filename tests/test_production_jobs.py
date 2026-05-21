
import pytest
from collective_mindgraph_desktop.ui.jobs import JOB_REGISTRY, JobStatus

def test_job_registry_lifecycle():
    # 1. Create
    job = JOB_REGISTRY.create_job("test_type", "Starting test")
    assert job.status == JobStatus.PENDING
    assert job.type == "test_type"
    
    # 2. Update to Running
    JOB_REGISTRY.update_job(job.id, status=JobStatus.RUNNING, progress=50, message="Halfway there")
    updated = JOB_REGISTRY.get_job(job.id)
    assert updated.status == JobStatus.RUNNING
    assert updated.progress == 50
    assert updated.message == "Halfway there"
    
    # 3. Complete
    JOB_REGISTRY.update_job(job.id, status=JobStatus.SUCCEEDED, progress=100)
    final = JOB_REGISTRY.get_job(job.id)
    assert final.status == JobStatus.SUCCEEDED
    
    # 4. List
    all_jobs = JOB_REGISTRY.list_all_jobs()
    assert any(j.id == job.id for j in all_jobs)
    
    active = JOB_REGISTRY.list_active_jobs()
    assert not any(j.id == job.id for j in active) # Should be empty since it succeeded
