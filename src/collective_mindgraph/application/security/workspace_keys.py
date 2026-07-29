"""Workspace key initialization, unlock, enrollment, recovery, and rotation."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from collective_mindgraph.application.ports.crypto import (
    ContentCipher,
    DeviceKeyFactory,
    DeviceSecretStore,
    KeyEnvelopeStore,
    KeyWrapper,
    RecoveryCodeFactory,
)
from collective_mindgraph.domain import (
    WORKSPACE_KEY_BYTES,
    ContentBinding,
    DeviceKey,
    DeviceTrust,
    EncryptedObject,
    KeyEnvelope,
    RecoveryBundle,
    WorkspaceKey,
)
from collective_mindgraph.domain.identifiers import DeviceId, SyncId, WorkspaceId

DEVICE_SECRET_PREFIX = "device-private-key"


class KeyManagementError(RuntimeError):
    """Base error for workspace key lifecycle failures."""


class WorkspaceLockedError(KeyManagementError):
    """Raised when this device holds no usable envelope for a workspace."""


class DeviceRevokedError(KeyManagementError):
    """Raised when a revoked device attempts a key operation."""


@dataclass(frozen=True, slots=True)
class DeviceEnrollmentRequest:
    """A device asking an authorized device to share the workspace key."""

    device_id: DeviceId
    workspace_id: WorkspaceId
    name: str
    public_key: bytes


class WorkspaceKeyService:
    """Owns every transition of workspace key material on this device."""

    def __init__(
        self,
        *,
        envelopes: KeyEnvelopeStore,
        device_secrets: DeviceSecretStore,
        wrapper: KeyWrapper,
        cipher: ContentCipher,
        device_keys: DeviceKeyFactory,
        recovery_codes: RecoveryCodeFactory,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._envelopes = envelopes
        self._device_secrets = device_secrets
        self._wrapper = wrapper
        self._cipher = cipher
        self._device_keys = device_keys
        self._recovery_codes = recovery_codes
        self._clock = clock or (lambda: datetime.now(tz=UTC))
        self._unlocked: dict[tuple[str, int], WorkspaceKey] = {}

    # Device identity -----------------------------------------------------

    def ensure_device_identity(self, workspace_id: WorkspaceId, name: str) -> DeviceKey:
        """Return this device's key, generating and protecting one if absent."""

        device_id = self._require_current_device_id()
        existing = self._envelopes.get_device(device_id)
        if existing is not None and existing.trust is DeviceTrust.REVOKED:
            raise DeviceRevokedError("This device has been revoked from the workspace.")
        private_key = self._device_secrets.load(_secret_name(device_id))
        if existing is not None and private_key is not None:
            return existing
        private_key = private_key or self._device_keys.generate_private_key()
        self._device_secrets.store(_secret_name(device_id), private_key)
        device = DeviceKey(
            device_id=device_id,
            workspace_id=workspace_id,
            name=(existing.name if existing is not None else name),
            public_key=self._device_keys.public_key(private_key),
            trust=(existing.trust if existing is not None else DeviceTrust.LOCAL),
            created_at=(existing.created_at if existing is not None else self._clock()),
        )
        self._envelopes.register_device(device)
        return device

    # Workspace lifecycle -------------------------------------------------

    def initialize_workspace(self, workspace_id: WorkspaceId, device_name: str) -> RecoveryBundle:
        """Create key version one and return the single-use recovery bundle."""

        device = self.ensure_device_identity(workspace_id, device_name)
        if self._envelopes.latest_key_version(workspace_id) >= 1:
            raise KeyManagementError("Workspace key material already exists.")
        key = self._new_key(workspace_id, version=1)
        self._envelopes.save_envelope(self._wrapper.wrap_for_device(key, device))
        return self._store_recovery_bundle(key)

    def unlock(self, workspace_id: WorkspaceId) -> WorkspaceKey:
        """Decrypt and cache the current workspace key for this device."""

        version = self._require_key_version(workspace_id)
        return self.unlock_version(workspace_id, version)

    def unlock_version(self, workspace_id: WorkspaceId, key_version: int) -> WorkspaceKey:
        """Decrypt and cache one specific workspace key version."""

        cached = self._unlocked.get((str(workspace_id), key_version))
        if cached is not None:
            return cached
        device_id = self._require_current_device_id()
        device = self._envelopes.get_device(device_id)
        if device is not None and device.trust is DeviceTrust.REVOKED:
            raise DeviceRevokedError("This device has been revoked from the workspace.")
        envelope = self._envelopes.active_envelope_for_device(workspace_id, device_id, key_version)
        if envelope is None:
            raise WorkspaceLockedError(
                "This device holds no active key envelope for the workspace."
            )
        private_key = self._device_secrets.load(_secret_name(device_id))
        if private_key is None:
            raise WorkspaceLockedError("This device's private key is unavailable.")
        return self._cache(self._wrapper.unwrap_for_device(envelope, private_key))

    def unlock_with_recovery_code(
        self,
        workspace_id: WorkspaceId,
        recovery_code: str,
        *,
        device_name: str = "Recovered Device",
    ) -> WorkspaceKey:
        """Recover the workspace key and re-wrap it for this device."""

        version = self._require_key_version(workspace_id)
        envelope = self._envelopes.active_recovery_envelope(workspace_id, version)
        if envelope is None:
            raise WorkspaceLockedError("No active recovery envelope exists for the workspace.")
        key = self._wrapper.unwrap_for_recovery(
            envelope,
            self._recovery_codes.normalize(recovery_code),
        )
        device = self.ensure_device_identity(workspace_id, device_name)
        self._envelopes.save_envelope(self._wrapper.wrap_for_device(key, device))
        return self._cache(key)

    def lock(self, workspace_id: WorkspaceId | None = None) -> None:
        """Drop cached plaintext key material."""

        if workspace_id is None:
            self._unlocked.clear()
            return
        for cached_key in [key for key in self._unlocked if key[0] == str(workspace_id)]:
            del self._unlocked[cached_key]

    # Membership ----------------------------------------------------------

    def approve_device(self, request: DeviceEnrollmentRequest) -> KeyEnvelope:
        """Share the current workspace key with an approved pending device."""

        key = self.unlock(request.workspace_id)
        existing = self._envelopes.get_device(request.device_id)
        if existing is not None and existing.trust is DeviceTrust.REVOKED:
            raise DeviceRevokedError("A revoked device cannot be re-approved without rotation.")
        device = DeviceKey(
            device_id=request.device_id,
            workspace_id=request.workspace_id,
            name=request.name,
            public_key=request.public_key,
            trust=DeviceTrust.TRUSTED,
            created_at=(existing.created_at if existing is not None else self._clock()),
        )
        self._envelopes.register_device(device)
        envelope = self._wrapper.wrap_for_device(key, device)
        self._envelopes.save_envelope(envelope)
        return envelope

    def revoke_device(self, workspace_id: WorkspaceId, device_id: DeviceId) -> RecoveryBundle:
        """Revoke a device, invalidate its envelopes, and rotate the key.

        Rotation protects future content only. Content the revoked device
        already decrypted cannot be recalled.
        """

        if device_id == self._envelopes.current_device_id():
            raise KeyManagementError("A device cannot revoke itself.")
        key = self.unlock(workspace_id)
        revoked_at = self._clock()
        self._envelopes.revoke_device(device_id, revoked_at)
        self._envelopes.revoke_envelopes_for_device(workspace_id, device_id, revoked_at)
        return self.rotate(workspace_id, previous=key)

    def rotate(
        self,
        workspace_id: WorkspaceId,
        *,
        previous: WorkspaceKey | None = None,
    ) -> RecoveryBundle:
        """Issue the next key version for every device that may still receive it."""

        if previous is None:
            self.unlock(workspace_id)
        version = self._require_key_version(workspace_id) + 1
        key = self._new_key(workspace_id, version=version)
        recipients = [
            device
            for device in self._envelopes.list_devices(workspace_id)
            if device.can_receive_keys
        ]
        if not recipients:
            raise KeyManagementError("Rotation requires at least one non-revoked device.")
        for device in recipients:
            self._envelopes.save_envelope(self._wrapper.wrap_for_device(key, device))
        return self._store_recovery_bundle(key)

    # Content -------------------------------------------------------------

    def encrypt(
        self,
        workspace_id: WorkspaceId,
        *,
        object_type: str,
        object_id: SyncId,
        revision: int,
        plaintext: bytes,
    ) -> EncryptedObject:
        """Encrypt one entity revision under the current key version."""

        key = self.unlock(workspace_id)
        binding = ContentBinding(
            workspace_id=workspace_id,
            object_type=object_type,
            object_id=object_id,
            revision=revision,
            key_version=key.version,
        )
        return self._cipher.encrypt(key, binding, plaintext)

    def decrypt(self, encrypted: EncryptedObject) -> bytes:
        """Decrypt one entity revision using the key version it was bound to."""

        key = self.unlock_version(encrypted.binding.workspace_id, encrypted.binding.key_version)
        return self._cipher.decrypt(key, encrypted)

    # Internals -----------------------------------------------------------

    def _new_key(self, workspace_id: WorkspaceId, *, version: int) -> WorkspaceKey:
        return WorkspaceKey(
            workspace_id=workspace_id,
            version=version,
            material=secrets.token_bytes(WORKSPACE_KEY_BYTES),
            created_at=self._clock(),
        )

    def _store_recovery_bundle(self, key: WorkspaceKey) -> RecoveryBundle:
        code = self._recovery_codes.generate()
        envelope = self._wrapper.wrap_for_recovery(key, self._recovery_codes.normalize(code))
        self._envelopes.save_envelope(envelope)
        self._cache(key)
        return RecoveryBundle(envelope=envelope, recovery_code=code)

    def _cache(self, key: WorkspaceKey) -> WorkspaceKey:
        self._unlocked[(str(key.workspace_id), key.version)] = key
        return key

    def _require_current_device_id(self) -> DeviceId:
        device_id = self._envelopes.current_device_id()
        if device_id is None:
            raise KeyManagementError("Local device identity is not initialized.")
        return device_id

    def _require_key_version(self, workspace_id: WorkspaceId) -> int:
        version = self._envelopes.latest_key_version(workspace_id)
        if version < 1:
            raise WorkspaceLockedError("The workspace has no key material yet.")
        return version


def _secret_name(device_id: DeviceId) -> str:
    return f"{DEVICE_SECRET_PREFIX}/{device_id}"


__all__ = [
    "DEVICE_SECRET_PREFIX",
    "DeviceEnrollmentRequest",
    "DeviceRevokedError",
    "KeyManagementError",
    "WorkspaceKeyService",
    "WorkspaceLockedError",
]
