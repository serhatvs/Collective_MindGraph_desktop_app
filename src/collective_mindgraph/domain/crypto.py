"""End-to-end encryption contracts for workspace content."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .identifiers import DeviceId, EnvelopeId, SyncId, WorkspaceId

PUBLIC_KEY_BYTES = 32
PRIVATE_KEY_BYTES = 32
WORKSPACE_KEY_BYTES = 32
CONTENT_NONCE_BYTES = 12
GCM_TAG_BYTES = 16

_AAD_PREFIX = b"collective-mindgraph/content-aad/v1"


class DeviceTrust(StrEnum):
    """Trust a workspace places in one device."""

    LOCAL = "local"
    PENDING = "pending"
    TRUSTED = "trusted"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class DeviceKey:
    """Public identity of one device inside a workspace."""

    device_id: DeviceId
    workspace_id: WorkspaceId
    name: str
    public_key: bytes
    trust: DeviceTrust
    created_at: datetime
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.device_id, "Device id")
        _require_uuid(self.workspace_id, "Workspace id")
        if not self.name.strip():
            raise ValueError("Device name is required.")
        if len(self.public_key) != PUBLIC_KEY_BYTES:
            raise ValueError(f"Device public key must be {PUBLIC_KEY_BYTES} bytes.")
        _require_aware(self.created_at, "Device creation timestamp")
        if self.revoked_at is not None:
            _require_aware(self.revoked_at, "Device revocation timestamp")
        if (self.trust is DeviceTrust.REVOKED) != (self.revoked_at is not None):
            raise ValueError("Revoked devices must carry exactly one revocation timestamp.")

    @property
    def can_receive_keys(self) -> bool:
        """Whether the workspace key may be wrapped to this device."""

        return self.trust in {DeviceTrust.LOCAL, DeviceTrust.TRUSTED}


@dataclass(frozen=True, slots=True)
class WorkspaceKey:
    """Symmetric content key for one workspace key version."""

    workspace_id: WorkspaceId
    version: int
    material: bytes
    created_at: datetime

    def __post_init__(self) -> None:
        _require_uuid(self.workspace_id, "Workspace id")
        _require_key_version(self.version)
        if len(self.material) != WORKSPACE_KEY_BYTES:
            raise ValueError(f"Workspace key material must be {WORKSPACE_KEY_BYTES} bytes.")
        _require_aware(self.created_at, "Workspace key timestamp")

    def __repr__(self) -> str:
        return (
            f"WorkspaceKey(workspace_id={self.workspace_id!r}, "
            f"version={self.version}, material=<redacted>)"
        )


@dataclass(frozen=True, slots=True)
class ContentBinding:
    """Associated data that binds ciphertext to one entity revision."""

    workspace_id: WorkspaceId
    object_type: str
    object_id: SyncId
    revision: int
    key_version: int

    def __post_init__(self) -> None:
        _require_uuid(self.workspace_id, "Workspace id")
        _require_uuid(self.object_id, "Object id")
        if not self.object_type.strip():
            raise ValueError("Object type is required.")
        if self.revision < 1:
            raise ValueError("Bound revision must be at least one.")
        _require_key_version(self.key_version)

    def associated_data(self) -> bytes:
        """Return unambiguous authenticated associated data.

        Every field is length prefixed so that no two distinct bindings can
        produce the same byte string.
        """

        fields = (
            str(self.workspace_id).encode("utf-8"),
            self.object_type.encode("utf-8"),
            str(self.object_id).encode("utf-8"),
            str(self.revision).encode("ascii"),
            str(self.key_version).encode("ascii"),
        )
        parts = [_AAD_PREFIX]
        for field_value in fields:
            parts.append(len(field_value).to_bytes(4, "big"))
            parts.append(field_value)
        return b"".join(parts)


@dataclass(frozen=True, slots=True)
class EncryptedObject:
    """Ciphertext for one entity revision plus its binding metadata."""

    binding: ContentBinding
    nonce: bytes
    ciphertext: bytes

    def __post_init__(self) -> None:
        if len(self.nonce) != CONTENT_NONCE_BYTES:
            raise ValueError(f"Content nonce must be {CONTENT_NONCE_BYTES} bytes.")
        if len(self.ciphertext) <= GCM_TAG_BYTES:
            raise ValueError("Ciphertext must contain an authentication tag.")


@dataclass(frozen=True, slots=True)
class KeyEnvelope:
    """One workspace key version wrapped for a single recipient."""

    id: EnvelopeId
    workspace_id: WorkspaceId
    key_version: int
    wrapped_key: bytes
    created_at: datetime
    recipient_device_id: DeviceId | None = None
    ephemeral_public_key: bytes | None = None
    salt: bytes | None = None
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.id, "Envelope id")
        _require_uuid(self.workspace_id, "Workspace id")
        _require_key_version(self.key_version)
        if not self.wrapped_key:
            raise ValueError("Key envelope must contain wrapped key material.")
        _require_aware(self.created_at, "Envelope timestamp")
        if self.revoked_at is not None:
            _require_aware(self.revoked_at, "Envelope revocation timestamp")
        if self.recipient_device_id is None:
            if self.salt is None:
                raise ValueError("Recovery envelopes must carry a derivation salt.")
        else:
            _require_uuid(self.recipient_device_id, "Recipient device id")
            if self.ephemeral_public_key is None:
                raise ValueError("Device envelopes must carry an ephemeral public key.")
            if len(self.ephemeral_public_key) != PUBLIC_KEY_BYTES:
                raise ValueError(f"Ephemeral public key must be {PUBLIC_KEY_BYTES} bytes.")

    @property
    def is_recovery(self) -> bool:
        """Whether this envelope is unlocked by a recovery code."""

        return self.recipient_device_id is None

    @property
    def is_active(self) -> bool:
        """Whether this envelope may still be used to unlock a workspace."""

        return self.revoked_at is None


@dataclass(frozen=True, slots=True)
class RecoveryBundle:
    """A recovery envelope paired with the code shown to the user once."""

    envelope: KeyEnvelope
    recovery_code: str

    def __post_init__(self) -> None:
        if not self.envelope.is_recovery:
            raise ValueError("Recovery bundles require a recovery envelope.")
        if not self.recovery_code.strip():
            raise ValueError("Recovery code is required.")

    def __repr__(self) -> str:
        return f"RecoveryBundle(workspace_id={self.envelope.workspace_id!r}, code=<redacted>)"


def _require_uuid(value: object, label: str) -> None:
    try:
        UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"{label} must be a UUID.") from error


def _require_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware.")


def _require_key_version(version: int) -> None:
    if version < 1:
        raise ValueError("Key version must be at least one.")
