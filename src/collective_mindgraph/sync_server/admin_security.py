"""Session, CSRF, rate limiting, and response headers for the admin surface.

The admin surface never renders workspace content. These controls exist so that
the metadata it does render cannot be read, replayed, or driven by a third
party.
"""

from __future__ import annotations

import hmac
import json
import secrets
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256

SESSION_COOKIE = "cmg_admin_session"
CSRF_FIELD = "csrf_token"
SESSION_TTL_SECONDS = 8 * 60 * 60

# No script, style, image, or frame source is permitted. The admin renders
# plain server-side HTML, so the strictest possible policy is also sufficient.
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cache-Control": "no-store",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


class AdminSecurityError(RuntimeError):
    """Raised when a session, token, or request rate is unacceptable."""


@dataclass(frozen=True, slots=True)
class AdminSession:
    """The authenticated administrator behind one browser session."""

    subject: str
    issuer: str
    csrf_token: str
    issued_at: int


class SessionCodec:
    """Signs and verifies the admin session cookie."""

    def __init__(self, secret: bytes, *, clock: Callable[[], float] | None = None) -> None:
        if len(secret) < 32:
            raise AdminSecurityError("The admin session secret must be at least 32 bytes.")
        self._secret = secret
        self._clock = clock or time.time

    def issue(self, *, subject: str, issuer: str) -> tuple[str, AdminSession]:
        """Return the cookie value and the session it encodes."""

        session = AdminSession(
            subject=subject,
            issuer=issuer,
            csrf_token=secrets.token_urlsafe(32),
            issued_at=int(self._clock()),
        )
        payload = _encode(
            json.dumps(
                {
                    "sub": session.subject,
                    "iss": session.issuer,
                    "csrf": session.csrf_token,
                    "iat": session.issued_at,
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        return f"{payload}.{self.sign(payload)}", session

    def verify(self, cookie: str | None) -> AdminSession:
        """Authenticate a cookie, rejecting tampered or expired sessions."""

        if not cookie or "." not in cookie:
            raise AdminSecurityError("No admin session is present.")
        payload, _, signature = cookie.rpartition(".")
        if not hmac.compare_digest(self.sign(payload), signature):
            raise AdminSecurityError("The admin session signature is invalid.")
        try:
            claims = json.loads(_decode(payload).decode("utf-8"))
        except (ValueError, TypeError) as error:
            raise AdminSecurityError("The admin session is unreadable.") from error
        if not isinstance(claims, dict):
            raise AdminSecurityError("The admin session is unreadable.")
        issued_at = claims.get("iat")
        if not isinstance(issued_at, int):
            raise AdminSecurityError("The admin session is unreadable.")
        if self._clock() - issued_at > SESSION_TTL_SECONDS:
            raise AdminSecurityError("The admin session has expired.")
        return AdminSession(
            subject=str(claims.get("sub", "")),
            issuer=str(claims.get("iss", "")),
            csrf_token=str(claims.get("csrf", "")),
            issued_at=issued_at,
        )

    def sign(self, payload: str) -> str:
        """Return the detached signature for an encoded payload."""

        return _encode(hmac.new(self._secret, payload.encode("ascii"), sha256).digest())


def require_csrf(session: AdminSession, submitted: str | None) -> None:
    """Reject a state-changing request that does not carry its own token."""

    if not submitted or not hmac.compare_digest(session.csrf_token, submitted):
        raise AdminSecurityError("The request is missing a valid CSRF token.")


class FixedWindowRateLimiter:
    """Bounds requests per identity so that admin actions cannot be hammered."""

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if limit < 1 or window_seconds <= 0:
            raise AdminSecurityError("A rate limit requires a positive limit and window.")
        self._limit = limit
        self._window = window_seconds
        self._clock = clock or time.monotonic
        self._seen: dict[str, deque[float]] = {}

    def check(self, identity: str) -> None:
        """Record one request, raising when the identity exceeds its budget."""

        now = self._clock()
        history = self._seen.setdefault(identity, deque())
        while history and now - history[0] > self._window:
            history.popleft()
        if len(history) >= self._limit:
            raise AdminSecurityError("Too many requests; slow down and try again.")
        history.append(now)

    def reset(self, identity: str) -> None:
        self._seen.pop(identity, None)


def _encode(payload: bytes) -> str:
    return urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode(payload: str) -> bytes:
    padding = "=" * (-len(payload) % 4)
    return urlsafe_b64decode(payload + padding)


__all__ = [
    "CONTENT_SECURITY_POLICY",
    "CSRF_FIELD",
    "SECURITY_HEADERS",
    "SESSION_COOKIE",
    "SESSION_TTL_SECONDS",
    "AdminSecurityError",
    "AdminSession",
    "FixedWindowRateLimiter",
    "SessionCodec",
    "require_csrf",
]
