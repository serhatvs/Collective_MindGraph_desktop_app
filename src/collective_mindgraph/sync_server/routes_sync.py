"""Push, pull, invalidation, and health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, Query, Request, WebSocket
from fastapi.websockets import WebSocketDisconnect

from .contracts import AccessDeniedError, Role, WorkspaceNotFoundError
from .http_support import principal_of, service_of
from .principals import IdentityError
from .schemas import PullResponse, PushRequest, PushResponse
from .service import SyncService

router = APIRouter(prefix="/sync/v1", tags=["sync"])


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    """Report liveness and negotiated limits without tenant detail."""

    settings = service_of(request).settings
    return {
        "status": "ok",
        "database": "postgresql" if settings.is_postgres else "sqlite",
        "push_operation_limit": settings.push_operation_limit,
        "push_byte_limit": settings.push_byte_limit,
        "blob_chunk_bytes": settings.blob_chunk_bytes,
        "pull_limit": settings.pull_limit,
    }


@router.post("/workspaces/{workspace_id}/push", response_model=PushResponse)
async def push(
    request: Request,
    workspace_id: str,
    payload: PushRequest,
    authorization: str | None = Header(default=None),
) -> PushResponse:
    """Apply an idempotent batch of opaque operations."""

    principal = await principal_of(request, authorization)
    result = await service_of(request).push(
        principal,
        workspace_id=workspace_id,
        device_id=payload.device_id,
        operations=[operation.to_input() for operation in payload.operations],
    )
    return PushResponse.of(result)


@router.get("/workspaces/{workspace_id}/pull", response_model=PullResponse)
async def pull(
    request: Request,
    workspace_id: str,
    cursor: str = Query(default="0"),
    limit: int | None = Query(default=None, ge=1),
    authorization: str | None = Header(default=None),
) -> PullResponse:
    """Return sealed changes after a cursor, in server order."""

    principal = await principal_of(request, authorization)
    page = await service_of(request).pull(
        principal,
        workspace_id=workspace_id,
        cursor=cursor,
        limit=limit,
    )
    return PullResponse.of(page)


@router.websocket("/workspaces/{workspace_id}/invalidations")
async def invalidations(websocket: WebSocket, workspace_id: str) -> None:
    """Stream cursor hints only; no ciphertext crosses this socket."""

    service: SyncService = websocket.app.state.sync_service
    if not await _authorize_socket(service, websocket, workspace_id):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    async with service.broadcaster.subscribe(workspace_id) as queue:
        try:
            while True:
                notification = await queue.get()
                await websocket.send_json(
                    {
                        "workspace_id": notification.workspace_id,
                        "cursor": notification.cursor,
                    }
                )
        except WebSocketDisconnect:
            return


async def _authorize_socket(
    service: SyncService,
    websocket: WebSocket,
    workspace_id: str,
) -> bool:
    try:
        principal = await service.principal(websocket.headers.get("authorization"))
        async with service.database.begin() as connection:
            await service.members.require_role(
                connection,
                workspace_id=workspace_id,
                principal=principal,
                minimum=Role.VIEWER,
            )
    except (IdentityError, AccessDeniedError, WorkspaceNotFoundError):
        return False
    return True


__all__ = ["router"]
