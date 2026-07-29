"""Lazy FastAPI composition root for the local engine."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from collective_mindgraph import __version__
from collective_mindgraph.application import ProviderUnavailableError
from collective_mindgraph.engine.logging import configure_logging

from .api.routes import router as compatibility_router
from .api.v1 import router as product_router
from .api.v2 import router as sync_router
from .api.ws import router as compatibility_websocket_router
from .context import build_engine_context
from .settings import EngineSettings, get_engine_settings

LOGGER = logging.getLogger(__name__)


def create_app(settings: EngineSettings | None = None) -> FastAPI:
    """Create a lightweight app; runtime resources are installed on startup."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved_settings = settings or get_engine_settings()
        configure_logging(resolved_settings.log_level)
        context = build_engine_context(resolved_settings)
        recovered_jobs = context.recording_jobs.recover_interrupted()
        app.state.engine_context = context
        app.state.settings = resolved_settings
        LOGGER.info("Collective MindGraph engine %s started.", __version__)
        if recovered_jobs:
            LOGGER.warning(
                "Marked %s interrupted processing job(s) as retryable failures.",
                recovered_jobs,
            )
        try:
            yield
        finally:
            await context.recording_jobs.shutdown()
            LOGGER.info("Collective MindGraph engine stopped.")

    application = FastAPI(
        title="Collective MindGraph Engine",
        version=__version__,
        lifespan=lifespan,
    )
    application.include_router(product_router)
    application.include_router(sync_router)
    application.include_router(compatibility_router)
    application.include_router(compatibility_websocket_router)

    @application.exception_handler(ValueError)
    async def value_error_handler(request: Request, error: ValueError) -> JSONResponse:
        if request.url.path.startswith("/api/v1/"):
            return JSONResponse(
                status_code=422,
                content={
                    "code": "invalid_request",
                    "message": str(error),
                    "details": {},
                    "retryable": False,
                },
            )
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @application.exception_handler(HTTPException)
    async def typed_http_error(request: Request, error: HTTPException):
        if not request.url.path.startswith("/api/v1/"):
            return await http_exception_handler(request, error)
        message = str(error.detail)
        return JSONResponse(
            status_code=error.status_code,
            content={
                "code": _error_code(error.status_code),
                "message": message,
                "details": {},
                "retryable": error.status_code >= 500,
            },
            headers=error.headers,
        )

    @application.exception_handler(RequestValidationError)
    async def typed_validation_error(
        request: Request,
        error: RequestValidationError,
    ):
        if not request.url.path.startswith("/api/v1/"):
            return await request_validation_exception_handler(request, error)
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "message": "The request could not be validated.",
                "details": {"errors": jsonable_encoder(error.errors())},
                "retryable": False,
            },
        )

    @application.exception_handler(ProviderUnavailableError)
    async def provider_unavailable_handler(
        request: Request,
        error: ProviderUnavailableError,
    ) -> JSONResponse:
        if not request.url.path.startswith("/api/v1/"):
            return JSONResponse(status_code=503, content={"detail": str(error)})
        return JSONResponse(
            status_code=503,
            content={
                "code": "provider_unavailable",
                "message": str(error),
                "details": {},
                "retryable": True,
            },
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request,
        error: Exception,
    ) -> JSONResponse:
        LOGGER.exception("Unhandled engine request failure.", exc_info=error)
        if not request.url.path.startswith("/api/v1/"):
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error"},
            )
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "The local engine could not complete the request.",
                "details": {},
                "retryable": True,
            },
        )

    return application


# Importing this module remains side-effect free. FastAPI runs the lifespan only
# when an ASGI server or TestClient actually starts the application.
app = create_app()


def _error_code(status_code: int) -> str:
    return {
        404: "not_found",
        409: "conflict",
        413: "payload_too_large",
        422: "invalid_request",
        503: "engine_unavailable",
    }.get(status_code, "request_failed")
