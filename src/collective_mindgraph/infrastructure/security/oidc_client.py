"""Native-app OIDC login using the system browser and a loopback redirect.

RFC 8252 requires a native client to use the operating system's browser and a
loopback redirect on a port chosen at request time, and RFC 7636 requires the
S256 proof key. Both are enforced here rather than assumed.
"""

from __future__ import annotations

import http.server
import socket
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlparse

from .pkce import CHALLENGE_METHOD, PkcePair, generate_state

LOOPBACK_HOST = "127.0.0.1"
DEFAULT_SCOPES = ("openid", "profile", "email", "offline_access")
DEFAULT_TIMEOUT_SECONDS = 300.0

_COMPLETED_PAGE = (
    b"<!doctype html><meta charset=utf-8><title>Sign-in complete</title>"
    b"<p>Sign-in complete. You can close this window and return to "
    b"Collective MindGraph.</p>"
)
_FAILED_PAGE = (
    b"<!doctype html><meta charset=utf-8><title>Sign-in failed</title>"
    b"<p>Sign-in did not complete. Return to Collective MindGraph and try again.</p>"
)


class OidcLoginError(RuntimeError):
    """Raised when an interactive login cannot complete."""


@dataclass(frozen=True, slots=True)
class DesktopOidcSettings:
    """Provider details a desktop installation needs to start a login."""

    issuer: str
    client_id: str
    authorization_endpoint: str
    token_endpoint: str
    scopes: tuple[str, ...] = field(default=DEFAULT_SCOPES)

    def __post_init__(self) -> None:
        for name, value in (
            ("issuer", self.issuer),
            ("client id", self.client_id),
            ("authorization endpoint", self.authorization_endpoint),
            ("token endpoint", self.token_endpoint),
        ):
            if not value.strip():
                raise OidcLoginError(f"The OIDC {name} must be configured.")
        for name, value in (
            ("issuer", self.issuer),
            ("authorization endpoint", self.authorization_endpoint),
            ("token endpoint", self.token_endpoint),
        ):
            if not value.startswith("https://"):
                raise OidcLoginError(f"The OIDC {name} must be an HTTPS URL.")
        if "openid" not in self.scopes:
            raise OidcLoginError("The openid scope is required.")


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    """One in-flight login, including the secrets it must not leak."""

    url: str
    state: str
    pkce: PkcePair
    redirect_uri: str

    def __repr__(self) -> str:
        return f"AuthorizationRequest(redirect_uri={self.redirect_uri!r}, state=<redacted>)"


@dataclass(frozen=True, slots=True)
class TokenSet:
    """Tokens returned by the provider."""

    access_token: str
    expires_at: datetime
    refresh_token: str | None = None
    id_token: str | None = None

    def __repr__(self) -> str:
        return f"TokenSet(expires_at={self.expires_at.isoformat()!r}, tokens=<redacted>)"

    @property
    def is_expired(self) -> bool:
        return datetime.now(tz=UTC) >= self.expires_at


