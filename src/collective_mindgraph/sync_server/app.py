"""FastAPI composition root for the synchronization service."""

from __future__ import annotations

import logging
import os
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from collective_mindgraph import __version__

from .admin_auth import AdminLoginFlow
from .admin_login_views import router as admin_login_router
from .admin_security import FixedWindowRateLimiter, SessionCodec
from .admin_views import router as admin_router
from .blob_storage import BlobStore
from .database import SyncDatabase
from .http_support import install_error_handlers
from .oidc import OidcPrincipalResolver, OidcSettings, oidc_settings_from_environment
from .principals import BootstrapTokenResolver, PrincipalResolver
from .routes_blobs import router as blob_router
from .routes_sync import router as sync_router
from .routes_workspaces import router as workspace_router
from .service import SyncService
from .settings import SyncServerSettings, get_sync_server_settings

LOGGER = logging.getLogger(__name__)

ADMIN_RATE_LIMIT = 120
ADMIN_RATE_WINDOW_SECONDS = 60.0
TEMPLATE_DIRECTORY = Path(__file__).resolve().parent / "admin_templates"


def create_sync_app(
    settings: SyncServerSettings | None = None,
    *,
    identities: PrincipalResolver | None = None,
    oidc: OidcSettings | None = None,
    blob_store: BlobStore | None = None,
    session_secret: bytes | None = None,
    create_schema: bool = False,
) -> FastAPI:
    """Build the service; resources are installed on startup, not on import."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved = settings or get_sync_server_settings()
        database = SyncDatabase(resolved)
        if create_schema:
            await database.create_schema()
        provider = oidc or oidc_settings_from_environment()
        resolver = identities or _resolver(provider)
        app.state.sync_service = SyncService(
            settings=resolved,
            database=database,
            identities=resolver,
            blob_store=blob_store,
        )
        app.state.settings = resolved
        _install_admin(app, provider, resolver, session_secret)
        LOGGER.info(
            "Collective MindGraph sync service %s started with %s identity.",
            __version__,
            "OIDC" if provider is not None else "bootstrap",
        )
        try:
            yield
        finally:
            await database.dispose()

    app = FastAPI(
        title="Collective MindGraph Sync",
        version=__version__,
        lifespan=lifespan,
        description=(
            "Stores sealed bytes and bounded routing metadata. The service holds "
            "no workspace keys and cannot decrypt anything it stores."
        ),
    )
    install_error_handlers(app)
    app.include_router(sync_router)
    app.include_router(workspace_router)
    app.include_router(blob_router)
    app.include_router(admin_login_router)
    app.include_router(admin_router)
    return app


def _resolver(provider: OidcSettings | None) -> PrincipalResolver:
    if provider is not None:
        return OidcPrincipalResolver(provider)
    LOGGER.warning(
        "OIDC is not configured; falling back to bootstrap tokens. "
        "Configure CMG_SYNC_OIDC_* before any public deployment."
    )
    return BootstrapTokenResolver.from_environment()


def _install_admin(
    app: FastAPI,
    provider: OidcSettings | None,
    resolver: PrincipalResolver,
    session_secret: bytes | None,
) -> None:
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    app.state.admin_templates = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIRECTORY)),
        autoescape=select_autoescape(("html",)),
        auto_reload=False,
    )
    app.state.admin_sessions = SessionCodec(session_secret or _session_secret())
    app.state.admin_rate_limiter = FixedWindowRateLimiter(
        limit=ADMIN_RATE_LIMIT,
        window_seconds=ADMIN_RATE_WINDOW_SECONDS,
    )
    app.state.admin_identities = resolver
    app.state.admin_login_flow = (
        AdminLoginFlow(provider, app.state.admin_sessions) if provider is not None else None
    )


def _session_secret() -> bytes:
    configured = os.environ.get("CMG_SYNC_ADMIN_SESSION_SECRET", "").strip()
    if configured:
        return configured.encode("utf-8")
    LOGGER.warning(
        "CMG_SYNC_ADMIN_SESSION_SECRET is unset; admin sessions will not survive a "
        "restart and cannot be shared across replicas."
    )
    return secrets.token_bytes(32)


__all__ = ["ADMIN_RATE_LIMIT", "create_sync_app"]
