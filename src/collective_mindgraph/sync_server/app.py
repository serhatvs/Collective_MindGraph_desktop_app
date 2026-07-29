"""FastAPI composition root for the synchronization service."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from collective_mindgraph import __version__

from .blob_storage import BlobStore
from .database import SyncDatabase
from .http_support import install_error_handlers
from .principals import BootstrapTokenResolver, PrincipalResolver
from .routes_blobs import router as blob_router
from .routes_sync import router as sync_router
from .routes_workspaces import router as workspace_router
from .service import SyncService
from .settings import SyncServerSettings, get_sync_server_settings

LOGGER = logging.getLogger(__name__)


def create_sync_app(
    settings: SyncServerSettings | None = None,
    *,
    identities: PrincipalResolver | None = None,
    blob_store: BlobStore | None = None,
    create_schema: bool = False,
) -> FastAPI:
    """Build the service; resources are installed on startup, not on import."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved = settings or get_sync_server_settings()
        database = SyncDatabase(resolved)
        if create_schema:
            await database.create_schema()
        app.state.sync_service = SyncService(
            settings=resolved,
            database=database,
            identities=identities or BootstrapTokenResolver.from_environment(),
            blob_store=blob_store,
        )
        app.state.settings = resolved
        LOGGER.info("Collective MindGraph sync service %s started.", __version__)
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
    return app


__all__ = ["create_sync_app"]
