from __future__ import annotations

import asyncio
import hashlib
import os
from base64 import b64encode
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from collective_mindgraph.sync_server.admin_cli import retention_summary
from collective_mindgraph.sync_server.app import create_sync_app
from collective_mindgraph.sync_server.blob_storage import FilesystemBlobStore, digest
from collective_mindgraph.sync_server.contracts import (
    OperationOutcome,
    Role,
    SyncOperationInput,
)
from collective_mindgraph.sync_server.notifications import CursorBroadcaster
from collective_mindgraph.sync_server.principals import (
    BootstrapTokenResolver,
    IdentityError,
)
from collective_mindgraph.sync_server.settings import (
    SyncServerConfigurationError,
    SyncServerSettings,
    get_sync_server_settings,
)

OWNER_TOKEN = "owner-token"
EDITOR_TOKEN = "editor-token"
VIEWER_TOKEN = "viewer-token"
OWNER = {"Authorization": f"Bearer {OWNER_TOKEN}"}
EDITOR = {"Authorization": f"Bearer {EDITOR_TOKEN}"}
VIEWER = {"Authorization": f"Bearer {VIEWER_TOKEN}"}

TOKENS = {
    OWNER_TOKEN: "owner@example.test",
    EDITOR_TOKEN: "editor@example.test",
    VIEWER_TOKEN: "viewer@example.test",
}


POSTGRES_URL = os.environ.get("CMG_SYNC_TEST_DATABASE_URL", "").strip()


def _database_url(tmp_path: Path) -> str:
    """Target PostgreSQL when the release environment supplies one."""

    if POSTGRES_URL:
        return POSTGRES_URL
    return f"sqlite+aiosqlite:///{(tmp_path / 'sync.sqlite3').as_posix()}"


def _settings(tmp_path: Path, **overrides: object) -> SyncServerSettings:
    values: dict[str, object] = {
        "database_url": _database_url(tmp_path),
        "blob_root": tmp_path / "blobs",
    }
    values.update(overrides)
    return SyncServerSettings(**values)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def reset_shared_database(tmp_path: Path) -> Iterator[None]:
    """Give each test an empty schema when a shared server is configured."""

    if POSTGRES_URL:
        asyncio.run(_drop_schema(_settings(tmp_path)))
    yield