class LoopbackRedirectReceiver:
    """Serves exactly one redirect on ``127.0.0.1`` at an ephemeral port."""

    def __init__(self, *, host: str = LOOPBACK_HOST) -> None:
        if host not in {LOOPBACK_HOST, "::1"}:
            raise OidcLoginError("A native redirect may only bind the loopback interface.")
        self._result: dict[str, str] = {}
        self._received = threading.Event()
        self._server = http.server.HTTPServer((host, 0), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        port: int = self._server.server_address[1]
        return port

    @property
    def redirect_uri(self) -> str:
        return f"http://{LOOPBACK_HOST}:{self.port}/oidc/callback"

    def __enter__(self) -> LoopbackRedirectReceiver:
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def wait(self, *, timeout: float) -> dict[str, str]:
        """Block until the browser redirects back, or the wait times out."""

        if not self._received.wait(timeout):
            raise OidcLoginError("The sign-in did not complete before the timeout.")
        return dict(self._result)

    def _handler(self) -> type[http.server.BaseHTTPRequestHandler]:
        receiver = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
                parsed = urlparse(self.path)
                if parsed.path != "/oidc/callback":
                    self.send_error(404)
                    return
                query = {key: values[0] for key, values in parse_qs(parsed.query).items() if values}
                receiver._result = query
                body = _COMPLETED_PAGE if "code" in query else _FAILED_PAGE
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                receiver._received.set()

            def log_message(self, *_: object) -> None:
                """Keep redirect parameters out of the application log."""

        return Handler


class DesktopOidcLogin:
    """Drives the interactive login and the authorization-code exchange."""

    def __init__(
        self,
        settings: DesktopOidcSettings,
        *,
        open_browser: Callable[[str], bool] | None = None,
        exchange: Callable[[str, Mapping[str, str]], Mapping[str, object]] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._settings = settings
        self._open_browser = open_browser or _open_system_browser
        self._exchange = exchange or _post_form
        self._timeout = timeout_seconds

    def build_request(self, redirect_uri: str) -> AuthorizationRequest:
        """Compose the authorization URL for one login attempt."""

        pkce = PkcePair.generate()
        state = generate_state()
        parameters = {
            "response_type": "code",
            "client_id": self._settings.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(self._settings.scopes),
            "state": state,
            "code_challenge": pkce.challenge,
            "code_challenge_method": CHALLENGE_METHOD,
        }
        separator = "&" if "?" in self._settings.authorization_endpoint else "?"
        url = f"{self._settings.authorization_endpoint}{separator}{urlencode(parameters)}"
        return AuthorizationRequest(url=url, state=state, pkce=pkce, redirect_uri=redirect_uri)

    def complete(self, request: AuthorizationRequest, callback: Mapping[str, str]) -> TokenSet:
        """Validate the redirect and exchange the code for tokens."""

        error = callback.get("error")
        if error:
            raise OidcLoginError(f"The provider rejected the sign-in: {error}.")
        returned_state = callback.get("state", "")
        if not returned_state or not _constant_time_equals(returned_state, request.state):
            raise OidcLoginError("The sign-in response did not match the request.")
        code = callback.get("code", "")
        if not code:
            raise OidcLoginError("The provider returned no authorization code.")
        payload = self._exchange(
            self._settings.token_endpoint,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": request.redirect_uri,
                "client_id": self._settings.client_id,
                "code_verifier": request.pkce.verifier,
            },
        )
        return _token_set(payload)

    def refresh(self, refresh_token: str) -> TokenSet:
        """Exchange a refresh token without any user interaction."""

        if not refresh_token.strip():
            raise OidcLoginError("A refresh token is required.")
        payload = self._exchange(
            self._settings.token_endpoint,
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self._settings.client_id,
            },
        )
        return _token_set(payload)

    def run(self) -> TokenSet:
        """Open the system browser and wait for the loopback redirect."""

        with LoopbackRedirectReceiver() as receiver:
            request = self.build_request(receiver.redirect_uri)
            if not self._open_browser(request.url):
                raise OidcLoginError("No system browser could be opened for sign-in.")
            callback = receiver.wait(timeout=self._timeout)
        return self.complete(request, callback)


def _token_set(payload: Mapping[str, object]) -> TokenSet:
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise OidcLoginError("The provider returned no access token.")
    expires_in = payload.get("expires_in")
    seconds = int(expires_in) if isinstance(expires_in, int | float | str) else 0
    if seconds <= 0:
        raise OidcLoginError("The provider returned no usable token lifetime.")
    refresh_token = payload.get("refresh_token")
    id_token = payload.get("id_token")
    return TokenSet(
        access_token=access_token,
        expires_at=datetime.now(tz=UTC) + timedelta(seconds=seconds),
        refresh_token=refresh_token if isinstance(refresh_token, str) else None,
        id_token=id_token if isinstance(id_token, str) else None,
    )


def _constant_time_equals(first: str, second: str) -> bool:
    import hmac

    return hmac.compare_digest(first, second)


def _open_system_browser(url: str) -> bool:  # pragma: no cover - platform boundary
    import webbrowser

    return webbrowser.open(url, new=1, autoraise=True)


def _post_form(  # pragma: no cover - network boundary
    endpoint: str,
    form: Mapping[str, str],
) -> Mapping[str, object]:
    import httpx

    response = httpx.post(endpoint, data=dict(form), timeout=30.0)
    if response.status_code >= 400:
        raise OidcLoginError("The token endpoint rejected the exchange.")
    payload = response.json()
    if not isinstance(payload, dict):
        raise OidcLoginError("The token endpoint returned an unusable response.")
    return payload


def available_loopback_port() -> int:
    """Return a free loopback port, used by tests and diagnostics."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((LOOPBACK_HOST, 0))
        port: int = probe.getsockname()[1]
        return port


__all__ = [
    "DEFAULT_SCOPES",
    "LOOPBACK_HOST",
    "AuthorizationRequest",
    "DesktopOidcLogin",
    "DesktopOidcSettings",
    "LoopbackRedirectReceiver",
    "OidcLoginError",
    "TokenSet",
    "available_loopback_port",
]
