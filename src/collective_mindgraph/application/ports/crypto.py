"""Ports for device secrets, key wrapping, and envelope persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from collective_mindgraph.domain import (
    ContentBinding,
    DeviceKey,
    EncryptedObject,
    KeyEnvelope,
    WorkspaceKey,
)
from collective_mindgraph.domain.identifiers import DeviceId, WorkspaceId


class DeviceSecretStore(Protocol):
    """Operating-system protected storage for this device's private material."""

    def store(self, name: str, secret: bytes) -> None: ...

    def load(self, name: str) -> bytes | None: ...

    def delete(self, name: str) -> None: ...


class ContentCipher(Protocol):
    """Authenticated encryption for one entity revision."""

    def encrypt(
        self,
        key: WorkspaceKey,
        binding: ContentBinding,
        plaintext: bytes,
    ) -> EncryptedObject: ...

    def decrypt(self, key: WorkspaceKey, encrypted: EncryptedObject) -> bytes: ...


class KeyWrapper(Protocol):
    """Wrapping and unwrapping of workspace keys for recipients."""

    def wrap_for_device(
        self,
        key: WorkspaceKey,
        device: DeviceKey,
    ) -> KeyEnvelope: ...

    def unwrap_for_device(
        self,
        envelope: KeyEnvelope,
        device_private_key: bytes,
    ) -> WorkspaceKey: ...

    def wrap_for_recovery(
        self,
        key: WorkspaceKey,
        recovery_code: str,
    ) -> KeyEnvelope: ...

    def unwrap_for_recovery(
        self,
        envelope: KeyEnvelope,
        recovery_code: str,
    ) -> WorkspaceKey: ...


class DeviceKeyFactory(Protocol):
    """Generation of this device's asymmetric identity."""

    def generate_private_key(self) -> bytes: ...

    def public_key(self, private_key: bytes) -> bytes: ...


class RecoveryCodeFactory(Protocol):
    """Generation and normalization of user-visible recovery codes."""

    def generate(self) -> str: ...

    def normalize(self, code: str) -> str: ...


class KeyEnvelopeStore(Protocol):
    """Persistence for device identities and wrapped workspace keys."""

    def register_device(self, device: DeviceKey) -> None: ...

    def get_device(self, device_id: DeviceId) -> DeviceKey | None: ...

    def current_device_id(self) -> DeviceId | None: ...

    def list_devices(self, workspace_id: WorkspaceId) -> tuple[DeviceKey, ...]: ...

    def revoke_device(self, device_id: DeviceId, revoked_at: datetime) -> None: ...

    def save_envelope(self, envelope: KeyEnvelope) -> None: ...

    def latest_key_version(self, workspace_id: WorkspaceId) -> int: ...

    def active_envelope_for_device(
        self,
        workspace_id: WorkspaceId,
        device_id: DeviceId,
        key_version: int | None = None,
    ) -> KeyEnvelope | None: ...

    def active_recovery_envelope(
        self,
        workspace_id: WorkspaceId,
        key_version: int | None = None,
    ) -> KeyEnvelope | None: ...

    def revoke_envelopes_for_device(
        self,
        workspace_id: WorkspaceId,
        device_id: DeviceId,
        revoked_at: datetime,
    ) -> int: ...


__all__ = [
    "ContentCipher",
    "DeviceKeyFactory",
    "DeviceSecretStore",
    "KeyEnvelopeStore",
    "KeyWrapper",
    "RecoveryCodeFactory",
]