async def _drop_schema(settings: SyncServerSettings) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from collective_mindgraph.sync_server.tables import METADATA

    engine = create_async_engine(settings.database_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(METADATA.drop_all)
    finally:
        await engine.dispose()


@pytest.fixture()
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_sync_app(
        _settings(tmp_path),
        identities=BootstrapTokenResolver(TOKENS),
        blob_store=FilesystemBlobStore(tmp_path / "blobs"),
        create_schema=True,
    )
    with TestClient(app) as running:
        yield running


def _create_workspace(client: TestClient, name: str = "Team") -> str:
    response = client.post("/sync/v1/workspaces", json={"name": name}, headers=OWNER)
    assert response.status_code == 201
    return str(response.json()["workspace_id"])


def _register_device(client: TestClient, workspace_id: str, headers: dict[str, str]) -> str:
    device_id = str(uuid4())
    response = client.post(
        f"/sync/v1/workspaces/{workspace_id}/devices",
        json={
            "device_id": device_id,
            "name": "Laptop",
            "public_key": b64encode(bytes(32)).decode("ascii"),
        },
        headers=headers,
    )
    assert response.status_code == 204
    return device_id


def _seat(client: TestClient, workspace_id: str, subject: str, role: str) -> None:
    response = client.put(
        f"/sync/v1/workspaces/{workspace_id}/members",
        json={"subject": subject, "issuer": "urn:collective-mindgraph:bootstrap", "role": role},
        headers=OWNER,
    )
    assert response.status_code == 204


def _operation(
    object_id: str,
    *,
    base_revision: int = 0,
    ciphertext: bytes = b"sealed-payload",
    operation_id: str | None = None,
    deleted: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "operation_id": operation_id or str(uuid4()),
        "object_id": object_id,
        "object_type": "transcript",
        "base_revision": base_revision,
        "key_version": 1,
        "client_timestamp": datetime.now(tz=UTC).isoformat(),
        "deleted": deleted,
    }
    if not deleted:
        payload["ciphertext"] = b64encode(ciphertext).decode("ascii")
        payload["nonce"] = b64encode(bytes(12)).decode("ascii")
    return payload


# Settings ---------------------------------------------------------------


def test_settings_reject_unsupported_and_invalid_configuration(tmp_path: Path):
    with pytest.raises(SyncServerConfigurationError):
        SyncServerSettings(database_url="mysql://host/db", blob_root=tmp_path)
    with pytest.raises(SyncServerConfigurationError):
        SyncServerSettings(database_url="   ", blob_root=tmp_path)
    with pytest.raises(SyncServerConfigurationError):
        _settings(tmp_path, push_operation_limit=0)
    with pytest.raises(SyncServerConfigurationError):
        _settings(tmp_path, pull_limit=9000)
    with pytest.raises(SyncServerConfigurationError):
        _settings(tmp_path, content_retention_days=0)


def test_settings_read_the_environment_and_report_defaults(tmp_path: Path):
    with pytest.raises(SyncServerConfigurationError):
        get_sync_server_settings({})
    with pytest.raises(SyncServerConfigurationError):
        get_sync_server_settings({"CMG_SYNC_DATABASE_URL": "sqlite+aiosqlite:///x"})
    with pytest.raises(SyncServerConfigurationError):
        get_sync_server_settings(
            {
                "CMG_SYNC_DATABASE_URL": "sqlite+aiosqlite:///x",
                "CMG_SYNC_BLOB_ROOT": str(tmp_path),
                "CMG_SYNC_PULL_LIMIT": "not-a-number",
            }
        )
    settings = get_sync_server_settings(
        {
            "CMG_SYNC_DATABASE_URL": "postgresql+asyncpg://user@host/db",
            "CMG_SYNC_BLOB_ROOT": str(tmp_path),
            "CMG_SYNC_TRUSTED_HOSTS": "sync.example.test, other.example.test",
            "CMG_SYNC_PUSH_OPERATION_LIMIT": "250",
        }
    )
    assert settings.is_postgres is True
    assert settings.push_operation_limit == 250
    assert settings.trusted_hosts == ("sync.example.test", "other.example.test")
    # The programme fixes these windows; the defaults must not drift silently.
    assert retention_summary(settings) == {
        "content_days": 30,
        "audit_days": 90,
        "backup_days": 35,
    }


# Identity ---------------------------------------------------------------


def test_bootstrap_resolver_requires_a_recognized_bearer_credential():
    resolver = BootstrapTokenResolver(TOKENS)
    assert resolver.resolve(f"Bearer {OWNER_TOKEN}").subject == "owner@example.test"
    for credential in (None, "", "Basic abc", "Bearer wrong-token"):
        with pytest.raises(IdentityError):
            resolver.resolve(credential)
    with pytest.raises(IdentityError):
        BootstrapTokenResolver({})
    from_environment = BootstrapTokenResolver.from_environment(
        {"CMG_SYNC_BOOTSTRAP_TOKENS": "t1=a@example.test, t2=b@example.test,broken"}
    )
    assert from_environment.resolve("Bearer t2").subject == "b@example.test"


def test_unauthenticated_requests_are_rejected(client: TestClient):
    assert client.get("/sync/v1/workspaces").status_code == 401
    assert client.get(
        "/sync/v1/workspaces", headers={"Authorization": "Bearer no"}
    ).status_code == (401)


def test_health_reports_limits_without_tenant_detail(client: TestClient):
    payload = client.get("/sync/v1/health").json()
    assert payload["status"] == "ok"
    assert payload["database"] == ("postgresql" if POSTGRES_URL else "sqlite")
    assert payload["push_operation_limit"] == 500
    assert payload["push_byte_limit"] == 4 * 1024 * 1024
    assert payload["blob_chunk_bytes"] == 8 * 1024 * 1024
    assert "tenant" not in payload


# Workspaces and roles ---------------------------------------------------


def test_workspace_creation_seats_the_owner(client: TestClient):
    workspace_id = _create_workspace(client)
    listing = client.get("/sync/v1/workspaces", headers=OWNER).json()
    assert [entry["workspace_id"] for entry in listing] == [workspace_id]
    assert listing[0]["role"] == "owner"
    assert listing[0]["raw_audio_enabled"] is False
    assert client.get("/sync/v1/workspaces", headers=VIEWER).json() == []


def test_roles_gate_reads_writes_and_administration(client: TestClient):
    workspace_id = _create_workspace(client)
    _seat(client, workspace_id, "editor@example.test", "editor")
    _seat(client, workspace_id, "viewer@example.test", "viewer")
    device_id = _register_device(client, workspace_id, EDITOR)

    assert client.get(f"/sync/v1/workspaces/{workspace_id}/pull", headers=VIEWER).status_code == 200

    denied = client.post(
        f"/sync/v1/workspaces/{workspace_id}/push",
        json={"device_id": device_id, "operations": [_operation(str(uuid4()))]},
        headers=VIEWER,
    )
    assert denied.status_code == 403

    accepted = client.post(
        f"/sync/v1/workspaces/{workspace_id}/push",
        json={"device_id": device_id, "operations": [_operation(str(uuid4()))]},
        headers=EDITOR,
    )
    assert accepted.status_code == 200

    assert (
        client.put(
            f"/sync/v1/workspaces/{workspace_id}/raw-audio",
            json={"enabled": True},
            headers=EDITOR,
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/sync/v1/workspaces/{workspace_id}/members",
            json={
                "subject": "someone@example.test",
                "issuer": "urn:collective-mindgraph:bootstrap",
                "role": "viewer",
            },
            headers=EDITOR,
        ).status_code
        == 403
    )


def test_non_members_and_unknown_workspaces_are_separated(client: TestClient):
    workspace_id = _create_workspace(client)
    assert client.get(f"/sync/v1/workspaces/{workspace_id}/pull", headers=EDITOR).status_code == 403
    assert client.get(f"/sync/v1/workspaces/{uuid4()}/pull", headers=OWNER).status_code == 404


def test_removed_members_lose_access(client: TestClient):
    workspace_id = _create_workspace(client)
    _seat(client, workspace_id, "viewer@example.test", "viewer")
    assert client.get(f"/sync/v1/workspaces/{workspace_id}/pull", headers=VIEWER).status_code == 200
    removed = client.request(
        "DELETE",
        f"/sync/v1/workspaces/{workspace_id}/members/viewer@example.test",
        json={"issuer": "urn:collective-mindgraph:bootstrap"},
        headers=OWNER,
    )
    assert removed.status_code == 204
    assert client.get(f"/sync/v1/workspaces/{workspace_id}/pull", headers=VIEWER).status_code == 403


# Push and pull ----------------------------------------------------------


def test_push_is_idempotent_and_conflicts_are_reported(client: TestClient):
    workspace_id = _create_workspace(client)
    device_id = _register_device(client, workspace_id, OWNER)
    object_id = str(uuid4())
    operation = _operation(object_id)

    first = client.post(
        f"/sync/v1/workspaces/{workspace_id}/push",
        json={"device_id": device_id, "operations": [operation]},
        headers=OWNER,
    ).json()
    assert first["results"][0]["outcome"] == OperationOutcome.APPLIED.value
    assert first["results"][0]["revision"] == 1

    replayed = client.post(
        f"/sync/v1/workspaces/{workspace_id}/push",
        json={"device_id": device_id, "operations": [operation]},
        headers=OWNER,
    ).json()
    assert replayed["results"][0]["outcome"] == OperationOutcome.DUPLICATE.value
    assert replayed["results"][0]["revision"] == 1

    stale = client.post(
        f"/sync/v1/workspaces/{workspace_id}/push",
        json={"device_id": device_id, "operations": [_operation(object_id, base_revision=0)]},
        headers=OWNER,
    ).json()
    assert stale["results"][0]["outcome"] == OperationOutcome.CONFLICT.value
    assert stale["results"][0]["server_revision"] == 1

    page = client.get(f"/sync/v1/workspaces/{workspace_id}/pull", headers=OWNER).json()
    assert len(page["records"]) == 1
    assert page["records"][0]["revision"] == 1
    assert page["records"][0]["ciphertext"] == b64encode(b"sealed-payload").decode("ascii")
    assert page["records"][0]["ciphertext_sha256"] == hashlib.sha256(b"sealed-payload").hexdigest()


def test_conflict_replay_returns_the_same_conflict(client: TestClient):
    workspace_id = _create_workspace(client)
    device_id = _register_device(client, workspace_id, OWNER)
    object_id = str(uuid4())
    client.post(
        f"/sync/v1/workspaces/{workspace_id}/push",
        json={"device_id": device_id, "operations": [_operation(object_id)]},
        headers=OWNER,
    )
    stale = _operation(object_id, base_revision=0)
    first = client.post(
        f"/sync/v1/workspaces/{workspace_id}/push",
        json={"device_id": device_id, "operations": [stale]},
        headers=OWNER,
    ).json()
    second = client.post(
        f"/sync/v1/workspaces/{workspace_id}/push",
        json={"device_id": device_id, "operations": [stale]},
        headers=OWNER,
    ).json()
    assert first["results"][0] == second["results"][0]


def test_pull_pages_in_server_order_and_advances_the_cursor(client: TestClient):
    workspace_id = _create_workspace(client)
    device_id = _register_device(client, workspace_id, OWNER)
    object_ids = [str(uuid4()) for _ in range(5)]
    for object_id in object_ids:
        client.post(
            f"/sync/v1/workspaces/{workspace_id}/push",
            json={"device_id": device_id, "operations": [_operation(object_id)]},
            headers=OWNER,
        )

    first = client.get(
        f"/sync/v1/workspaces/{workspace_id}/pull",
        params={"cursor": "0", "limit": 2},
        headers=OWNER,
    ).json()
    assert [record["object_id"] for record in first["records"]] == object_ids[:2]
    assert first["has_more"] is True

    second = client.get(
        f"/sync/v1/workspaces/{workspace_id}/pull",
        params={"cursor": first["cursor"], "limit": 10},
        headers=OWNER,
    ).json()
    assert [record["object_id"] for record in second["records"]] == object_ids[2:]
    assert second["has_more"] is False

    drained = client.get(
        f"/sync/v1/workspaces/{workspace_id}/pull",
        params={"cursor": second["cursor"]},
        headers=OWNER,
    ).json()
    assert drained["records"] == []
    assert drained["cursor"] == second["cursor"]


def test_deletions_clear_ciphertext_but_keep_the_tombstone(client: TestClient):
    workspace_id = _create_workspace(client)
    device_id = _register_device(client, workspace_id, OWNER)
    object_id = str(uuid4())
    client.post(
        f"/sync/v1/workspaces/{workspace_id}/push",
        json={"device_id": device_id, "operations": [_operation(object_id)]},
        headers=OWNER,
    )
    removed = client.post(
        f"/sync/v1/workspaces/{workspace_id}/push",
        json={
            "device_id": device_id,
            "operations": [_operation(object_id, base_revision=1, deleted=True)],
        },
        headers=OWNER,
    ).json()
    assert removed["results"][0]["outcome"] == OperationOutcome.APPLIED.value

    page = client.get(f"/sync/v1/workspaces/{workspace_id}/pull", headers=OWNER).json()
    assert page["records"][0]["deleted"] is True
    assert page["records"][0]["ciphertext"] is None
    assert page["records"][0]["nonce"] is None


def test_push_batches_respect_the_configured_limits(tmp_path: Path):
    app = create_sync_app(
        _settings(tmp_path, push_operation_limit=2, push_byte_limit=64),
        identities=BootstrapTokenResolver(TOKENS),
        blob_store=FilesystemBlobStore(tmp_path / "blobs"),
        create_schema=True,
    )
    with TestClient(app) as client:
        workspace_id = _create_workspace(client)
        device_id = _register_device(client, workspace_id, OWNER)
        too_many = client.post(
            f"/sync/v1/workspaces/{workspace_id}/push",
            json={
                "device_id": device_id,
                "operations": [_operation(str(uuid4())) for _ in range(3)],
            },
            headers=OWNER,
        )
        assert too_many.status_code == 413

        too_large = client.post(
            f"/sync/v1/workspaces/{workspace_id}/push",
            json={
                "device_id": device_id,
                "operations": [_operation(str(uuid4()), ciphertext=b"x" * 128)],
            },
            headers=OWNER,
        )
        assert too_large.status_code == 413

        duplicate_id = str(uuid4())
        repeated = client.post(
            f"/sync/v1/workspaces/{workspace_id}/push",
            json={
                "device_id": device_id,
                "operations": [
                    _operation(str(uuid4()), operation_id=duplicate_id),
                    _operation(str(uuid4()), operation_id=duplicate_id),
                ],
            },
            headers=OWNER,
        )
        assert repeated.status_code == 413


def test_operation_input_rejects_malformed_payloads():
    now = datetime.now(tz=UTC)
    with pytest.raises(ValueError):
        SyncOperationInput(
            operation_id="a",
            object_id="b",
            object_type="transcript",
            base_revision=-1,
            key_version=1,
            client_timestamp=now,
            ciphertext=b"x",
            nonce=b"y",
        )
    with pytest.raises(ValueError):
        SyncOperationInput(
            operation_id="a",
            object_id="b",
            object_type=" ",
            base_revision=0,
            key_version=1,
            client_timestamp=now,
            ciphertext=b"x",
            nonce=b"y",
        )
    with pytest.raises(ValueError):
        SyncOperationInput(
            operation_id="a",
            object_id="b",
            object_type="transcript",
            base_revision=0,
            key_version=0,
            client_timestamp=now,
            ciphertext=b"x",
            nonce=b"y",
        )
    with pytest.raises(ValueError):
        SyncOperationInput(
            operation_id="a",
            object_id="b",
            object_type="transcript",
            base_revision=0,
            key_version=1,
            client_timestamp=datetime(2026, 1, 1),
            ciphertext=b"x",
            nonce=b"y",
        )
    with pytest.raises(ValueError):
        SyncOperationInput(
            operation_id="a",
            object_id="b",
            object_type="transcript",
            base_revision=0,
            key_version=1,
            client_timestamp=now,
        )
    with pytest.raises(ValueError):
        SyncOperationInput(
            operation_id="a",
            object_id="b",
            object_type="transcript",
            base_revision=0,
            key_version=1,
            client_timestamp=now,
            ciphertext=b"x",
            deleted=True,
        )


def test_pull_rejects_a_malformed_cursor(client: TestClient):
    workspace_id = _create_workspace(client)
    with pytest.raises(ValueError):
        client.get(
            f"/sync/v1/workspaces/{workspace_id}/pull",
            params={"cursor": "not-a-cursor"},
            headers=OWNER,
        )


# Devices ----------------------------------------------------------------


def test_revoked_devices_cannot_push_and_lose_their_envelopes(client: TestClient):
    workspace_id = _create_workspace(client)
    device_id = _register_device(client, workspace_id, OWNER)
    stored = client.post(
        f"/sync/v1/workspaces/{workspace_id}/envelopes",
        json={
            "key_version": 1,
            "wrapped_key": b64encode(b"wrapped-material").decode("ascii"),
            "recipient_device_id": device_id,
            "ephemeral_public_key": b64encode(bytes(32)).decode("ascii"),
            "salt": b64encode(bytes(32)).decode("ascii"),
        },
        headers=OWNER,
    )
    assert stored.status_code == 201

    listed = client.get(
        f"/sync/v1/workspaces/{workspace_id}/devices/{device_id}/envelopes",
        headers=OWNER,
    ).json()
    assert len(listed) == 1
    assert listed[0]["wrapped_key"] == b64encode(b"wrapped-material").decode("ascii")

    revoked = client.delete(
        f"/sync/v1/workspaces/{workspace_id}/devices/{device_id}",
        headers=OWNER,
    )
    assert revoked.status_code == 204

    assert (
        client.get(
            f"/sync/v1/workspaces/{workspace_id}/devices/{device_id}/envelopes",
            headers=OWNER,
        ).json()
        == []
    )
    denied = client.post(
        f"/sync/v1/workspaces/{workspace_id}/push",
        json={"device_id": device_id, "operations": [_operation(str(uuid4()))]},
        headers=OWNER,
    )
    assert denied.status_code == 403


def test_unknown_and_foreign_devices_cannot_push(client: TestClient):
    workspace_id = _create_workspace(client)
    _seat(client, workspace_id, "editor@example.test", "editor")
    other_workspace = _create_workspace(client, name="Other")
    foreign_device = _register_device(client, other_workspace, OWNER)

    unknown = client.post(
        f"/sync/v1/workspaces/{workspace_id}/push",
        json={"device_id": str(uuid4()), "operations": [_operation(str(uuid4()))]},
        headers=OWNER,
    )
    assert unknown.status_code == 403

    foreign = client.post(
        f"/sync/v1/workspaces/{workspace_id}/push",
        json={"device_id": foreign_device, "operations": [_operation(str(uuid4()))]},
        headers=OWNER,
    )
    assert foreign.status_code == 403

    editor_device = _register_device(client, workspace_id, EDITOR)
    borrowed = client.post(
        f"/sync/v1/workspaces/{workspace_id}/push",
        json={"device_id": editor_device, "operations": [_operation(str(uuid4()))]},
        headers=OWNER,
    )
    assert borrowed.status_code == 403


def test_device_public_keys_must_be_thirty_two_bytes(client: TestClient):
    workspace_id = _create_workspace(client)
    with pytest.raises(ValueError):
        client.post(
            f"/sync/v1/workspaces/{workspace_id}/devices",
            json={
                "device_id": str(uuid4()),
                "name": "Laptop",
                "public_key": b64encode(bytes(16)).decode("ascii"),
            },
            headers=OWNER,
        )


# Blobs ------------------------------------------------------------------


def test_raw_audio_blobs_require_the_workspace_opt_in(client: TestClient):
    workspace_id = _create_workspace(client)
    payload = b"c" * 1024
    rejected = client.post(
        f"/sync/v1/workspaces/{workspace_id}/blobs",
        json={"object_id": str(uuid4()), "total_chunks": 1, "sha256": digest(payload)},
        headers=OWNER,
    )
    assert rejected.status_code == 409
    assert "disabled" in rejected.json()["detail"]


def test_blob_upload_is_resumable_and_digest_verified(tmp_path: Path):
    chunk_bytes = 1024
    app = create_sync_app(
        _settings(tmp_path, blob_chunk_bytes=chunk_bytes),
        identities=BootstrapTokenResolver(TOKENS),
        blob_store=FilesystemBlobStore(tmp_path / "blobs"),
        create_schema=True,
    )
    with TestClient(app) as client:
        workspace_id = _create_workspace(client)
        client.put(
            f"/sync/v1/workspaces/{workspace_id}/raw-audio",
            json={"enabled": True},
            headers=OWNER,
        )
        first, second = b"a" * chunk_bytes, b"b" * 100
        payload = first + second
        object_id = str(uuid4())
        manifest = client.post(
            f"/sync/v1/workspaces/{workspace_id}/blobs",
            json={"object_id": object_id, "total_chunks": 2, "sha256": digest(payload)},
            headers=OWNER,
        ).json()
        assert manifest["missing_chunks"] == [0, 1]
        manifest_id = manifest["manifest_id"]

        client.put(
            f"/sync/v1/workspaces/{workspace_id}/blobs/{manifest_id}/chunks/0",
            content=first,
            headers=OWNER,
        )
        resumed = client.post(
            f"/sync/v1/workspaces/{workspace_id}/blobs",
            json={"object_id": object_id, "total_chunks": 2, "sha256": digest(payload)},
            headers=OWNER,
        ).json()
        assert resumed["missing_chunks"] == [1]
        assert resumed["manifest_id"] == manifest_id

        incomplete = client.post(
            f"/sync/v1/workspaces/{workspace_id}/blobs/{manifest_id}/complete",
            headers=OWNER,
        )
        assert incomplete.status_code == 409

        client.put(
            f"/sync/v1/workspaces/{workspace_id}/blobs/{manifest_id}/chunks/1",
            content=second,
            headers=OWNER,
        )
        completed = client.post(
            f"/sync/v1/workspaces/{workspace_id}/blobs/{manifest_id}/complete",
            headers=OWNER,
        ).json()
        assert completed["state"] == "complete"

        downloaded = client.get(
            f"/sync/v1/workspaces/{workspace_id}/blobs/{manifest_id}",
            headers=OWNER,
        )
        assert downloaded.content == payload

        usage = client.get(f"/sync/v1/workspaces/{workspace_id}/usage", headers=OWNER).json()
        assert usage["blob_bytes"] == len(payload)


def test_blob_uploads_reject_bad_chunks_and_mismatched_digests(tmp_path: Path):
    chunk_bytes = 512
    app = create_sync_app(
        _settings(tmp_path, blob_chunk_bytes=chunk_bytes),
        identities=BootstrapTokenResolver(TOKENS),
        blob_store=FilesystemBlobStore(tmp_path / "blobs"),
        create_schema=True,
    )
    with TestClient(app) as client:
        workspace_id = _create_workspace(client)
        client.put(
            f"/sync/v1/workspaces/{workspace_id}/raw-audio",
            json={"enabled": True},
            headers=OWNER,
        )
        object_id = str(uuid4())
        declared = digest(b"z" * chunk_bytes * 2)
        manifest_id = client.post(
            f"/sync/v1/workspaces/{workspace_id}/blobs",
            json={"object_id": object_id, "total_chunks": 2, "sha256": declared},
            headers=OWNER,
        ).json()["manifest_id"]
        base = f"/sync/v1/workspaces/{workspace_id}/blobs/{manifest_id}"

        assert client.put(f"{base}/chunks/5", content=b"x" * 8, headers=OWNER).status_code == 409
        assert (
            client.put(
                f"{base}/chunks/0", content=b"x" * (chunk_bytes + 1), headers=OWNER
            ).status_code
            == 409
        )
        assert client.put(f"{base}/chunks/0", content=b"x" * 8, headers=OWNER).status_code == 409
        assert client.put(f"{base}/chunks/1", content=b"", headers=OWNER).status_code == 409

        client.put(f"{base}/chunks/0", content=b"q" * chunk_bytes, headers=OWNER)
        client.put(f"{base}/chunks/1", content=b"q" * chunk_bytes, headers=OWNER)
        mismatched = client.post(f"{base}/complete", headers=OWNER)
        assert mismatched.status_code == 409
        assert "declared digest" in mismatched.json()["detail"]

        conflicting = client.post(
            f"/sync/v1/workspaces/{workspace_id}/blobs",
            json={"object_id": object_id, "total_chunks": 2, "sha256": digest(b"other")},
            headers=OWNER,
        )
        assert conflicting.status_code == 409

        assert (
            client.post(
                f"/sync/v1/workspaces/{workspace_id}/blobs",
                json={"object_id": str(uuid4()), "total_chunks": 1, "sha256": "not-a-digest" * 4},
                headers=OWNER,
            ).status_code
            == 422
        )


def test_filesystem_blob_store_confines_keys_to_its_root(tmp_path: Path):
    store = FilesystemBlobStore(tmp_path / "blobs")
    store.put("workspace/manifest/00000000.chunk", b"sealed")
    assert store.get("workspace/manifest/00000000.chunk") == b"sealed"
    with pytest.raises(ValueError):
        store.put("../escape", b"sealed")
    with pytest.raises(ValueError):
        store.get("   ")
    assert store.delete_prefix("workspace/manifest") == 1
    assert store.delete_prefix("workspace/missing") == 0


# Invalidations and retention -------------------------------------------


def test_invalidations_stream_cursor_hints_only(client: TestClient):
    workspace_id = _create_workspace(client)
    device_id = _register_device(client, workspace_id, OWNER)
    with client.websocket_connect(
        f"/sync/v1/workspaces/{workspace_id}/invalidations",
        headers=OWNER,
    ) as socket:
        client.post(
            f"/sync/v1/workspaces/{workspace_id}/push",
            json={"device_id": device_id, "operations": [_operation(str(uuid4()))]},
            headers=OWNER,
        )
        message = socket.receive_json()
    assert message == {"workspace_id": workspace_id, "cursor": "1"}
    assert set(message) == {"workspace_id", "cursor"}


def test_invalidations_reject_unauthorized_subscribers(client: TestClient):
    workspace_id = _create_workspace(client)
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/sync/v1/workspaces/{workspace_id}/invalidations",
            headers=EDITOR,
        ) as socket:
            socket.receive_json()


