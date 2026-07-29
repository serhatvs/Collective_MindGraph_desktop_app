"""Caller identity resolution.

Stage 5 replaces the bootstrap resolver with provider-independent OIDC. The
protocol exists now so the service already authorizes every request against a
real principal rather than trusting a client-supplied user identifier.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Protocol

BOOTSTRAP_ISSUER = "urn:collective-mindgraph:bootstrap"


class IdentityError(RuntimeError):
    """Raised when a caller cannot be authenticated."""


@dataclass(frozen=True, slots=True)
class ResolvedIdentity:
    """The issuer and subject an authenticated caller presented."""

    issuer: str
    subject: str


class PrincipalResolver(Protocol):
    """Turns a request credential into an authenticated identity."""

    def resolve(self, authorization: str | None) -> ResolvedIdentity: ...


class BootstrapTokenResolver:
    """Static bearer tokens for self-host bootstrap and automated tests.

    This is deliberately minimal and is not an identity provider. It exists so
    that stage 4 can enforce membership and roles end to end before stage 5
    introduces OIDC. Deployments must configure OIDC before public use.
    """

    def __init__(self, tokens: dict[str, str]) -> None:
        if not tokens:
            raise IdentityError("At least one bootstrap token must be configured.")
        self._tokens = dict(tokens)

    @classmethod
    def from_environment(cls, environment: dict[str, str] | None = None) -> BootstrapTokenResolver:
        """Read ``token=subject`` pairs from ``CMG_SYNC_BOOTSTRAP_TOKENS``."""

        source = environment if environment is not None else dict(os.environ)
        raw = source.get("CMG_SYNC_BOOTSTRAP_TOKENS", "")
        tokens: dict[str, str] = {}
        for entry in raw.split(","):
            token, separator, subject = entry.partition("=")
            if separator and token.strip() and subject.strip():
                tokens[token.strip()] = subject.strip()
        return cls(tokens)

    def resolve(self, authorization: str | None) -> ResolvedIdentity:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise IdentityError("A bearer credential is required.")
        presented = authorization[len("bearer ") :].strip()
        for token, subject in self._tokens.items():
            if hmac.compare_digest(token, presented):
                return ResolvedIdentity(issuer=BOOTSTRAP_ISSUER, subject=subject)
        raise IdentityError("The presented credential is not recognized.")


__all__ = [
    "BOOTSTRAP_ISSUER",
    "BootstrapTokenResolver",
    "IdentityError",
    "PrincipalResolver",
    "ResolvedIdentity",
]
