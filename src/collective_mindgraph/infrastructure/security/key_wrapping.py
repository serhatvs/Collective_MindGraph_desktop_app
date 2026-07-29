"""X25519 + HKDF key wrapping and scrypt recovery wrapping."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from collective_mindgraph.domain import (
    WORKSPACE_KEY_BYTES,
    DeviceKey,
    KeyEnvelope,
    WorkspaceKey,
)
from collective_mindgraph.domain.identifiers import EnvelopeId, WorkspaceId

DEVICE_WRAP_INFO = b"collective-mindgraph/workspace-key-wrap/x25519/v1"
RECOVERY_WRAP_INFO = b"collective-mindgraph/workspace-key-wrap/recovery/v1"
WRAP_NONCE_BYTES = 12
HKDF_SALT_BYTES = 32
RECOVERY_SALT_BYTES = 16
_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1


class KeyUnwrapError(ValueError):
    """Raised when a key envelope cannot be authenticated or decoded."""


class X25519KeyWrapper:
    """Wraps workspace keys for device public keys and for recovery codes."""

    def __init__(
        self,
        *,
        random_source: Callable[[int], bytes] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._random = random_source or os.urandom
        self._clock = clock or (lambda: datetime.now(tz=UTC))

    # Device recipients ---------------------------------------------------

    def wrap_for_device(self, key: WorkspaceKey, device: DeviceKey) -> KeyEnvelope:
        """Wrap one workspace key version for a single device public key."""

        if device.workspace_id != key.workspace_id:
            raise ValueError("Device belongs to a different workspace.")
        if not device.can_receive_keys:
            raise ValueError("Only local or trusted devices may receive workspace keys.")
        ephemeral = X25519PrivateKey.generate()
        ephemeral_public = _public_bytes(ephemeral.public_key())
        shared = ephemeral.exchange(X25519PublicKey.from_public_bytes(device.public_key))
        salt = self._random(HKDF_SALT_BYTES)
        info = _device_info(key.workspace_id, key.version, ephemeral_public, device.public_key)
        wrapping_key = _hkdf(shared, salt, info)
        nonce = self._random(WRAP_NONCE_BYTES)
        sealed = AESGCM(wrapping_key).encrypt(nonce, key.material, info)
        return KeyEnvelope(
            id=EnvelopeId(str(uuid4())),
            workspace_id=key.workspace_id,
            key_version=key.version,
            wrapped_key=nonce + sealed,
            created_at=self._clock(),
            recipient_device_id=device.device_id,
            ephemeral_public_key=ephemeral_public,
            salt=salt,
        )

    def unwrap_for_device(self, envelope: KeyEnvelope, device_private_key: bytes) -> WorkspaceKey:
        """Recover the workspace key from a device envelope."""

        if envelope.is_recovery:
            raise KeyUnwrapError("Recovery envelopes cannot be unwrapped with a device key.")
        ephemeral_public = _require_parameter(envelope.ephemeral_public_key, "an ephemeral key")
        salt = _require_parameter(envelope.salt, "a derivation salt")
        try:
            private = X25519PrivateKey.from_private_bytes(device_private_key)
            recipient_public = _public_bytes(private.public_key())
            shared = private.exchange(X25519PublicKey.from_public_bytes(ephemeral_public))
        except ValueError as error:
            raise KeyUnwrapError("Device key material is invalid.") from error
        info = _device_info(
            envelope.workspace_id,
            envelope.key_version,
            ephemeral_public,
            recipient_public,
        )
        material = _open(envelope.wrapped_key, _hkdf(shared, salt, info), info)
        return self._workspace_key(envelope, material)

    # Recovery recipients -------------------------------------------------

    def wrap_for_recovery(self, key: WorkspaceKey, recovery_code: str) -> KeyEnvelope:
        """Wrap one workspace key version under a normalized recovery code."""

        salt = self._random(RECOVERY_SALT_BYTES)
        info = _recovery_info(key.workspace_id, key.version)
        nonce = self._random(WRAP_NONCE_BYTES)
        sealed = AESGCM(_scrypt(recovery_code, salt)).encrypt(nonce, key.material, info)
        return KeyEnvelope(
            id=EnvelopeId(str(uuid4())),
            workspace_id=key.workspace_id,
            key_version=key.version,
            wrapped_key=nonce + sealed,
            created_at=self._clock(),
            recipient_device_id=None,
            ephemeral_public_key=None,
            salt=salt,
        )

    def unwrap_for_recovery(self, envelope: KeyEnvelope, recovery_code: str) -> WorkspaceKey:
        """Recover the workspace key from a recovery envelope."""

        if not envelope.is_recovery:
            raise KeyUnwrapError("Device envelopes cannot be unwrapped with a recovery code.")
        salt = _require_parameter(envelope.salt, "a derivation salt")
        info = _recovery_info(envelope.workspace_id, envelope.key_version)
        material = _open(envelope.wrapped_key, _scrypt(recovery_code, salt), info)
        return self._workspace_key(envelope, material)

    def _workspace_key(self, envelope: KeyEnvelope, material: bytes) -> WorkspaceKey:
        if len(material) != WORKSPACE_KEY_BYTES:
            raise KeyUnwrapError("Unwrapped workspace key has an unexpected length.")
        return WorkspaceKey(
            workspace_id=envelope.workspace_id,
            version=envelope.key_version,
            material=material,
            created_at=envelope.created_at,
        )


class X25519DeviceKeyFactory:
    """Generates and derives this device's X25519 identity."""

    def generate_private_key(self) -> bytes:
        return X25519PrivateKey.generate().private_bytes(
            encoding=Encoding.Raw,
            format=PrivateFormat.Raw,
            encryption_algorithm=NoEncryption(),
        )

    def public_key(self, private_key: bytes) -> bytes:
        return _public_bytes(X25519PrivateKey.from_private_bytes(private_key).public_key())


