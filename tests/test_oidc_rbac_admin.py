"""OIDC contract tests, admin session controls, and the admin surface."""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from collective_mindgraph.infrastructure.security.oidc_client import (
    DEFAULT_SCOPES,
    LOOPBACK_HOST,
    DesktopOidcLogin,
    DesktopOidcSettings,
    LoopbackRedirectReceiver,
    OidcLoginError,
    available_loopback_port,
)
from collective_mindgraph.infrastructure.security.pkce import (
    CHALLENGE_METHOD,
    MAX_VERIFIER_LENGTH,
    MIN_VERIFIER_LENGTH,
    PkceError,
    PkcePair,
    derive_challenge,
    validate_verifier,
)
from collective_mindgraph.sync_server.admin_auth import FLOW_COOKIE, AdminLoginFlow
from collective_mindgraph.sync_server.admin_security import (
    CONTENT_SECURITY_POLICY,
    SESSION_COOKIE,
    AdminSecurityError,
    FixedWindowRateLimiter,
    SessionCodec,
    require_csrf,
)
from collective_mindgraph.sync_server.app import create_sync_app
from collective_mindgraph.sync_server.blob_storage import FilesystemBlobStore
from collective_mindgraph.sync_server.oidc import (
    JwksProvider,
    OidcPrincipalResolver,
    OidcSettings,
    oidc_settings_from_environment,
)
from collective_mindgraph.sync_server.principals import IdentityError
from collective_mindgraph.sync_server.settings import SyncServerSettings

ISSUER = "https://issuer.example.test"
AUDIENCE = "collective-mindgraph-sync"
JWKS_URI = "https://issuer.example.test/jwks"
SECRET = b"a" * 32


def _oidc(**overrides: object) -> OidcSettings:
    values: dict[str, object] = {
        "issuer": ISSUER,
        "audience": AUDIENCE,
        "jwks_uri": JWKS_URI,
        "client_id": "desktop-client",
        "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token",
    }
    values.update(overrides)
    return OidcSettings(**values)  # type: ignore[arg-type]


# PKCE, RFC 7636 -----------------------------------------------------------


def test_pkce_pairs_follow_rfc_7636():
    pair = PkcePair.generate()
    assert pair.method == CHALLENGE_METHOD
    assert MIN_VERIFIER_LENGTH <= len(pair.verifier) <= MAX_VERIFIER_LENGTH
    assert pair.challenge == derive_challenge(pair.verifier)
    assert "=" not in pair.challenge
    assert pair.verifier not in repr(pair)
    assert len({PkcePair.generate().verifier for _ in range(32)}) == 32


def test_pkce_rejects_verifiers_outside_the_specification():
    with pytest.raises(PkceError):
        validate_verifier("short")
    with pytest.raises(PkceError):
        validate_verifier("a" * (MAX_VERIFIER_LENGTH + 1))
    with pytest.raises(PkceError):
        validate_verifier("a" * 42 + "/")
    valid = PkcePair.generate()
    with pytest.raises(PkceError):
        PkcePair(verifier=valid.verifier, challenge="wrong")
    with pytest.raises(PkceError):
        PkcePair(verifier=valid.verifier, challenge=valid.challenge, method="plain")


