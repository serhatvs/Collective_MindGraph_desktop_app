"""Synchronization status, runs, and the conflict inbox.

The desktop reaches the cloud only through these localhost routes. The engine
owns the outbox, the cursor, and every decision about conflicting revisions.
"""

from __future__ import annotations

from base64 import b64decode
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from collective_mindgraph.application.sync.agent import ConflictNotFoundError, SyncAgent
from collective_mindgraph.domain import ConflictResolution
from collective_mindgraph.domain.identifiers import ConflictId, DeviceId, WorkspaceId

router = APIRouter(prefix="/api/v2/sync", tags=["sync"])


class SyncStatusResponse(BaseModel):
    workspace_id: str
    phase: str
    pending_operations: int
    open_conflicts: int
    cursor: str
    is_settled: bool
    poll_seconds: float
    last_pull_at: datetime | None = None
    last_push_at: datetime | None = None
    last_error: str | None = None


class SyncRunResponse(BaseModel):
    workspace_id: str
    pushed: int
    duplicates: int
    pulled: int
    conflicts: int
    cursor: str
    has_more: bool
    skipped_reason: str | None = None
    error: str | None = None


class ConflictResponse(BaseModel):
    id: str
    object_id: str
    object_type: str
    local_revision: int
    remote_revision: int
    created_at: datetime


class ResolutionRequest(BaseModel):
    resolution: ConflictResolution
    merged_payload: str | None = Field(default=None)

    def merged_bytes(self) -> bytes | None:
        if self.merged_payload is None:
            return None
        try:
            return b64decode(self.merged_payload, validate=True)
        except ValueError as error:
            raise HTTPException(status_code=422, detail="Merged payload must be base64.") from error


class ResolutionResponse(BaseModel):
    resolved: str
    requeued_operation_id: str | None = None


def _agent(request: Request) -> SyncAgent:
    agent: SyncAgent | None = getattr(request.app.state.engine_context, "sync_agent", None)
    if agent is None:
        raise HTTPException(status_code=503, detail="Synchronization is not configured.")
    return agent


def _device(request: Request) -> DeviceId:
    device_id = request.app.state.engine_context.key_envelopes.current_device_id()
    if device_id is None:
        raise HTTPException(status_code=409, detail="This device is not enrolled yet.")
    return DeviceId(str(device_id))


@router.get("/{workspace_id}/status", response_model=SyncStatusResponse)
async def status(request: Request, workspace_id: str) -> SyncStatusResponse:
    """Report queue depth, conflicts, and the next poll without any network."""

    agent = _agent(request)
    identifier = WorkspaceId(workspace_id)
    state = agent.status(identifier)
    return SyncStatusResponse(
        workspace_id=str(state.workspace_id),
        phase=state.phase.value,
        pending_operations=state.pending_operations,
        open_conflicts=state.open_conflicts,
        cursor=state.cursor,
        is_settled=state.is_settled,
        poll_seconds=agent.next_interval_seconds(identifier, foreground=True),
        last_pull_at=state.last_pull_at,
        last_push_at=state.last_push_at,
        last_error=state.last_error,
    )


@router.post("/{workspace_id}/run", response_model=SyncRunResponse)
async def run(request: Request, workspace_id: str) -> SyncRunResponse:
    """Run one pass now, as the "synchronize now" control does."""

    report = _agent(request).run_once(
        WorkspaceId(workspace_id),
        device_id=_device(request),
    )
    return SyncRunResponse(
        workspace_id=str(report.workspace_id),
        pushed=report.pushed,
        duplicates=report.duplicates,
        pulled=report.pulled,
        conflicts=len(report.conflicts),
        cursor=report.cursor,
        has_more=report.has_more,
        skipped_reason=report.skipped_reason,
        error=report.error,
    )


@router.get("/{workspace_id}/conflicts", response_model=list[ConflictResponse])
async def conflicts(request: Request, workspace_id: str) -> list[ConflictResponse]:
    """List the changes waiting for a decision."""

    outbox = request.app.state.engine_context.outbox
    return [
        ConflictResponse(
            id=str(conflict.id),
            object_id=str(conflict.object_id),
            object_type=conflict.object_type,
            local_revision=conflict.local_revision,
            remote_revision=conflict.remote_revision,
            created_at=conflict.created_at,
        )
        for conflict in outbox.open_conflicts(WorkspaceId(workspace_id))
    ]


@router.post("/conflicts/{conflict_id}/resolve", response_model=ResolutionResponse)
async def resolve(
    request: Request,
    conflict_id: str,
    payload: ResolutionRequest,
) -> ResolutionResponse:
    """Settle one conflict, re-queueing the chosen version when needed."""

    try:
        entry = _agent(request).resolve(
            ConflictId(conflict_id),
            payload.resolution,
            merged_payload=payload.merged_bytes(),
        )
    except ConflictNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return ResolutionResponse(
        resolved=payload.resolution.value,
        requeued_operation_id=str(entry.operation_id) if entry is not None else None,
    )


__all__ = ["router"]
