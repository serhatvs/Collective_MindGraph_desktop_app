"""Content-free administration surface.

Every page renders membership, device, quota, and audit metadata only. No
route can reach ciphertext, and the templates have no way to render it, so the
surface cannot leak content even if a future query returned it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from .admin_security import (
    CSRF_FIELD,
    SECURITY_HEADERS,
    SESSION_COOKIE,
    AdminSecurityError,
    AdminSession,
    require_csrf,
)
from .contracts import Role
from .service import SyncService
from .tables import audit_events, devices, memberships, usage_counters, user_subjects, workspaces

router = APIRouter(prefix="/admin", tags=["admin"])

AUDIT_PAGE_SIZE = 50


def _service(request: Request) -> SyncService:
    service: SyncService = request.app.state.sync_service
    return service


def _admin(request: Request) -> tuple[SyncService, AdminSession]:
    service = _service(request)
    session = request.app.state.admin_sessions.verify(request.cookies.get(SESSION_COOKIE))
    request.app.state.admin_rate_limiter.check(session.subject)
    return service, session


def _render(request: Request, template: str, **context: Any) -> HTMLResponse:
    templates = request.app.state.admin_templates
    body = templates.get_template(template).render(**context)
    return HTMLResponse(body, headers=dict(SECURITY_HEADERS))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> Response:
    """List the workspaces the signed-in administrator can see."""

    service, session = _admin(request)
    async with service.database.begin() as connection:
        rows = (
            await connection.execute(
                select(
                    workspaces.c.id,
                    workspaces.c.name,
                    workspaces.c.raw_audio_enabled,
                    memberships.c.role,
                )
                .select_from(
                    workspaces.join(
                        memberships, memberships.c.workspace_id == workspaces.c.id
                    ).join(user_subjects, user_subjects.c.id == memberships.c.user_id)
                )
                .where(
                    user_subjects.c.subject == session.subject,
                    memberships.c.removed_at.is_(None),
                    workspaces.c.deleted_at.is_(None),
                )
                .order_by(workspaces.c.created_at)
            )
        ).fetchall()
    return _render(
        request,
        "index.html",
        session=session,
        workspaces=[
            {
                "id": str(row.id),
                "name": str(row.name),
                "role": str(row.role),
                "raw_audio_enabled": bool(row.raw_audio_enabled),
            }
            for row in rows
        ],
    )


@router.get("/workspaces/{workspace_id}", response_class=HTMLResponse)
async def workspace_detail(request: Request, workspace_id: str) -> Response:
    """Show members, devices, quota, and content-free audit records."""

    service, session = _admin(request)
    async with service.database.begin() as connection:
        principal = await _principal_for(service, connection, session)
        role = await service.members.require_role(
            connection,
            workspace_id=workspace_id,
            principal=principal,
            minimum=Role.VIEWER,
        )
        workspace = (
            await connection.execute(select(workspaces).where(workspaces.c.id == workspace_id))
        ).fetchone()
        member_rows = (
            await connection.execute(
                select(
                    user_subjects.c.subject,
                    user_subjects.c.issuer,
                    memberships.c.role,
                    memberships.c.removed_at,
                )
                .select_from(
                    memberships.join(user_subjects, user_subjects.c.id == memberships.c.user_id)
                )
                .where(memberships.c.workspace_id == workspace_id)
                .order_by(user_subjects.c.subject)
            )
        ).fetchall()
        device_rows = (
            await connection.execute(
                select(devices.c.id, devices.c.name, devices.c.trust, devices.c.created_at)
                .where(devices.c.workspace_id == workspace_id)
                .order_by(devices.c.created_at)
            )
        ).fetchall()
        usage_row = (
            await connection.execute(
                select(usage_counters).where(usage_counters.c.workspace_id == workspace_id)
            )
        ).fetchone()
        audit_rows = (
            await connection.execute(
                select(audit_events.c.kind, audit_events.c.created_at, audit_events.c.detail)
                .where(audit_events.c.workspace_id == workspace_id)
                .order_by(audit_events.c.created_at.desc())
                .limit(AUDIT_PAGE_SIZE)
            )
        ).fetchall()
    if workspace is None:
        raise AdminSecurityError("The workspace does not exist.")
    return _render(
        request,
        "workspace.html",
        session=session,
        role=role.value,
        may_administer=role.may_administer,
        roles=[entry.value for entry in Role],
        workspace={
            "id": str(workspace.id),
            "name": str(workspace.name),
            "raw_audio_enabled": bool(workspace.raw_audio_enabled),
        },
        members=[
            {
                "subject": str(row.subject),
                "issuer": str(row.issuer),
                "role": str(row.role),
                "removed": row.removed_at is not None,
            }
            for row in member_rows
        ],
        devices=[
            {
                "id": str(row.id),
                "name": str(row.name),
                "trust": str(row.trust),
                "created_at": str(row.created_at),
            }
            for row in device_rows
        ],
        usage={
            "object_count": int(usage_row.object_count) if usage_row else 0,
            "ciphertext_bytes": int(usage_row.ciphertext_bytes) if usage_row else 0,
            "blob_bytes": int(usage_row.blob_bytes) if usage_row else 0,
        },
        audit=[
            {
                "kind": str(row.kind),
                "created_at": str(row.created_at),
                "detail": str(row.detail) if row.detail else "",
            }
            for row in audit_rows
        ],
    )


@router.post("/workspaces/{workspace_id}/members")
async def update_member(
    request: Request,
    workspace_id: str,
    subject: str = Form(...),
    issuer: str = Form(...),
    role: str = Form(...),
    csrf_token: str = Form(alias=CSRF_FIELD),
) -> Response:
    """Change or remove one member's seat."""

    service, session = _admin(request)
    require_csrf(session, csrf_token)
    async with service.database.begin() as connection:
        principal = await _principal_for(service, connection, session)
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
        if role == "remove":
            await service.members.remove_membership(
                connection,
                workspace_id=workspace_id,
                user_id=member.user_id,
            )
            kind = "membership.removed"
        else:
            await service.members.upsert_membership(
                connection,
                workspace_id=workspace_id,
                user_id=member.user_id,
                role=Role(role),
            )
            kind = "membership.updated"
        await service.members.record_audit(
            connection,
            workspace_id=workspace_id,
            kind=kind,
            principal=principal,
        )
    return _redirect(f"/admin/workspaces/{workspace_id}")