def _device_info(
    workspace_id: WorkspaceId,
    key_version: int,
    ephemeral_public: bytes,
    recipient_public: bytes,
) -> bytes:
    return b"".join(
        (
            DEVICE_WRAP_INFO,
            _field(str(workspace_id).encode("utf-8")),
            _field(str(key_version).encode("ascii")),
            _field(ephemeral_public),
            _field(recipient_public),
        )
    )


def _recovery_info(workspace_id: WorkspaceId, key_version: int) -> bytes:
    return b"".join(
        (
            RECOVERY_WRAP_INFO,
            _field(str(workspace_id).encode("utf-8")),
            _field(str(key_version).encode("ascii")),
        )
    )


def _field(value: bytes) -> bytes:
    return len(value).to_bytes(4, "big") + value


def _require_parameter(value: bytes | None, label: str) -> bytes:
    if value is None:
        raise KeyUnwrapError(f"Key envelope is missing {label}.")
    return value


def _hkdf(shared: bytes, salt: bytes, info: bytes) -> bytes:
    return HKDF(algorithm=SHA256(), length=32, salt=salt, info=info).derive(shared)


def _scrypt(recovery_code: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P).derive(
        recovery_code.encode("utf-8")
    )


def _open(wrapped_key: bytes, wrapping_key: bytes, info: bytes) -> bytes:
    if len(wrapped_key) <= WRAP_NONCE_BYTES:
        raise KeyUnwrapError("Wrapped key material is truncated.")
    nonce, sealed = wrapped_key[:WRAP_NONCE_BYTES], wrapped_key[WRAP_NONCE_BYTES:]
    try:
        return AESGCM(wrapping_key).decrypt(nonce, sealed, info)
    except InvalidTag as error:
        raise KeyUnwrapError("Key envelope failed authentication.") from error


def _public_bytes(public_key: X25519PublicKey) -> bytes:
    """Return the 32-byte raw X25519 encoding the domain requires."""

    return public_key.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)


__all__ = [
    "DEVICE_WRAP_INFO",
    "RECOVERY_WRAP_INFO",
    "KeyUnwrapError",
    "X25519DeviceKeyFactory",
    "X25519KeyWrapper",
]
