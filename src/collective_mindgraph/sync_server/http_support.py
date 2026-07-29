"""Shared request helpers and error mapping for the `/sync/v1` surface."""

from __future__ import annotations

from base64 import b64decode, b64encode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .blob_repository import BlobManifest
from .contracts import (
    AccessDeniedError,
    BlobRejectedError,
    Principal,
    PushLimitExceededError,
    WorkspaceNotFoundError,
)
from .principals import IdentityError
from .schemas import BlobManifestResponse
from .service import SyncService


def service_of(request: Request) -> SyncService:
    """Return the service installed on the running application."""

    service: SyncService = request.app.state.sync_service
    return service


async def principal_of(request: Request, authorization: str | None) -> Principal:
    """Authenticate the caller or fail with a 401."""

    try:
        return await service_of(request).principal(authorization)
    except IdentityError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


def install_error_handlers(app: FastAPI) -> None:
    """Map service errors onto stable, detail-free status codes."""

    @app.exception_handler(AccessDeniedError)
    async def _denied(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(error)})

    @app.exception_handler(WorkspaceNotFoundError)
    async def _missing(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(PushLimitExceededError)
    async def _too_large(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=413, content={"detail": str(error)})

    @app.exception_handler(BlobRejectedError)
    async def _rejected(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(IdentityError)
    async def _unauthenticated(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(error)})


def manifest_response(manifest: BlobManifest) -> BlobManifestResponse:
    """Describe upload progress so a client can resume precisely."""

    return BlobManifestResponse(
        manifest_id=manifest.id,
        object_id=manifest.object_id,
        chunk_bytes=manifest.chunk_bytes,
        total_chunks=manifest.total_chunks,
        state=manifest.state,
        missing_chunks=list(manifest.missing_chunks),
    )


def required_bytes(value: str, label: str) -> bytes:
    decoded = optional_bytes(value)
    if not decoded:
        raise HTTPException(status_code=422, detail=f"The {label} is required.")
    return decoded


def optional_bytes(value: str | None) -> bytes | None:
    if value is None:
        return None
    try:
        return b64decode(value, validate=True)
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail="Sealed fields must be base64.") from error


def encode_bytes(value: bytes) -> str:
    return b64encode(value).decode("ascii")


__all__ = [
    "encode_bytes",
    "install_error_handlers",
    "manifest_response",
    "optional_bytes",
    "principal_of",
    "required_bytes",
    "service_of",
]