@router.post("/workspaces/{workspace_id}/devices/{device_id}/revoke")
async def revoke_device(
    request: Request,
    workspace_id: str,
    device_id: str,
    csrf_token: str = Form(alias=CSRF_FIELD),
) -> Response:
    """Revoke a device and every envelope wrapped for it."""

    service, session = _admin(request)
    require_csrf(session, csrf_token)
    async with service.database.begin() as connection:
        principal = await _principal_for(service, connection, session)
        await service.members.require_role(
            connection,
            workspace_id=workspace_id,
            principal=principal,
            minimum=Role.ADMIN,
        )
        await service.members.revoke_device(
            connection,
            workspace_id=workspace_id,
            device_id=device_id,
        )
        await service.members.record_audit(
            connection,
            workspace_id=workspace_id,
            kind="device.revoked",
            principal=principal,
            device_id=device_id,
        )
    return _redirect(f"/admin/workspaces/{workspace_id}")


@router.post("/workspaces/{workspace_id}/raw-audio")
async def toggle_raw_audio(
    request: Request,
    workspace_id: str,
    enabled: str = Form(default=""),
    csrf_token: str = Form(alias=CSRF_FIELD),
) -> Response:
    """Turn the raw-audio opt-in on or off for one workspace."""

    service, session = _admin(request)
    require_csrf(session, csrf_token)
    async with service.database.begin() as connection:
        principal = await _principal_for(service, connection, session)
    await service.set_raw_audio(
        principal,
        workspace_id=workspace_id,
        enabled=enabled == "on",
    )
    return _redirect(f"/admin/workspaces/{workspace_id}")


async def _principal_for(service: SyncService, connection: Any, session: AdminSession) -> Any:
    from .tables import tenants

    row = (
        await connection.execute(select(tenants.c.id).order_by(tenants.c.created_at).limit(1))
    ).fetchone()
    if row is None:
        raise AdminSecurityError("No tenant exists for this deployment.")
    return await service.members.ensure_user(
        connection,
        tenant_id=str(row.id),
        issuer=session.issuer,
        subject=session.subject,
    )


def _redirect(location: str) -> RedirectResponse:
    return RedirectResponse(location, status_code=303, headers=dict(SECURITY_HEADERS))


__all__ = ["AUDIT_PAGE_SIZE", "router"]
