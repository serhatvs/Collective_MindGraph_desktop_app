"""Provider-independent OIDC access-token validation.

The service trusts no client-supplied identity. Every request is authenticated
by verifying a signed token against the provider's published keys, its issuer,
and this deployment's audience.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from .principals import IdentityError, ResolvedIdentity

DEFAULT_JWKS_CACHE_SECONDS = 300
DEFAULT_LEEWAY_SECONDS = 60
SUPPORTED_ALGORITHMS = ("RS256", "RS384", "RS512", "ES256", "ES384")


@dataclass(frozen=True, slots=True)
class OidcSettings:
    """Everything a deployment must state before it can accept logins."""

    issuer: str
    audience: str
    jwks_uri: str
    client_id: str
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    algorithms: tuple[str, ...] = field(default=SUPPORTED_ALGORITHMS)
    jwks_cache_seconds: int = DEFAULT_JWKS_CACHE_SECONDS
    leeway_seconds: int = DEFAULT_LEEWAY_SECONDS

    def __post_init__(self) -> None:
        for name, value in (
            ("issuer", self.issuer),
            ("audience", self.audience),
            ("JWKS URI", self.jwks_uri),
            ("client id", self.client_id),
        ):
            if not value.strip():
                raise IdentityError(f"The OIDC {name} must be configured.")
        if not self.issuer.startswith("https://"):
            raise IdentityError("The OIDC issuer must be an HTTPS URL.")
        if not self.jwks_uri.startswith("https://"):
            raise IdentityError("The OIDC JWKS URI must be an HTTPS URL.")
        unsupported = set(self.algorithms) - set(SUPPORTED_ALGORITHMS)
        if unsupported or not self.algorithms:
            raise IdentityError("Only asymmetric OIDC signing algorithms are accepted.")


def oidc_settings_from_environment(
    environment: dict[str, str] | None = None,
) -> OidcSettings | None:
    """Build settings when the deployment configured OIDC, else ``None``."""

    source = environment if environment is not None else dict(os.environ)
    issuer = source.get("CMG_SYNC_OIDC_ISSUER", "").strip()
    if not issuer:
        return None
    algorithms = tuple(
        entry.strip()
        for entry in source.get("CMG_SYNC_OIDC_ALGORITHMS", "").split(",")
        if entry.strip()
    )
    return OidcSettings(
        issuer=issuer,
        audience=source.get("CMG_SYNC_OIDC_AUDIENCE", "").strip(),
        jwks_uri=source.get("CMG_SYNC_OIDC_JWKS_URI", "").strip(),
        client_id=source.get("CMG_SYNC_OIDC_CLIENT_ID", "").strip(),
        authorization_endpoint=source.get("CMG_SYNC_OIDC_AUTHORIZATION_ENDPOINT", "").strip(),
        token_endpoint=source.get("CMG_SYNC_OIDC_TOKEN_ENDPOINT", "").strip(),
        algorithms=algorithms or SUPPORTED_ALGORITHMS,
    )


class JwksProvider:
    """Fetches and caches the provider's signing keys."""

    def __init__(
        self,
        settings: OidcSettings,
        *,
        fetch: Any = None,
        clock: Any = None,
    ) -> None:
        self._settings = settings
        self._fetch = fetch or _fetch_jwks
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._keys: dict[str, Any] = {}
        self._expires_at = 0.0

    def key_for(self, kid: str) -> Any:
        """Return the signing key for a key id, refreshing once on a miss."""

        with self._lock:
            if self._clock() >= self._expires_at:
                self._refresh()
            key = self._keys.get(kid)
            if key is None:
                # A rotated key can appear before the cache expires.
                self._refresh()
                key = self._keys.get(kid)
        if key is None:
            raise IdentityError("The token was signed by an unknown key.")
        return key

    def _refresh(self) -> None:
        from jwt import PyJWK

        document = self._fetch(self._settings.jwks_uri)
        keys = document.get("keys") if isinstance(document, dict) else None
        if not isinstance(keys, list):
            raise IdentityError("The provider returned an unusable JWKS document.")
        resolved: dict[str, Any] = {}
        for entry in keys:
            if not isinstance(entry, dict):
                continue
            kid = entry.get("kid")
            if isinstance(kid, str) and kid:
                resolved[kid] = PyJWK(entry)
        self._keys = resolved
        self._expires_at = self._clock() + self._settings.jwks_cache_seconds


class OidcPrincipalResolver:
    """Validates a bearer access token and returns its issuer and subject."""

    def __init__(self, settings: OidcSettings, *, keys: JwksProvider | None = None) -> None:
        self._settings = settings
        self._keys = keys or JwksProvider(settings)

    def resolve(self, authorization: str | None) -> ResolvedIdentity:
        import jwt

        token = _bearer_token(authorization)
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as error:
            raise IdentityError("The presented token is malformed.") from error
        algorithm = header.get("alg")
        if algorithm not in self._settings.algorithms:
            raise IdentityError("The token uses an unaccepted signing algorithm.")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise IdentityError("The token does not identify its signing key.")
        try:
            claims = jwt.decode(
                token,
                self._keys.key_for(kid).key,
                algorithms=list(self._settings.algorithms),
                audience=self._settings.audience,
                issuer=self._settings.issuer,
                leeway=self._settings.leeway_seconds,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as error:
            raise IdentityError("The presented token failed validation.") from error
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise IdentityError("The token carries no usable subject.")
        return ResolvedIdentity(issuer=self._settings.issuer, subject=subject)


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise IdentityError("A bearer credential is required.")
    token = authorization[len("bearer ") :].strip()
    if not token:
        raise IdentityError("A bearer credential is required.")
    return token


def _fetch_jwks(uri: str) -> dict[str, Any]:  # pragma: no cover - network boundary
    import json
    import urllib.request

    request = urllib.request.Request(uri, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - HTTPS enforced
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise IdentityError("The provider returned an unusable JWKS document.")
    return payload


__all__ = [
    "DEFAULT_JWKS_CACHE_SECONDS",
    "SUPPORTED_ALGORITHMS",
    "JwksProvider",
    "OidcPrincipalResolver",
    "OidcSettings",
    "oidc_settings_from_environment",
]
