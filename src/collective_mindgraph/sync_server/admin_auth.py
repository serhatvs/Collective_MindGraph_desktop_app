"""Browser sign-in for the admin surface.

The admin uses the same provider as the desktop but completes the code flow on
the server, so no token is ever exposed to a page. PKCE is applied here too:
the flow is confidential, but a proof key costs nothing and removes code
interception as a concern entirely.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from base64 import urlsafe_b64encode
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from urllib.parse import urlencode

from .admin_security import AdminSecurityError, SessionCodec
from .oidc import OidcSettings
from .principals import IdentityError

FLOW_COOKIE = "cmg_admin_flow"
FLOW_TTL_SECONDS = 600
CHALLENGE_METHOD = "S256"


@dataclass(frozen=True, slots=True)
class PendingLogin:
    """The state a callback must prove it belongs to."""

    state: str
    verifier: str
    redirect_uri: str
    started_at: int

    def __repr__(self) -> str:
        return f"PendingLogin(redirect_uri={self.redirect_uri!r}, state=<redacted>)"


class AdminLoginFlow:
    """Starts and finishes the browser authorization-code flow."""

    def __init__(
        self,
        settings: OidcSettings,
        codec: SessionCodec,
        *,
        exchange: Callable[[str, Mapping[str, str]], Mapping[str, object]] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if not settings.authorization_endpoint or not settings.token_endpoint:
            raise IdentityError(
                "The admin surface requires the OIDC authorization and token endpoints."
            )
        self._settings = settings
        self._codec = codec
        self._exchange = exchange or _post_form
        self._clock = clock or time.time

    def start(self, redirect_uri: str) -> tuple[str, str]:
        """Return the provider URL and the signed flow cookie to set."""

        verifier = _encode(secrets.token_bytes(64))
        pending = PendingLogin(
            state=_encode(secrets.token_bytes(32)),
            verifier=verifier,
            redirect_uri=redirect_uri,
            started_at=int(self._clock()),
        )
        parameters = {
            "response_type": "code",
            "client_id": self._settings.client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid profile email",
            "state": pending.state,
            "code_challenge": _challenge(verifier),
            "code_challenge_method": CHALLENGE_METHOD,
        }
        separator = "&" if "?" in self._settings.authorization_endpoint else "?"
        url = f"{self._settings.authorization_endpoint}{separator}{urlencode(parameters)}"
        return url, self._seal(pending)

    def finish(self, cookie: str | None, query: Mapping[str, str]) -> str:
        """Validate the callback and return the provider's access token."""

        pending = self._open(cookie)
        if query.get("error"):
            raise IdentityError("The provider rejected the admin sign-in.")
        state = query.get("state", "")
        if not state or not hmac.compare_digest(state, pending.state):
            raise IdentityError("The sign-in response did not match the request.")
        code = query.get("code", "")
        if not code:
            raise IdentityError("The provider returned no authorization code.")
        payload = self._exchange(
            self._settings.token_endpoint,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": pending.redirect_uri,
                "client_id": self._settings.client_id,
                "code_verifier": pending.verifier,
            },
        )
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise IdentityError("The provider returned no access token.")
        return token

    def _seal(self, pending: PendingLogin) -> str:
        body = _encode(
            json.dumps(
                {
                    "state": pending.state,
                    "verifier": pending.verifier,
                    "redirect_uri": pending.redirect_uri,
                    "started_at": pending.started_at,
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        return f"{body}.{self._codec.sign(body)}"

    def _open(self, cookie: str | None) -> PendingLogin:
        if not cookie or "." not in cookie:
            raise IdentityError("No sign-in is in progress.")
        body, _, signature = cookie.rpartition(".")
        if not hmac.compare_digest(self._codec.sign(body), signature):
            raise IdentityError("The sign-in state was tampered with.")
        try:
            claims = json.loads(_decode(body).decode("utf-8"))
        except (ValueError, TypeError) as error:
            raise IdentityError("The sign-in state is unreadable.") from error
        if not isinstance(claims, dict) or not isinstance(claims.get("started_at"), int):
            raise IdentityError("The sign-in state is unreadable.")
        pending = PendingLogin(
            state=str(claims.get("state", "")),
            verifier=str(claims.get("verifier", "")),
            redirect_uri=str(claims.get("redirect_uri", "")),
            started_at=int(claims["started_at"]),
        )
        if self._clock() - pending.started_at > FLOW_TTL_SECONDS:
            raise IdentityError("The sign-in attempt expired; start again.")
        return pending


def _challenge(verifier: str) -> str:
    return _encode(hashlib.sha256(verifier.encode("ascii")).digest())


def _encode(payload: bytes) -> str:
    return urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode(payload: str) -> bytes:
    from base64 import urlsafe_b64decode

    return urlsafe_b64decode(payload + "=" * (-len(payload) % 4))


def _post_form(  # pragma: no cover - network boundary
    endpoint: str,
    form: Mapping[str, str],
) -> Mapping[str, object]:
    import httpx

    response = httpx.post(endpoint, data=dict(form), timeout=30.0)
    if response.status_code >= 400:
        raise IdentityError("The token endpoint rejected the exchange.")
    payload = response.json()
    if not isinstance(payload, dict):
        raise IdentityError("The token endpoint returned an unusable response.")
    return payload


__all__ = [
    "FLOW_COOKIE",
    "FLOW_TTL_SECONDS",
    "AdminLoginFlow",
    "AdminSecurityError",
    "PendingLogin",
]
