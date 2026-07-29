"""Resumable encrypted-blob upload and download endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request, Response

from .http_support import manifest_response, principal_of, service_of
from .schemas import BlobInitiateRequest, BlobManifestResponse

router = APIRouter(prefix="/sync/v1", tags=["blobs"])


@router.post("/workspaces/{workspace_id}/blobs", response_model=BlobManifestResponse)
async def initiate_blob(
    request: Request,
    workspace_id: str,
    payload: BlobInitiateRequest,
    authorization: str | None = Header(default=None),
) -> BlobManifestResponse:
    """Open or resume an upload; rejected unless raw audio is enabled."""

    principal = await principal_of(request, authorization)
    manifest = await service_of(request).blobs.initiate(
        principal,
        workspace_id=workspace_id,
        object_id=payload.object_id,
        total_chunks=payload.total_chunks,
        sha256=payload.sha256,
    )
    return manifest_response(manifest)


@router.put(
    "/workspaces/{workspace_id}/blobs/{manifest_id}/chunks/{chunk_index}",
    response_model=BlobManifestResponse,
)
async def upload_blob_chunk(
    request: Request,
    workspace_id: str,
    manifest_id: str,
    chunk_index: int,
    authorization: str | None = Header(default=None),
) -> BlobManifestResponse:
    """Accept one independently sealed chunk and record its digest."""

    principal = await principal_of(request, authorization)
    manifest = await service_of(request).blobs.upload_chunk(
        principal,
        workspace_id=workspace_id,
        manifest_id=manifest_id,
        chunk_index=chunk_index,
        payload=await request.body(),
    )
    return manifest_response(manifest)


@router.post(
    "/workspaces/{workspace_id}/blobs/{manifest_id}/complete",
    response_model=BlobManifestResponse,
)
async def complete_blob(
    request: Request,
    workspace_id: str,
    manifest_id: str,
    authorization: str | None = Header(default=None),
) -> BlobManifestResponse:
    """Verify the reassembled ciphertext digest before accepting the blob."""

    principal = await principal_of(request, authorization)
    manifest = await service_of(request).blobs.complete(
        principal,
        workspace_id=workspace_id,
        manifest_id=manifest_id,
    )
    return manifest_response(manifest)


@router.get("/workspaces/{workspace_id}/blobs/{manifest_id}")
async def download_blob(
    request: Request,
    workspace_id: str,
    manifest_id: str,
    authorization: str | None = Header(default=None),
) -> Response:
    """Return the sealed bytes exactly as they were uploaded."""

    principal = await principal_of(request, authorization)
    payload = await service_of(request).blobs.read(
        principal,
        workspace_id=workspace_id,
        manifest_id=manifest_id,
    )
    return Response(content=payload, media_type="application/octet-stream")


__all__ = ["router"]
