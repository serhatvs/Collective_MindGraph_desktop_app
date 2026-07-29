"""Comments, mentions, and workspace activity for the desktop."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from collective_mindgraph.domain import ActivityKind, Comment
from collective_mindgraph.domain.collaboration import MAX_COMMENT_CHARACTERS
from collective_mindgraph.domain.identifiers import CommentId, SyncId, WorkspaceId
from collective_mindgraph.infrastructure.persistence import SqliteCollaborationStore

router = APIRouter(prefix="/api/v2/collaboration", tags=["collaboration"])

MAX_ACTIVITY_LIMIT = 500


class CommentRequest(BaseModel):
    target_type: str = Field(min_length=1, max_length=60)
    target_sync_id: str
    body: str = Field(min_length=1, max_length=MAX_COMMENT_CHARACTERS)
    author_subject: str = Field(min_length=1, max_length=320)
    parent_id: str | None = None
    meeting_id: int | None = None


class CommentResponse(BaseModel):
    id: str
    target_type: str
    target_sync_id: str
    body: str
    author_subject: str
    created_at: datetime
    parent_id: str | None = None
    mentions: list[str] = Field(default_factory=list)
    is_reply: bool = False


class ActivityResponse(BaseModel):
    id: str
    kind: str
    created_at: datetime
    actor_subject: str | None = None
    object_type: str | None = None
    object_sync_id: str | None = None
    details: dict[str, str] = Field(default_factory=dict)


def _store(request: Request) -> SqliteCollaborationStore:
    store: SqliteCollaborationStore = request.app.state.engine_context.collaboration
    return store


def _comment_response(comment: Comment) -> CommentResponse:
    return CommentResponse(
        id=str(comment.id),
        target_type=comment.target_type,
        target_sync_id=str(comment.target_sync_id),
        body=comment.body,
        author_subject=comment.author_subject,
        created_at=comment.created_at,
        parent_id=str(comment.parent_id) if comment.parent_id else None,
        mentions=list(comment.mentions),
        is_reply=comment.is_reply,
    )


@router.post("/{workspace_id}/comments", response_model=CommentResponse, status_code=201)
async def add_comment(
    request: Request,
    workspace_id: str,
    payload: CommentRequest,
) -> CommentResponse:
    """Append one comment; mentions are parsed from the body itself."""

    try:
        comment = _store(request).add_comment(
            workspace_id=WorkspaceId(workspace_id),
            target_type=payload.target_type,
            target_sync_id=SyncId(payload.target_sync_id),
            body=payload.body,
            author_subject=payload.author_subject,
            parent_id=CommentId(payload.parent_id) if payload.parent_id else None,
            meeting_id=payload.meeting_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _comment_response(comment)


@router.get("/{workspace_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    request: Request,
    workspace_id: str,
    target_type: str = Query(min_length=1),
    target_sync_id: str = Query(min_length=1),
) -> list[CommentResponse]:
    """Return one entity's thread in the order it was written."""

    comments = _store(request).comments_for(
        WorkspaceId(workspace_id),
        target_type=target_type,
        target_sync_id=SyncId(target_sync_id),
    )
    return [_comment_response(comment) for comment in comments]


@router.get("/{workspace_id}/mentions", response_model=list[CommentResponse])
async def list_mentions(
    request: Request,
    workspace_id: str,
    subject: str = Query(min_length=1),
    limit: int = Query(default=100, ge=1, le=MAX_ACTIVITY_LIMIT),
) -> list[CommentResponse]:
    """Return comments that mention one member, newest first."""

    comments = _store(request).mentions_of(WorkspaceId(workspace_id), subject, limit=limit)
    return [_comment_response(comment) for comment in comments]


@router.get("/{workspace_id}/activity", response_model=list[ActivityResponse])
async def list_activity(
    request: Request,
    workspace_id: str,
    limit: int = Query(default=100, ge=1, le=MAX_ACTIVITY_LIMIT),
) -> list[ActivityResponse]:
    """Return the newest workspace activity."""

    return [
        ActivityResponse(
            id=str(event.id),
            kind=event.kind.value,
            created_at=event.created_at,
            actor_subject=event.actor_subject,
            object_type=event.object_type,
            object_sync_id=str(event.object_sync_id) if event.object_sync_id else None,
            details=dict(event.details),
        )
        for event in _store(request).recent_activity(WorkspaceId(workspace_id), limit=limit)
    ]


@router.get("/kinds", response_model=list[str])
async def activity_kinds() -> list[str]:
    """Expose the fixed activity vocabulary the desktop renders."""

    return [kind.value for kind in ActivityKind]


__all__ = ["MAX_ACTIVITY_LIMIT", "router"]
