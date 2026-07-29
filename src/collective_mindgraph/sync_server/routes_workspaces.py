"""Workspace, membership, device, envelope, and usage endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Body, Header, Request, Response

from .contracts import Role
from .http_support import (
    encode_bytes,
    optional_bytes,
    principal_of,
    required_bytes,
    service_of,
)
from .schemas import (
    DeviceRequest,
    EnvelopeRequest,
    EnvelopeResponse,
    MembershipRequest,
    UsageResponse,
    WorkspaceRequest,
    WorkspaceResponse,
)
from .service import WorkspaceSummary

router = APIRouter(prefix="/sync/v1", tags=["workspaces"])


@router.get("/workspaces", response_model=list[WorkspaceResponse])
async def list_workspaces(
    request: Request,
    authorization: str | None = Header(default=None),
) -> list[WorkspaceResponse]:
    principal = await principal_of(request, authorization)
    summaries = await service_of(request).list_workspaces(principal)
    return [_summary_response(summary) for summary in summaries]


@router.post("/workspaces", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    request: Request,
    payload: WorkspaceRequest,
    authorization: str | None = Header(default=None),
) -> WorkspaceResponse:
    principal = await principal_of(request, authorization)
    summary = await service_of(request).create_workspace(
        principal,
        name=payload.name,
        workspace_id=payload.workspace_id,
    )
    return _summary_response(summary)


@router.put("/workspaces/{workspace_id}/raw-audio", status_code=204)
async def set_raw_audio(
    request: Request,
    workspace_id: str,
    enabled: bool = Body(embed=True),
    authorization: str | None = Header(default=None),
) -> Response:
    """Raw-audio sync stays opt-in per workspace and defaults to off."""

    principal = await principal_of(request, authorization)
    await service_of(request).set_raw_audio(
        principal,
        workspace_id=workspace_id,
        enabled=enabled,
    )
    return Response(status_code=204)


@router.put("/workspaces/{workspace_id}/members", status_code=204)
async def upsert_member(
    request: Request,
    workspace_id: str,
    payload: MembershipRequest,
    authorization: str | None = Header(default=None),
) -> Response:
    service = service_of(request)
    principal = await principal_of(request, authorization)
    async with service.database.begin() as connection:
        await service.members.require_role(
            connection,
            workspace_id=workspace_id,
            principal=principal,
            minimum=Role.ADMIN,
        )
        member = await service.members.ensure_user(
            connection,
            tenant_id=principal.tenant_id,
            issuer=payload.issuer,
            subject=payload.subject,
        )
        await service.members.upsert_membership(
            connection,
            workspace_id=workspace_id,
            user_id=member.user_id,
            role=payload.role,
        )
        await service.members.record_audit(
            connection,
            workspace_id=workspace_id,
            kind="membership.updated",
            principal=principal,
        )
    return Response(status_code=204)


@router.delete("/workspaces/{workspace_id}/members/{subject}", status_code=204)
async def remove_member(
    request: Request,
    workspace_id: str,
    subject: str,
    issuer: str = Body(embed=True),
    authorization: str | None = Header(default=None),
) -> Response:
    service = service_of(request)
    principal = await principal_of(request, authorization)
    async with service.database.begin() as connection:
        await service.members.require_role(
            connection,
            workspace_id=workspace_id,
            principal=principal,
            minimum=Role.ADMIN,
        )
        member = await service.members.ensure_user(
            connection,
            tenant_id=principal.tenant_id,
            issuer=issuer,
            subject=subject,
        )
        await service.members.remove_membership(
            connection,
            workspace_id=workspace_id,
            user_id=member.user_id,
        )
        await service.members.record_audit(
            connection,
            workspace_id=workspace_id,
            kind="membership.removed",
            principal=principal,
        )
    return Response(status_code=204)


@router.post("/workspaces/{workspace_id}/devices", status_code=204)
async def register_device(
    request: Request,
    workspace_id: str,
    payload: DeviceRequest,
    authorization: str | None = Header(default=None),
) -> Response:
    principal = await principal_of(request, authorization)
    await service_of(request).devices.register(
        principal,
        workspace_id=workspace_id,
        device_id=payload.device_id,
        name=payload.name,
        public_key=payload.public_key_bytes(),
    )
    return Response(status_code=204)


@router.delete("/workspaces/{workspace_id}/devices/{device_id}", status_code=204)
async def revoke_device(
    request: Request,
    workspace_id: str,
    device_id: str,
    authorization: str | None = Header(default=None),
) -> Response:
    principal = await principal_of(request, authorization)
    await service_of(request).devices.revoke(
        principal,
        workspace_id=workspace_id,
        device_id=device_id,
    )
    return Response(status_code=204)


@router.post("/workspaces/{workspace_id}/envelopes", status_code=201)
async def store_envelope(
    request: Request,
    workspace_id: str,
    payload: EnvelopeRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    """Store a wrapped key the service is unable to unwrap."""

    principal = await principal_of(request, authorization)
    envelope_id = await service_of(request).devices.store_envelope(
        principal,
        workspace_id=workspace_id,
        key_version=payload.key_version,
        wrapped_key=required_bytes(payload.wrapped_key, "wrapped key"),
        recipient_device_id=payload.recipient_device_id,
        ephemeral_public_key=optional_bytes(payload.ephemeral_public_key),
        salt=optional_bytes(payload.salt),
    )
    return {"id": envelope_id}


@router.get(
    "/workspaces/{workspace_id}/devices/{device_id}/envelopes",
    response_model=list[EnvelopeResponse],
)
async def list_envelopes(
    request: Request,
    workspace_id: str,
    device_id: str,
    authorization: str | None = Header(default=None),
) -> list[EnvelopeResponse]:
    principal = await principal_of(request, authorization)
    rows = await service_of(request).devices.envelopes_for(
        principal,
        workspace_id=workspace_id,
        device_id=device_id,
    )
    return [
        EnvelopeResponse(
            id=str(row.id),
            key_version=int(row.key_version),
            wrapped_key=encode_bytes(bytes(row.wrapped_key)),
            recipient_device_id=(
                str(row.recipient_device_id) if row.recipient_device_id is not None else None
            ),
            ephemeral_public_key=(
                encode_bytes(bytes(row.ephemeral_public_key))
                if row.ephemeral_public_key is not None
                else None
            ),
            salt=encode_bytes(bytes(row.salt)) if row.salt is not None else None,
        )
        for row in rows
    ]


@router.get("/workspaces/{workspace_id}/usage", response_model=UsageResponse)
async def usage(
    request: Request,
    workspace_id: str,
    authorization: str | None = Header(default=None),
) -> UsageResponse:
    """Report content-free quota counters."""

    principal = await principal_of(request, authorization)
    counters = await service_of(request).usage(principal, workspace_id=workspace_id)
    return UsageResponse(workspace_id=workspace_id, **counters)


def _summary_response(summary: WorkspaceSummary) -> WorkspaceResponse:
    return WorkspaceResponse(
        workspace_id=summary.workspace_id,
        name=summary.name,
        role=summary.role.value,
        raw_audio_enabled=summary.raw_audio_enabled,
    )


__all__ = ["router"]
