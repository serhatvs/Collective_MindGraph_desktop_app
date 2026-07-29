"""AES-256-GCM content encryption bound to entity revisions."""

from __future__ import annotations

import os
from collections.abc import Callable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from collective_mindgraph.domain import (
    CONTENT_NONCE_BYTES,
    ContentBinding,
    EncryptedObject,
    WorkspaceKey,
)


class ContentAuthenticationError(ValueError):
    """Raised when ciphertext fails authentication against its binding."""


class AesGcmContentCipher:
    """Encrypts entity payloads under a workspace key version."""

    def __init__(self, nonce_source: Callable[[int], bytes] | None = None) -> None:
        self._nonce_source = nonce_source or os.urandom

    def encrypt(
        self,
        key: WorkspaceKey,
        binding: ContentBinding,
        plaintext: bytes,
    ) -> EncryptedObject:
        """Encrypt one revision, authenticating the full binding."""

        if binding.workspace_id != key.workspace_id:
            raise ValueError("Content binding workspace does not match the key.")
        if binding.key_version != key.version:
            raise ValueError("Content binding key version does not match the key.")
        nonce = self._nonce_source(CONTENT_NONCE_BYTES)
        ciphertext = AESGCM(key.material).encrypt(
            nonce,
            plaintext,
            binding.associated_data(),
        )
        return EncryptedObject(binding=binding, nonce=nonce, ciphertext=ciphertext)

    def decrypt(self, key: WorkspaceKey, encrypted: EncryptedObject) -> bytes:
        """Decrypt one revision, rejecting any rebound or altered ciphertext."""

        binding = encrypted.binding
        if binding.workspace_id != key.workspace_id or binding.key_version != key.version:
            raise ContentAuthenticationError(
                "Encrypted object is bound to a different workspace key."
            )
        try:
            return AESGCM(key.material).decrypt(
                encrypted.nonce,
                encrypted.ciphertext,
                binding.associated_data(),
            )
        except InvalidTag as error:
            raise ContentAuthenticationError(
                "Ciphertext failed authentication for its declared binding."
            ) from error


__all__ = ["AesGcmContentCipher", "ContentAuthenticationError"]
