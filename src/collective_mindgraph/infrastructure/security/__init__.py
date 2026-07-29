"""Offline-safety, local-resource, and end-to-end encryption boundaries."""

from .content_cipher import AesGcmContentCipher, ContentAuthenticationError
from .device_secrets import (
    DeviceSecretUnavailableError,
    ProtectedFileSecretStore,
    create_device_secret_store,
)
from .key_wrapping import KeyUnwrapError, X25519DeviceKeyFactory, X25519KeyWrapper
from .recovery_codes import ChecksummedRecoveryCodeFactory, InvalidRecoveryCodeError

__all__ = [
    "AesGcmContentCipher",
    "ChecksummedRecoveryCodeFactory",
    "ContentAuthenticationError",
    "DeviceSecretUnavailableError",
    "InvalidRecoveryCodeError",
    "KeyUnwrapError",
    "ProtectedFileSecretStore",
    "X25519DeviceKeyFactory",
    "X25519KeyWrapper",
    "create_device_secret_store",
]