@pytest.mark.asyncio
async def test_broadcaster_skips_saturated_subscribers():
    broadcaster = CursorBroadcaster()
    assert await broadcaster.publish("absent", "1") == 0
    async with broadcaster.subscribe("workspace") as queue:
        assert broadcaster.subscriber_count == 1
        for index in range(40):
            await broadcaster.publish("workspace", str(index))
        assert queue.qsize() == 32
    assert broadcaster.subscriber_count == 0


@pytest.mark.asyncio
async def test_retention_purges_only_expired_records(tmp_path: Path):
    from collective_mindgraph.sync_server.blob_storage import FilesystemBlobStore as Store
    from collective_mindgraph.sync_server.database import SyncDatabase
    from collective_mindgraph.sync_server.principals import BootstrapTokenResolver as Resolver
    from collective_mindgraph.sync_server.service import SyncService

    settings = _settings(tmp_path)
    database = SyncDatabase(settings)
    await database.create_schema()
    service = SyncService(
        settings=settings,
        database=database,
        identities=Resolver(TOKENS),
        blob_store=Store(tmp_path / "blobs"),
    )
    try:
        principal = await service.principal(f"Bearer {OWNER_TOKEN}")
        summary = await service.create_workspace(principal, name="Retention")
        async with database.begin() as connection:
            await service.members.register_device(
                connection,
                workspace_id=summary.workspace_id,
                principal=principal,
                device_id="device-1",
                name="Laptop",
                public_key=bytes(32),
                trust="trusted",
            )
        object_id = str(uuid4())
        await service.push(
            principal,
            workspace_id=summary.workspace_id,
            device_id="device-1",
            operations=[
                SyncOperationInput(
                    operation_id=str(uuid4()),
                    object_id=object_id,
                    object_type="transcript",
                    base_revision=0,
                    key_version=1,
                    client_timestamp=datetime.now(tz=UTC),
                    ciphertext=b"sealed",
                    nonce=bytes(12),
                )
            ],
        )
        await service.push(
            principal,
            workspace_id=summary.workspace_id,
            device_id="device-1",
            operations=[
                SyncOperationInput(
                    operation_id=str(uuid4()),
                    object_id=object_id,
                    object_type="transcript",
                    base_revision=1,
                    key_version=1,
                    client_timestamp=datetime.now(tz=UTC),
                    deleted=True,
                )
            ],
        )

        untouched = await service.purge_expired()
        assert untouched["objects"] == 0
        assert untouched["audit_events"] == 0

        later = datetime.now(tz=UTC) + timedelta(days=settings.content_retention_days + 1)
        purged = await service.purge_expired(now=later)
        assert purged["objects"] == 1

        much_later = datetime.now(tz=UTC) + timedelta(days=settings.audit_retention_days + 1)
        audit_purged = await service.purge_expired(now=much_later)
        assert audit_purged["audit_events"] >= 1
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_push_requires_an_initialized_cursor_sequence(tmp_path: Path):
    from sqlalchemy import delete

    from collective_mindgraph.sync_server.blob_storage import FilesystemBlobStore as Store
    from collective_mindgraph.sync_server.contracts import WorkspaceNotFoundError
    from collective_mindgraph.sync_server.database import SyncDatabase
    from collective_mindgraph.sync_server.principals import BootstrapTokenResolver as Resolver
    from collective_mindgraph.sync_server.service import SyncService
    from collective_mindgraph.sync_server.tables import workspace_cursors

    settings = _settings(tmp_path)
    database = SyncDatabase(settings)
    await database.create_schema()
    service = SyncService(
        settings=settings,
        database=database,
        identities=Resolver(TOKENS),
        blob_store=Store(tmp_path / "blobs"),
    )
    try:
        principal = await service.principal(f"Bearer {OWNER_TOKEN}")
        summary = await service.create_workspace(principal, name="Cursorless")
        async with database.begin() as connection:
            await service.members.register_device(
                connection,
                workspace_id=summary.workspace_id,
                principal=principal,
                device_id="device-1",
                name="Laptop",
                public_key=bytes(32),
                trust="trusted",
            )
            await connection.execute(
                delete(workspace_cursors).where(
                    workspace_cursors.c.workspace_id == summary.workspace_id
                )
            )
        with pytest.raises(WorkspaceNotFoundError):
            await service.push(
                principal,
                workspace_id=summary.workspace_id,
                device_id="device-1",
                operations=[
                    SyncOperationInput(
                        operation_id=str(uuid4()),
                        object_id=str(uuid4()),
                        object_type="transcript",
                        base_revision=0,
                        key_version=1,
                        client_timestamp=datetime.now(tz=UTC),
                        ciphertext=b"sealed",
                        nonce=bytes(12),
                    )
                ],
            )
    finally:
        await database.dispose()


def test_empty_push_batches_are_rejected(client: TestClient):
    workspace_id = _create_workspace(client)
    device_id = _register_device(client, workspace_id, OWNER)
    response = client.post(
        f"/sync/v1/workspaces/{workspace_id}/push",
        json={"device_id": device_id, "operations": []},
        headers=OWNER,
    )
    assert response.status_code == 422


def test_role_capabilities_are_explicit():
    assert Role.OWNER.may_administer and Role.ADMIN.may_administer
    assert not Role.EDITOR.may_administer
    assert Role.EDITOR.may_write_content and not Role.REVIEWER.may_write_content
    assert Role.REVIEWER.may_review and not Role.VIEWER.may_review