def test_pkce_challenge_matches_the_rfc_7636_appendix_vector():
    # RFC 7636 appendix B fixes this verifier and its S256 challenge.
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert derive_challenge(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


# Desktop login, RFC 8252 --------------------------------------------------


def test_authorization_requests_use_pkce_state_and_a_loopback_redirect():
    login = DesktopOidcLogin(DesktopOidcSettings(**_desktop()))
    redirect_uri = f"http://{LOOPBACK_HOST}:53211/oidc/callback"
    request = login.build_request(redirect_uri)
    query = parse_qs(urlparse(request.url).query)
    assert query["response_type"] == ["code"]
    assert query["code_challenge_method"] == [CHALLENGE_METHOD]
    assert query["code_challenge"] == [request.pkce.challenge]
    assert query["redirect_uri"] == [redirect_uri]
    assert query["state"] == [request.state]
    assert set(DEFAULT_SCOPES).issubset(set(query["scope"][0].split()))
    assert request.state not in repr(request)


def test_loopback_receiver_binds_only_the_loopback_interface():
    with LoopbackRedirectReceiver() as receiver:
        assert receiver.redirect_uri.startswith(f"http://{LOOPBACK_HOST}:")
        assert receiver.port != 0
    with pytest.raises(OidcLoginError):
        LoopbackRedirectReceiver(host="0.0.0.0")
    assert available_loopback_port() > 0


def test_loopback_receiver_captures_a_real_browser_redirect():
    import urllib.request

    with LoopbackRedirectReceiver() as receiver:
        with urllib.request.urlopen(  # noqa: S310 - loopback only
            f"{receiver.redirect_uri}?code=abc&state=xyz",
            timeout=5,
        ) as response:
            body = response.read()
            assert response.status == 200
            assert response.headers["Cache-Control"] == "no-store"
        assert b"Sign-in complete" in body
        assert receiver.wait(timeout=5) == {"code": "abc", "state": "xyz"}


def test_loopback_receiver_reports_a_failed_redirect_and_ignores_other_paths():
    import urllib.error
    import urllib.request

    with LoopbackRedirectReceiver() as receiver:
        with pytest.raises(urllib.error.HTTPError) as unexpected:
            urllib.request.urlopen(  # noqa: S310 - loopback only
                f"http://{LOOPBACK_HOST}:{receiver.port}/elsewhere",
                timeout=5,
            )
        assert unexpected.value.code == 404
        with urllib.request.urlopen(  # noqa: S310 - loopback only
            f"{receiver.redirect_uri}?error=access_denied",
            timeout=5,
        ) as response:
            assert b"did not complete" in response.read()
        assert receiver.wait(timeout=5) == {"error": "access_denied"}


def test_login_completes_only_when_the_callback_matches_the_request():
    exchanged: list[Mapping[str, str]] = []

    def _exchange(endpoint: str, form: Mapping[str, str]) -> Mapping[str, object]:
        exchanged.append(dict(form))
        return {
            "access_token": "secret-access-value",
            "expires_in": 3600,
            "refresh_token": "secret-refresh-value",
        }

    login = DesktopOidcLogin(DesktopOidcSettings(**_desktop()), exchange=_exchange)
    request = login.build_request(f"http://{LOOPBACK_HOST}:53211/oidc/callback")

    tokens = login.complete(request, {"code": "abc", "state": request.state})
    assert tokens.access_token == "secret-access-value"
    assert tokens.refresh_token == "secret-refresh-value"
    assert not tokens.is_expired
    assert "secret-access-value" not in repr(tokens)
    assert "secret-refresh-value" not in repr(tokens)
    assert exchanged[0]["code_verifier"] == request.pkce.verifier
    assert exchanged[0]["grant_type"] == "authorization_code"

    for callback in (
        {"code": "abc", "state": "forged"},
        {"code": "abc"},
        {"state": request.state},
        {"error": "access_denied", "state": request.state},
    ):
        with pytest.raises(OidcLoginError):
            login.complete(request, callback)


def test_token_responses_must_carry_a_usable_lifetime():
    for payload in (
        {"expires_in": 60},
        {"access_token": "at"},
        {"access_token": "at", "expires_in": 0},
    ):
        login = DesktopOidcLogin(
            DesktopOidcSettings(**_desktop()),
            exchange=lambda _endpoint, _form, payload=payload: payload,
        )
        request = login.build_request(f"http://{LOOPBACK_HOST}:1/oidc/callback")
        with pytest.raises(OidcLoginError):
            login.complete(request, {"code": "abc", "state": request.state})


def test_refresh_requires_a_token_and_reuses_the_client_id():
    seen: list[Mapping[str, str]] = []
    login = DesktopOidcLogin(
        DesktopOidcSettings(**_desktop()),
        exchange=lambda _endpoint, form: (
            seen.append(dict(form)),
            {"access_token": "a", "expires_in": 60},
        )[1],
    )
    assert login.refresh("rt").access_token == "a"
    assert seen[0]["grant_type"] == "refresh_token"
    with pytest.raises(OidcLoginError):
        login.refresh("  ")


def test_desktop_settings_require_https_and_openid():
    for override in (
        {"issuer": "http://issuer.example.test"},
        {"authorization_endpoint": "http://issuer.example.test/authorize"},
        {"token_endpoint": ""},
        {"scopes": ("profile",)},
    ):
        with pytest.raises(OidcLoginError):
            DesktopOidcSettings(**{**_desktop(), **override})


def test_login_reports_when_no_browser_can_open():
    login = DesktopOidcLogin(
        DesktopOidcSettings(**_desktop()),
        open_browser=lambda _url: False,
        timeout_seconds=0.1,
    )
    with pytest.raises(OidcLoginError, match="browser"):
        login.run()


def test_login_times_out_when_the_browser_never_returns():
    login = DesktopOidcLogin(
        DesktopOidcSettings(**_desktop()),
        open_browser=lambda _url: True,
        timeout_seconds=0.1,
    )
    with pytest.raises(OidcLoginError, match="timeout"):
        login.run()


def _desktop() -> dict[str, object]:
    return {
        "issuer": ISSUER,
        "client_id": "desktop-client",
        "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token",
    }


# Server-side token validation --------------------------------------------


@pytest.fixture(scope="module")
def signing_key() -> object:
    from cryptography.hazmat.primitives.asymmetric import rsa

    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks(signing_key: object, kid: str = "key-1") -> dict[str, object]:
    from jwt.algorithms import RSAAlgorithm

    document = RSAAlgorithm.to_jwk(signing_key.public_key(), as_dict=True)  # type: ignore[attr-defined]
    document.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return {"keys": [document]}


def _token(signing_key: object, *, kid: str = "key-1", **claims: object) -> str:
    import jwt

    now = datetime.now(tz=UTC)
    payload: dict[str, object] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "person@example.test",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    payload.update(claims)
    return jwt.encode(payload, signing_key, algorithm="RS256", headers={"kid": kid})


def _resolver(signing_key: object, settings: OidcSettings | None = None) -> OidcPrincipalResolver:
    resolved = settings or _oidc()
    return OidcPrincipalResolver(
        resolved,
        keys=JwksProvider(resolved, fetch=lambda _uri: _jwks(signing_key)),
    )


def test_valid_tokens_resolve_to_their_issuer_and_subject(signing_key: object):
    identity = _resolver(signing_key).resolve(f"Bearer {_token(signing_key)}")
    assert identity.issuer == ISSUER
    assert identity.subject == "person@example.test"


def test_tokens_are_rejected_on_issuer_audience_expiry_and_signature(signing_key: object):
    from cryptography.hazmat.primitives.asymmetric import rsa

    resolver = _resolver(signing_key)
    now = datetime.now(tz=UTC)
    for claims in (
        {"iss": "https://other.example.test"},
        {"aud": "another-audience"},
        {"exp": int((now - timedelta(hours=2)).timestamp())},
        {"sub": "   "},
    ):
        with pytest.raises(IdentityError):
            resolver.resolve(f"Bearer {_token(signing_key, **claims)}")

    foreign = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(IdentityError):
        resolver.resolve(f"Bearer {_token(foreign)}")
    with pytest.raises(IdentityError):
        resolver.resolve(f"Bearer {_token(signing_key, kid='unknown-key')}")


def test_credentials_must_be_well_formed_bearer_tokens(signing_key: object):
    resolver = _resolver(signing_key)
    for credential in (None, "", "Basic abc", "Bearer ", "Bearer not-a-jwt"):
        with pytest.raises(IdentityError):
            resolver.resolve(credential)


def test_unsigned_and_symmetric_tokens_are_refused(signing_key: object):
    import jwt

    resolver = _resolver(signing_key)
    now = int(datetime.now(tz=UTC).timestamp())
    claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": "a", "iat": now, "exp": now + 300}
    unsigned = jwt.encode(claims, key="", algorithm="none", headers={"kid": "key-1"})
    with pytest.raises(IdentityError, match="algorithm"):
        resolver.resolve(f"Bearer {unsigned}")
    symmetric = jwt.encode(claims, key="shared-secret", algorithm="HS256", headers={"kid": "key-1"})
    with pytest.raises(IdentityError, match="algorithm"):
        resolver.resolve(f"Bearer {symmetric}")


def test_tokens_without_a_key_id_are_refused(signing_key: object):
    import jwt

    resolver = _resolver(signing_key)
    now = int(datetime.now(tz=UTC).timestamp())
    token = jwt.encode(
        {"iss": ISSUER, "aud": AUDIENCE, "sub": "a", "iat": now, "exp": now + 300},
        signing_key,
        algorithm="RS256",
    )
    with pytest.raises(IdentityError, match="signing key"):
        resolver.resolve(f"Bearer {token}")


def test_jwks_is_cached_and_refreshed_on_an_unknown_key(signing_key: object):
    calls: list[str] = []
    ticks = iter([0.0, 0.0, 0.0, 0.0, 0.0, 1000.0, 1000.0, 1000.0, 1000.0])

    def _fetch(uri: str) -> dict[str, object]:
        calls.append(uri)
        return _jwks(signing_key)

    settings = _oidc()
    provider = JwksProvider(settings, fetch=_fetch, clock=lambda: next(ticks))
    provider.key_for("key-1")
    provider.key_for("key-1")
    assert len(calls) == 1
    with pytest.raises(IdentityError):
        provider.key_for("missing")
    # An unknown key forces one refresh even before the cache expires.
    assert len(calls) >= 2


def test_jwks_documents_must_be_usable(signing_key: object):
    settings = _oidc()
    for document in ({"keys": "not-a-list"}, {}, "not-a-document"):
        provider = JwksProvider(settings, fetch=lambda _uri, d=document: d)
        with pytest.raises(IdentityError):
            provider.key_for("key-1")
    provider = JwksProvider(settings, fetch=lambda _uri: {"keys": [{"no": "kid"}, "junk"]})
    with pytest.raises(IdentityError):
        provider.key_for("key-1")


def test_oidc_settings_reject_unusable_configuration():
    for override in (
        {"issuer": ""},
        {"issuer": "http://issuer.example.test"},
        {"audience": " "},
        {"jwks_uri": "http://issuer.example.test/jwks"},
        {"client_id": ""},
        {"algorithms": ("HS256",)},
        {"algorithms": ()},
    ):
        with pytest.raises(IdentityError):
            _oidc(**override)


def test_oidc_settings_are_optional_but_complete_when_present(tmp_path: Path):
    assert oidc_settings_from_environment({}) is None
    settings = oidc_settings_from_environment(
        {
            "CMG_SYNC_OIDC_ISSUER": ISSUER,
            "CMG_SYNC_OIDC_AUDIENCE": AUDIENCE,
            "CMG_SYNC_OIDC_JWKS_URI": JWKS_URI,
            "CMG_SYNC_OIDC_CLIENT_ID": "admin-client",
            "CMG_SYNC_OIDC_ALGORITHMS": "RS256, ES256",
        }
    )
    assert settings is not None
    assert settings.algorithms == ("RS256", "ES256")


# Admin session controls ---------------------------------------------------


def test_sessions_are_signed_scoped_and_expiring():
    codec = SessionCodec(SECRET)
    cookie, session = codec.issue(subject="admin@example.test", issuer=ISSUER)
    assert codec.verify(cookie).subject == "admin@example.test"
    assert session.csrf_token

    payload, _, signature = cookie.rpartition(".")
    with pytest.raises(AdminSecurityError):
        codec.verify(f"{payload}.{signature[:-2]}xx")
    with pytest.raises(AdminSecurityError):
        codec.verify(None)
    with pytest.raises(AdminSecurityError):
        codec.verify("no-separator")
    with pytest.raises(AdminSecurityError):
        SessionCodec(b"short")

    forged = SessionCodec(b"b" * 32)
    with pytest.raises(AdminSecurityError):
        forged.verify(cookie)

    expired_codec = SessionCodec(SECRET, clock=lambda: time.time() + 60 * 60 * 24)
    with pytest.raises(AdminSecurityError, match="expired"):
        expired_codec.verify(cookie)


def test_unreadable_session_payloads_are_rejected():
    codec = SessionCodec(SECRET)
    payload = "bm90LWpzb24"
    with pytest.raises(AdminSecurityError):
        codec.verify(f"{payload}.{codec.sign(payload)}")


def test_csrf_tokens_must_match_the_session():
    codec = SessionCodec(SECRET)
    _, session = codec.issue(subject="a", issuer=ISSUER)
    require_csrf(session, session.csrf_token)
    for submitted in (None, "", "wrong"):
        with pytest.raises(AdminSecurityError):
            require_csrf(session, submitted)


def test_rate_limits_bound_each_identity_independently():
    ticks = iter([0.0, 0.0, 0.0, 0.0, 100.0, 100.0])
    limiter = FixedWindowRateLimiter(limit=2, window_seconds=60, clock=lambda: next(ticks))
    limiter.check("a")
    limiter.check("a")
    with pytest.raises(AdminSecurityError):
        limiter.check("a")
    limiter.check("b")
    limiter.check("a")
    limiter.reset("a")
    with pytest.raises(AdminSecurityError):
        FixedWindowRateLimiter(limit=0, window_seconds=60)
    with pytest.raises(AdminSecurityError):
        FixedWindowRateLimiter(limit=1, window_seconds=0)


# Admin login flow ---------------------------------------------------------


def test_admin_login_flow_binds_its_callback_to_the_request():
    codec = SessionCodec(SECRET)
    flow = AdminLoginFlow(
        _oidc(),
        codec,
        exchange=lambda _endpoint, _form: {"access_token": "server-token"},
    )
    url, cookie = flow.start("https://admin.example.test/admin/callback")
    query = parse_qs(urlparse(url).query)
    assert query["code_challenge_method"] == [CHALLENGE_METHOD]
    state = query["state"][0]
    assert flow.finish(cookie, {"code": "abc", "state": state}) == "server-token"

    for callback in ({"code": "abc", "state": "forged"}, {"state": state}, {"error": "denied"}):
        with pytest.raises(IdentityError):
            flow.finish(cookie, callback)
    with pytest.raises(IdentityError):
        flow.finish(None, {"code": "abc", "state": state})
    body, _, signature = cookie.rpartition(".")
    with pytest.raises(IdentityError):
        flow.finish(f"{body}.{signature[:-2]}xx", {"code": "abc", "state": state})


def test_admin_login_flow_expires_and_requires_endpoints():
    codec = SessionCodec(SECRET)
    ticks = iter([0.0, 100000.0])
    flow = AdminLoginFlow(
        _oidc(),
        codec,
        exchange=lambda _endpoint, _form: {"access_token": "t"},
        clock=lambda: next(ticks),
    )
    _, cookie = flow.start("https://admin.example.test/admin/callback")
    with pytest.raises(IdentityError, match="expired"):
        flow.finish(cookie, {"code": "abc", "state": "any"})
    with pytest.raises(IdentityError):
        AdminLoginFlow(_oidc(authorization_endpoint="", token_endpoint=""), codec)


def test_admin_login_flow_rejects_a_token_free_exchange():
    flow = AdminLoginFlow(_oidc(), SessionCodec(SECRET), exchange=lambda _e, _f: {})
    url, cookie = flow.start("https://admin.example.test/admin/callback")
    state = parse_qs(urlparse(url).query)["state"][0]
    with pytest.raises(IdentityError):
        flow.finish(cookie, {"code": "abc", "state": state})


# Admin surface ------------------------------------------------------------


@pytest.fixture()
def admin_client(tmp_path: Path, signing_key: object) -> Iterator[TestClient]:
    settings = SyncServerSettings(
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'admin.sqlite3').as_posix()}",
        blob_root=tmp_path / "blobs",
    )
    app = create_sync_app(
        settings,
        identities=_resolver(signing_key),
        oidc=_oidc(),
        blob_store=FilesystemBlobStore(tmp_path / "blobs"),
        session_secret=SECRET,
        create_schema=True,
    )
    with TestClient(app) as running:
        yield running


