"""Proof Key for Code Exchange values as defined by RFC 7636."""

from __future__ import annotations

import hashlib
import secrets
from base64 import urlsafe_b64encode
from dataclasses import dataclass

CHALLENGE_METHOD = "S256"
MIN_VERIFIER_LENGTH = 43
MAX_VERIFIER_LENGTH = 128
DEFAULT_VERIFIER_BYTES = 64
UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


class PkceError(ValueError):
    """Raised when a verifier does not satisfy RFC 7636."""


@dataclass(frozen=True, slots=True)
class PkcePair:
    """A verifier kept locally and the challenge sent to the provider."""

    verifier: str
    challenge: str
    method: str = CHALLENGE_METHOD

    def __post_init__(self) -> None:
        validate_verifier(self.verifier)
        if self.method != CHALLENGE_METHOD:
            raise PkceError("Only the S256 challenge method is accepted.")
        if self.challenge != derive_challenge(self.verifier):
            raise PkceError("The challenge does not match its verifier.")

    def __repr__(self) -> str:
        return (
            f"PkcePair(method={self.method!r}, challenge={self.challenge!r}, verifier=<redacted>)"
        )

    @classmethod
    def generate(cls, *, entropy_bytes: int = DEFAULT_VERIFIER_BYTES) -> PkcePair:
        """Create a fresh high-entropy verifier and its S256 challenge."""

        verifier = _encode(secrets.token_bytes(entropy_bytes))
        return cls(verifier=verifier, challenge=derive_challenge(verifier))


def validate_verifier(verifier: str) -> None:
    """Reject verifiers outside the length and character set RFC 7636 fixes."""

    if not MIN_VERIFIER_LENGTH <= len(verifier) <= MAX_VERIFIER_LENGTH:
        raise PkceError(
            f"A verifier must be {MIN_VERIFIER_LENGTH}-{MAX_VERIFIER_LENGTH} characters."
        )
    if any(character not in UNRESERVED for character in verifier):
        raise PkceError("A verifier may only use unreserved characters.")


def derive_challenge(verifier: str) -> str:
    """Return ``BASE64URL(SHA256(ASCII(verifier)))`` without padding."""

    return _encode(hashlib.sha256(verifier.encode("ascii")).digest())


def generate_state() -> str:
    """Return an unguessable value binding a callback to its request."""

    return _encode(secrets.token_bytes(32))


def _encode(payload: bytes) -> str:
    return urlsafe_b64encode(payload).decode("ascii").rstrip("=")


__all__ = [
    "CHALLENGE_METHOD",
    "MAX_VERIFIER_LENGTH",
    "MIN_VERIFIER_LENGTH",
    "PkceError",
    "PkcePair",
    "derive_challenge",
    "generate_state",
    "validate_verifier",
]
