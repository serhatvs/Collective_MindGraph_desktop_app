"""Offline-safety, local-resource, and end-to-end encryption boundaries."""

from .content_cipher import AesGcmContentCipher, ContentAuthenticationError
from .device_secrets import (
    DeviceSecretUnavailableError,
    ProtectedFileSecretStore,
    create_device_secret_store,
)
from .key_wrapping import KeyUnwrapError, X25519DeviceKeyFactory, X25519KeyWrapper
from .oidc_client import (
    AuthorizationRequest,
    DesktopOidcLogin,
    DesktopOidcSettings,
    LoopbackRedirectReceiver,
    OidcLoginError,
    TokenSet,
)
from .pkce import PkceError, PkcePair, derive_challenge, generate_state
from .recovery_codes import ChecksummedRecoveryCodeFactory, InvalidRecoveryCodeError

__all__ = [
    "AesGcmContentCipher",
    "AuthorizationRequest",
    "ChecksummedRecoveryCodeFactory",
    "ContentAuthenticationError",
    "DesktopOidcLogin",
    "DesktopOidcSettings",
    "DeviceSecretUnavailableError",
    "InvalidRecoveryCodeError",
    "KeyUnwrapError",
    "LoopbackRedirectReceiver",
    "OidcLoginError",
    "PkceError",
    "PkcePair",
    "ProtectedFileSecretStore",
    "TokenSet",
    "X25519DeviceKeyFactory",
    "X25519KeyWrapper",
    "create_device_secret_store",
    "derive_challenge",
    "generate_state",
]