def _sign_in(client: TestClient, subject: str = "person@example.test") -> None:
    cookie, _ = client.app.state.admin_sessions.issue(subject=subject, issuer=ISSUER)
    client.cookies.set(SESSION_COOKIE, cookie)


def _csrf(client: TestClient) -> str:
    session = client.app.state.admin_sessions.verify(client.cookies.get(SESSION_COOKIE))
    return session.csrf_token


def test_admin_requires_a_session(admin_client: TestClient):
    assert admin_client.get("/admin/").status_code == 403


def test_admin_login_redirects_to_the_provider(admin_client: TestClient):
    response = admin_client.get("/admin/login", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith(f"{ISSUER}/authorize?")
    assert FLOW_COOKIE in response.cookies
    assert response.headers["Content-Security-Policy"] == CONTENT_SECURITY_POLICY


def test_admin_pages_show_metadata_and_never_content(
    admin_client: TestClient,
    signing_key: object,
):
    token = _token(signing_key)
    workspace = admin_client.post(
        "/sync/v1/workspaces",
        json={"name": "Team"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    workspace_id = workspace["workspace_id"]
    admin_client.post(
        f"/sync/v1/workspaces/{workspace_id}/devices",
        json={
            "device_id": str(uuid4()),
            "name": "Laptop",
            "public_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    _sign_in(admin_client)
    index = admin_client.get("/admin/")
    assert index.status_code == 200
    assert "Team" in index.text
    assert index.headers["Content-Security-Policy"] == CONTENT_SECURITY_POLICY
    assert index.headers["X-Frame-Options"] == "DENY"
    assert index.headers["Cache-Control"] == "no-store"

    detail = admin_client.get(f"/admin/workspaces/{workspace_id}")
    assert detail.status_code == 200
    assert "Laptop" in detail.text
    assert "Synchronized objects" in detail.text
    assert "cannot recall content" in detail.text
    # The surface renders no script and no ciphertext field.
    assert "<script" not in detail.text.lower()
    assert "ciphertext" not in detail.text.lower().replace("ciphertext bytes", "")


def test_admin_actions_require_csrf_and_the_admin_role(
    admin_client: TestClient,
    signing_key: object,
):
    token = _token(signing_key)
    workspace_id = admin_client.post(
        "/sync/v1/workspaces",
        json={"name": "Team"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["workspace_id"]
    _sign_in(admin_client)

    missing = admin_client.post(
        f"/admin/workspaces/{workspace_id}/raw-audio",
        data={"enabled": "on", "csrf_token": "wrong"},
        follow_redirects=False,
    )
    assert missing.status_code == 403

    accepted = admin_client.post(
        f"/admin/workspaces/{workspace_id}/raw-audio",
        data={"enabled": "on", "csrf_token": _csrf(admin_client)},
        follow_redirects=False,
    )
    assert accepted.status_code == 303
    detail = admin_client.get(f"/admin/workspaces/{workspace_id}")
    assert "currently\nenabled" in detail.text or "enabled" in detail.text


def test_admin_can_change_roles_and_revoke_devices(
    admin_client: TestClient,
    signing_key: object,
):
    token = _token(signing_key)
    headers = {"Authorization": f"Bearer {token}"}
    workspace_id = admin_client.post(
        "/sync/v1/workspaces", json={"name": "Team"}, headers=headers
    ).json()["workspace_id"]
    device_id = str(uuid4())
    admin_client.post(
        f"/sync/v1/workspaces/{workspace_id}/devices",
        json={
            "device_id": device_id,
            "name": "Laptop",
            "public_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        },
        headers=headers,
    )
    _sign_in(admin_client)
    csrf = _csrf(admin_client)

    seated = admin_client.post(
        f"/admin/workspaces/{workspace_id}/members",
        data={
            "subject": "editor@example.test",
            "issuer": ISSUER,
            "role": "editor",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert seated.status_code == 303
    assert "editor@example.test" in admin_client.get(f"/admin/workspaces/{workspace_id}").text

    removed = admin_client.post(
        f"/admin/workspaces/{workspace_id}/members",
        data={
            "subject": "editor@example.test",
            "issuer": ISSUER,
            "role": "remove",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert removed.status_code == 303

    revoked = admin_client.post(
        f"/admin/workspaces/{workspace_id}/devices/{device_id}/revoke",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert revoked.status_code == 303
    assert "revoked" in admin_client.get(f"/admin/workspaces/{workspace_id}").text


def test_admin_routes_reject_identifiers_that_are_not_uuids(admin_client: TestClient):
    """Request input never reaches a redirect target or a query value."""

    _sign_in(admin_client)
    csrf = _csrf(admin_client)
    assert admin_client.get("/admin/workspaces/not-a-uuid").status_code == 403
    # A slash-bearing identifier never even reaches a handler.
    escaped = admin_client.get("/admin/workspaces/..%2F..%2Fevil", follow_redirects=False)
    assert escaped.status_code == 404
    assert "location" not in escaped.headers

    forged = admin_client.post(
        "/admin/workspaces/evil.example/raw-audio",
        data={"enabled": "on", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert forged.status_code == 403
    assert "location" not in forged.headers

    workspace_id = str(uuid4())
    bad_device = admin_client.post(
        f"/admin/workspaces/{workspace_id}/devices/not-a-uuid/revoke",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert bad_device.status_code == 403


def test_non_members_cannot_open_a_workspace_page(admin_client: TestClient, signing_key: object):
    workspace_id = admin_client.post(
        "/sync/v1/workspaces",
        json={"name": "Team"},
        headers={"Authorization": f"Bearer {_token(signing_key)}"},
    ).json()["workspace_id"]
    _sign_in(admin_client, subject="stranger@example.test")
    assert admin_client.get(f"/admin/workspaces/{workspace_id}").status_code == 403


def test_the_browser_callback_opens_a_session_from_a_provider_token(
    admin_client: TestClient,
    signing_key: object,
):
    """The whole browser flow: redirect out, come back, receive a session."""

    issued = _token(signing_key)
    admin_client.app.state.admin_login_flow = AdminLoginFlow(
        _oidc(),
        admin_client.app.state.admin_sessions,
        exchange=lambda _endpoint, _form: {"access_token": issued},
    )
    started = admin_client.get("/admin/login", follow_redirects=False)
    state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]

    completed = admin_client.get(
        f"/admin/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert completed.status_code == 303
    assert completed.headers["location"] == "/admin/"
    session = admin_client.app.state.admin_sessions.verify(completed.cookies.get(SESSION_COOKIE))
    assert session.subject == "person@example.test"
    assert admin_client.get("/admin/").status_code == 200


def test_the_browser_callback_rejects_a_mismatched_state(
    admin_client: TestClient,
    signing_key: object,
):
    admin_client.app.state.admin_login_flow = AdminLoginFlow(
        _oidc(),
        admin_client.app.state.admin_sessions,
        exchange=lambda _endpoint, _form: {"access_token": _token(signing_key)},
    )
    admin_client.get("/admin/login", follow_redirects=False)
    forged = admin_client.get("/admin/callback?code=abc&state=forged", follow_redirects=False)
    assert forged.status_code == 401
    assert SESSION_COOKIE not in forged.cookies


def test_logout_clears_the_session(admin_client: TestClient):
    _sign_in(admin_client)
    response = admin_client.post(
        "/admin/logout",
        data={"csrf_token": _csrf(admin_client)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_the_service_still_starts_without_oidc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CMG_SYNC_BOOTSTRAP_TOKENS", "token=operator@example.test")
    monkeypatch.delenv("CMG_SYNC_OIDC_ISSUER", raising=False)
    settings = SyncServerSettings(
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'plain.sqlite3').as_posix()}",
        blob_root=tmp_path / "blobs",
    )
    app = create_sync_app(settings, session_secret=SECRET, create_schema=True)
    with TestClient(app) as client:
        assert client.get("/sync/v1/health").json()["status"] == "ok"
        # Without OIDC the admin sign-in is unavailable rather than insecure.
        assert client.get("/admin/login", follow_redirects=False).status_code == 401
