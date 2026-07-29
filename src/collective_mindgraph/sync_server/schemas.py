"""Request and response bodies for the `/sync/v1` surface."""

from __future__ import annotations

from base64 import b64decode, b64encode
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from .contracts import (
    BlobRejectedError,
    OperationResult,
    PullPage,
    PushResult,
    Role,
    SyncObjectRecord,
    SyncOperationInput,
)


class OperationRequest(BaseModel):
    """One opaque change, with sealed bytes carried as base64."""

    operation_id: str
    object_id: str
    object_type: str = Field(min_length=1, max_length=60)
    base_revision: int = Field(ge=0)
    key_version: int = Field(ge=1)
    client_timestamp: datetime
    ciphertext: str | None = None
    nonce: str | None = None
    deleted: bool = False

    @field_validator("ciphertext", "nonce")
    @classmethod
    def _validate_base64(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            b64decode(value, validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError("Sealed fields must be base64.") from error
        return value

    def to_input(self) -> SyncOperationInput:
        return SyncOperationInput(
            operation_id=self.operation_id,
            object_id=self.object_id,
            object_type=self.object_type,
            base_revision=self.base_revision,
            key_version=self.key_version,
            client_timestamp=self.client_timestamp,
            ciphertext=_decode(self.ciphertext),
            nonce=_decode(self.nonce),
            deleted=self.deleted,
        )


class PushRequest(BaseModel):
    device_id: str
    operations: list[OperationRequest] = Field(min_length=1)


class OperationResultResponse(BaseModel):
    operation_id: str
    object_id: str
    outcome: str
    revision: int | None = None
    server_revision: int | None = None

    @classmethod
    def of(cls, result: OperationResult) -> OperationResultResponse:
        return cls(
            operation_id=result.operation_id,
            object_id=result.object_id,
            outcome=result.outcome.value,
            revision=result.revision,
            server_revision=result.server_revision,
        )


class PushResponse(BaseModel):
    cursor: str
    results: list[OperationResultResponse]

    @classmethod
    def of(cls, result: PushResult) -> PushResponse:
        return cls(
            cursor=result.cursor,
            results=[OperationResultResponse.of(entry) for entry in result.results],
        )


class SyncObjectResponse(BaseModel):
    object_id: str
    object_type: str
    revision: int
    key_version: int
    deleted: bool
    client_timestamp: datetime
    server_timestamp: datetime
    ciphertext: str | None = None
    nonce: str | None = None
    ciphertext_sha256: str | None = None
    updated_by_device: str | None = None

    @classmethod
    def of(cls, record: SyncObjectRecord) -> SyncObjectResponse:
        return cls(
            object_id=record.object_id,
            object_type=record.object_type,
            revision=record.revision,
            key_version=record.key_version,
            deleted=record.deleted,
            client_timestamp=record.client_timestamp,
            server_timestamp=record.server_timestamp,
            ciphertext=_encode(record.ciphertext),
            nonce=_encode(record.nonce),
            ciphertext_sha256=record.ciphertext_sha256,
            updated_by_device=record.updated_by_device,
        )


class PullResponse(BaseModel):
    cursor: str
    has_more: bool
    records: list[SyncObjectResponse]

    @classmethod
    def of(cls, page: PullPage) -> PullResponse:
        return cls(
            cursor=page.cursor,
            has_more=page.has_more,
            records=[SyncObjectResponse.of(record) for record in page.records],
        )


class WorkspaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    workspace_id: str | None = None


class WorkspaceResponse(BaseModel):
    workspace_id: str
    name: str
    role: str
    raw_audio_enabled: bool


class MembershipRequest(BaseModel):
    subject: str = Field(min_length=1)
    issuer: str = Field(min_length=1)
    role: Role


class DeviceRequest(BaseModel):
    device_id: str
    name: str = Field(min_length=1, max_length=200)
    public_key: str

    def public_key_bytes(self) -> bytes:
        decoded = _decode(self.public_key)
        if decoded is None or len(decoded) != 32:
            raise ValueError("Device public keys must be 32 base64-encoded bytes.")
        return decoded


class EnvelopeRequest(BaseModel):
    key_version: int = Field(ge=1)
    wrapped_key: str
    recipient_device_id: str | None = None
    ephemeral_public_key: str | None = None
    salt: str | None = None


class EnvelopeResponse(BaseModel):
    id: str
    key_version: int
    wrapped_key: str
    recipient_device_id: str | None = None
    ephemeral_public_key: str | None = None
    salt: str | None = None


class BlobInitiateRequest(BaseModel):
    object_id: str
    total_chunks: int = Field(ge=1)
    sha256: str = Field(min_length=64, max_length=64)


class BlobManifestResponse(BaseModel):
    manifest_id: str
    object_id: str
    chunk_bytes: int
    total_chunks: int
    state: str
    missing_chunks: list[int]


class UsageResponse(BaseModel):
    workspace_id: str
    object_count: int
    ciphertext_bytes: int
    blob_bytes: int


def _decode(value: str | None) -> bytes | None:
    if value is None:
        return None
    try:
        return b64decode(value, validate=True)
    except (ValueError, TypeError) as error:
        raise BlobRejectedError("Sealed fields must be base64.") from error


def _encode(value: bytes | None) -> str | None:
    return b64encode(value).decode("ascii") if value is not None else None


__all__ = [
    "BlobInitiateRequest",
    "BlobManifestResponse",
    "DeviceRequest",
    "EnvelopeRequest",
    "EnvelopeResponse",
    "MembershipRequest",
    "OperationRequest",
    "PullResponse",
    "PushRequest",
    "PushResponse",
    "SyncObjectResponse",
    "UsageResponse",
    "WorkspaceRequest",
    "WorkspaceResponse",
]
