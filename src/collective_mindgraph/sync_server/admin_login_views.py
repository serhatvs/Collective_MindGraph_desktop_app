"""Sign-in, callback, and sign-out routes for the admin surface."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import RedirectResponse

from .admin_auth import FLOW_COOKIE, FLOW_TTL_SECONDS, AdminLoginFlow
from .admin_security import (
    CSRF_FIELD,
    SECURITY_HEADERS,
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    require_csrf,
)
from .principals import IdentityError

router = APIRouter(prefix="/admin", tags=["admin"])


def _flow(request: Request) -> AdminLoginFlow:
    flow: AdminLoginFlow | None = getattr(request.app.state, "admin_login_flow", None)
    if flow is None:
        raise IdentityError("The admin surface requires OIDC to be configured.")
    return flow


@router.get("/login")
async def login(request: Request) -> Response:
    """Send the browser to the provider with a proof key and state."""

    request.app.state.admin_rate_limiter.check(_client_key(request))
    redirect_uri = str(request.url_for("callback"))
    url, cookie = _flow(request).start(redirect_uri)
    response = RedirectResponse(url, status_code=303, headers=dict(SECURITY_HEADERS))
    _set_cookie(request, response, FLOW_COOKIE, cookie, FLOW_TTL_SECONDS)
    return response


@router.get("/callback", name="callback")
async def callback(request: Request) -> Response:
    """Validate the provider response and open an admin session."""

    request.app.state.admin_rate_limiter.check(_client_key(request))
    token = _flow(request).finish(
        request.cookies.get(FLOW_COOKIE),
        dict(request.query_params),
    )
    identity = request.app.state.admin_identities.resolve(f"Bearer {token}")
    cookie, _ = request.app.state.admin_sessions.issue(
        subject=identity.subject,
        issuer=identity.issuer,
    )
    response = RedirectResponse("/admin/", status_code=303, headers=dict(SECURITY_HEADERS))
    _set_cookie(request, response, SESSION_COOKIE, cookie, SESSION_TTL_SECONDS)
    response.delete_cookie(FLOW_COOKIE, path="/")
    return response


@router.post("/logout")
async def logout(request: Request, csrf_token: str = Form(alias=CSRF_FIELD)) -> Response:
    """End the admin session."""

    session = request.app.state.admin_sessions.verify(request.cookies.get(SESSION_COOKIE))
    require_csrf(session, csrf_token)
    response = RedirectResponse("/admin/login", status_code=303, headers=dict(SECURITY_HEADERS))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


def _set_cookie(
    request: Request,
    response: Response,
    name: str,
    value: str,
    max_age: int,
) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


__all__ = ["router"]
