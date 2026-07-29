"""Repository-level tests that exercise the service without HTTP.

The HTTP module covers the wire contract. These tests drive the same code on
the test's own event loop so that branch behaviour is asserted, and measured,
directly.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, update

from collective_mindgraph.sync_server.blob_storage import FilesystemBlobStore, digest
from collective_mindgraph.sync_server.contracts import (
    AccessDeniedError,
    BlobRejectedError,
    OperationOutcome,
    Principal,
    PushLimitExceededError,
    Role,
    SyncOperationInput,
    WorkspaceNotFoundError,
)
from collective_mindgraph.sync_server.database import SyncDatabase
from collective_mindgraph.sync_server.principals import BootstrapTokenResolver
from collective_mindgraph.sync_server.service import SyncService
from collective_mindgraph.sync_server.settings import SyncServerSettings
from collective_mindgraph.sync_server.tables import blob_manifests, devices, key_envelopes

TOKENS = {
    "owner-token": "owner@example.test",
    "member-token": "member@example.test",
}
CHUNK_BYTES = 256


def _settings(tmp_path: Path, **overrides: object) -> SyncServerSettings:
    configured = os.environ.get("CMG_SYNC_TEST_DATABASE_URL", "").strip()
    values: dict[str, object] = {
        "database_url": configured or f"sqlite+aiosqlite:///{(tmp_path / 'a.sqlite3').as_posix()}",
        "blob_root": tmp_path / "blobs",
        "blob_chunk_bytes": CHUNK_BYTES,
    }
    values.update(overrides)
    return SyncServerSettings(**values)  # type: ignore[arg-type]


@pytest_asyncio.fixture()
async def service(tmp_path: Path) -> AsyncIterator[SyncService]:
    settings = _settings(tmp_path)
    database = SyncDatabase(settings)
    if os.environ.get("CMG_SYNC_TEST_DATABASE_URL", "").strip():
        from collective_mindgraph.sync_server.tables import METADATA

        async with database.engine.begin() as connection:
            await connection.run_sync(METADATA.drop_all)
    await database.create_schema()
    built = SyncService(
        settings=settings,
        database=database,
        identities=BootstrapTokenResolver(TOKENS),
        blob_store=FilesystemBlobStore(tmp_path / "blobs"),
    )
    try:
        yield built
    finally:
        await database.dispose()


async def _owner(service: SyncService) -> Principal:
    return await service.principal("Bearer owner-token")


async def _member(service: SyncService) -> Principal:
    return await service.principal("Bearer member-token")


async def _workspace(service: SyncService, owner: Principal, name: str = "Team") -> str:
    summary = await service.create_workspace(owner, name=name)
    return summary.workspace_id


async def _device(service: SyncService, owner: Principal, workspace_id: str) -> str:
    device_id = str(uuid4())
    await service.devices.register(
        owner,
        workspace_id=workspace_id,
        device_id=device_id,
        name="Laptop",
        public_key=bytes(32),
    )
    return device_id


def _operation(
    object_id: str,
    *,
    base_revision: int = 0,
    ciphertext: bytes | None = b"sealed",
    deleted: bool = False,
    operation_id: str | None = None,
) -> SyncOperationInput:
    return SyncOperationInput(
        operation_id=operation_id or str(uuid4()),
        object_id=object_id,
        object_type="transcript",
        base_revision=base_revision,
        key_version=1,
        client_timestamp=datetime.now(tz=UTC),
        ciphertext=None if deleted else ciphertext,
        nonce=None if deleted else bytes(12),
        deleted=deleted,
    )


# Identity and membership ------------------------------------------------


@pytest.mark.asyncio
async def test_principals_are_stable_and_share_one_default_tenant(service: SyncService):
    first = await _owner(service)
    again = await _owner(service)
    other = await _member(service)
    assert first == again
    assert other.user_id != first.user_id
    assert other.tenant_id == first.tenant_id


@pytest.mark.asyncio
async def test_role_checks_cover_every_rank(service: SyncService):
    owner = await _owner(service)
    member = await _member(service)
    workspace_id = await _workspace(service, owner)

    async with service.database.begin() as connection:
        assert (
            await service.members.require_role(
                connection,
                workspace_id=workspace_id,
                principal=owner,
                minimum=Role.OWNER,
            )
            is Role.OWNER
        )
        with pytest.raises(AccessDeniedError):
            await service.members.require_role(
                connection,
                workspace_id=workspace_id,
                principal=member,
                minimum=Role.VIEWER,
            )
        with pytest.raises(WorkspaceNotFoundError):
            await service.members.require_role(
                connection,
                workspace_id=str(uuid4()),
                principal=owner,
                minimum=Role.VIEWER,
            )
        await service.members.upsert_membership(
            connection,
            workspace_id=workspace_id,
            user_id=member.user_id,
            role=Role.REVIEWER,
        )
        assert (
            await service.members.require_role(
                connection,
                workspace_id=workspace_id,
                principal=member,
                minimum=Role.REVIEWER,
            )
            is Role.REVIEWER
        )
        with pytest.raises(AccessDeniedError):
            await service.members.require_role(
                connection,
                workspace_id=workspace_id,
                principal=member,
                minimum=Role.EDITOR,
            )
        # Re-seating an existing member changes the role in place.
        await service.members.upsert_membership(
            connection,
            workspace_id=workspace_id,
            user_id=member.user_id,
            role=Role.ADMIN,
        )
        assert (
            await service.members.require_role(
                connection,
                workspace_id=workspace_id,
                principal=member,
                minimum=Role.ADMIN,
            )
            is Role.ADMIN
        )
        await service.members.remove_membership(
            connection,
            workspace_id=workspace_id,
            user_id=member.user_id,
        )
        with pytest.raises(AccessDeniedError):
            await service.members.require_role(
                connection,
                workspace_id=workspace_id,
                principal=member,
                minimum=Role.VIEWER,
            )


@pytest.mark.asyncio
async def test_deleted_workspaces_disappear_from_listings(service: SyncService):
    owner = await _owner(service)
    workspace_id = await _workspace(service, owner)
    assert [entry.workspace_id for entry in await service.list_workspaces(owner)] == [workspace_id]
    async with service.database.begin() as connection:
        from collective_mindgraph.sync_server.tables import workspaces

        await connection.execute(
            update(workspaces)
            .where(workspaces.c.id == workspace_id)
            .values(deleted_at=datetime.now(tz=UTC))
        )
    assert await service.list_workspaces(owner) == ()


# Devices and envelopes --------------------------------------------------


@pytest.mark.asyncio
async def test_device_registration_updates_in_place(service: SyncService):
    owner = await _owner(service)
    workspace_id = await _workspace(service, owner)
    device_id = await _device(service, owner, workspace_id)
    await service.devices.register(
        owner,
        workspace_id=workspace_id,
        device_id=device_id,
        name="Renamed",
        public_key=bytes(range(32)),
    )
    async with service.database.begin() as connection:
        rows = (await connection.execute(select(devices))).fetchall()
    assert len(rows) == 1
    assert str(rows[0].name) == "Renamed"
    assert bytes(rows[0].public_key) == bytes(range(32))


@pytest.mark.asyncio
async def test_device_authorization_rejects_unknown_foreign_and_revoked(service: SyncService):
    owner = await _owner(service)
    workspace_id = await _workspace(service, owner)
    other_id = await _workspace(service, owner, name="Other")
    device_id = await _device(service, owner, workspace_id)
    foreign_id = await _device(service, owner, other_id)

    async with service.database.begin() as connection:
        await service.members.authorize_device(
            connection,
            workspace_id=workspace_id,
            principal=owner,
            device_id=device_id,
        )
        with pytest.raises(AccessDeniedError):
            await service.members.authorize_device(
                connection,
                workspace_id=workspace_id,
                principal=owner,
                device_id=str(uuid4()),
            )
        with pytest.raises(AccessDeniedError):
            await service.members.authorize_device(
                connection,
                workspace_id=workspace_id,
                principal=owner,
                device_id=foreign_id,
            )
    await service.devices.revoke(owner, workspace_id=workspace_id, device_id=device_id)
    async with service.database.begin() as connection:
        with pytest.raises(AccessDeniedError):
            await service.members.authorize_device(
                connection,
                workspace_id=workspace_id,
                principal=owner,
                device_id=device_id,
            )


@pytest.mark.asyncio
async def test_envelopes_replace_per_recipient_and_version(service: SyncService):
    owner = await _owner(service)
    workspace_id = await _workspace(service, owner)
    device_id = await _device(service, owner, workspace_id)

    await service.devices.store_envelope(
        owner,
        workspace_id=workspace_id,
        key_version=1,
        wrapped_key=b"first",
        recipient_device_id=device_id,
        ephemeral_public_key=bytes(32),
        salt=bytes(32),
    )
    await service.devices.store_envelope(
        owner,
        workspace_id=workspace_id,
        key_version=1,
        wrapped_key=b"second",
        recipient_device_id=device_id,
        ephemeral_public_key=bytes(32),
        salt=bytes(32),
    )
    await service.devices.store_envelope(
        owner,
        workspace_id=workspace_id,
        key_version=1,
        wrapped_key=b"recovery",
        recipient_device_id=None,
        ephemeral_public_key=None,
        salt=bytes(16),
    )
    await service.devices.store_envelope(
        owner,
        workspace_id=workspace_id,
        key_version=2,
        wrapped_key=b"rotated",
        recipient_device_id=device_id,
        ephemeral_public_key=bytes(32),
        salt=bytes(32),
    )

    envelopes = await service.devices.envelopes_for(
        owner,
        workspace_id=workspace_id,
        device_id=device_id,
    )
    assert [bytes(row.wrapped_key) for row in envelopes] == [b"second", b"rotated"]

    async with service.database.begin() as connection:
        recovery = (
            await connection.execute(
                select(key_envelopes).where(key_envelopes.c.recipient_device_id.is_(None))
            )
        ).fetchall()
    assert len(recovery) == 1
    assert bytes(recovery[0].wrapped_key) == b"recovery"


# Synchronization --------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_limits_and_duplicate_identifiers_are_rejected(service: SyncService):
    owner = await _owner(service)
    workspace_id = await _workspace(service, owner)
    device_id = await _device(service, owner, workspace_id)

    async def _push(operations: list[SyncOperationInput]) -> None:
        await service.push(
            owner,
            workspace_id=workspace_id,
            device_id=device_id,
            operations=operations,
        )

    with pytest.raises(PushLimitExceededError):
        await _push([])
    duplicate = str(uuid4())
    with pytest.raises(PushLimitExceededError):
        await _push(
            [
                _operation(str(uuid4()), operation_id=duplicate),
                _operation(str(uuid4()), operation_id=duplicate),
            ]
        )


@pytest.mark.asyncio
async def test_pull_rejects_malformed_cursors(service: SyncService):
    owner = await _owner(service)
    workspace_id = await _workspace(service, owner)
    for cursor in ("not-a-cursor", "-1"):
        with pytest.raises(ValueError):
            await service.pull(owner, workspace_id=workspace_id, cursor=cursor)


@pytest.mark.asyncio
async def test_usage_counters_follow_content_and_deletion(service: SyncService):
    owner = await _owner(service)
    workspace_id = await _workspace(service, owner)
    device_id = await _device(service, owner, workspace_id)
    assert await service.usage(owner, workspace_id=workspace_id) == {
        "object_count": 0,
        "ciphertext_bytes": 0,
        "blob_bytes": 0,
    }

    object_id = str(uuid4())
    await service.push(
        owner,
        workspace_id=workspace_id,
        device_id=device_id,
        operations=[_operation(object_id, ciphertext=b"x" * 40)],
    )
    assert await service.usage(owner, workspace_id=workspace_id) == {
        "object_count": 1,
        "ciphertext_bytes": 40,
        "blob_bytes": 0,
    }

    await service.push(
        owner,
        workspace_id=workspace_id,
        device_id=device_id,
        operations=[_operation(object_id, base_revision=1, deleted=True)],
    )
    after_delete = await service.usage(owner, workspace_id=workspace_id)
    assert after_delete["object_count"] == 0


@pytest.mark.asyncio
async def test_batches_apply_atomically_across_mixed_outcomes(service: SyncService):
    owner = await _owner(service)
    workspace_id = await _workspace(service, owner)
    device_id = await _device(service, owner, workspace_id)
    first, second = str(uuid4()), str(uuid4())
    await service.push(
        owner,
        workspace_id=workspace_id,
        device_id=device_id,
        operations=[_operation(first)],
    )
    result = await service.push(
        owner,
        workspace_id=workspace_id,
        device_id=device_id,
        operations=[_operation(first), _operation(second)],
    )
    outcomes = {entry.object_id: entry.outcome for entry in result.results}
    assert outcomes[first] is OperationOutcome.CONFLICT
    assert outcomes[second] is OperationOutcome.APPLIED
    assert len(result.conflicts) == 1
    # The accepted half is still durable and visible.
    page = await service.pull(owner, workspace_id=workspace_id, cursor="0")
    assert {record.object_id for record in page.records} == {first, second}


# Blobs ------------------------------------------------------------------


async def _enable_raw_audio(service: SyncService, owner: Principal, workspace_id: str) -> None:
    await service.set_raw_audio(owner, workspace_id=workspace_id, enabled=True)


@pytest.mark.asyncio
async def test_blob_lifecycle_from_initiate_to_retention(service: SyncService, tmp_path: Path):
    owner = await _owner(service)
    workspace_id = await _workspace(service, owner)
    await _enable_raw_audio(service, owner, workspace_id)

    first, second = b"a" * CHUNK_BYTES, b"b" * 32
    payload = first + second
    object_id = str(uuid4())
    manifest = await service.blobs.initiate(
        owner,
        workspace_id=workspace_id,
        object_id=object_id,
        total_chunks=2,
        sha256=digest(payload),
    )
    assert manifest.missing_chunks == (0, 1)

    with pytest.raises(BlobRejectedError):
        await service.blobs.complete(owner, workspace_id=workspace_id, manifest_id=manifest.id)

    await service.blobs.upload_chunk(
        owner,
        workspace_id=workspace_id,
        manifest_id=manifest.id,
        chunk_index=0,
        payload=first,
    )
    resumed = await service.blobs.initiate(
        owner,
        workspace_id=workspace_id,
        object_id=object_id,
        total_chunks=2,
        sha256=digest(payload),
    )
    assert resumed.id == manifest.id
    assert resumed.missing_chunks == (1,)

    # Re-uploading a chunk replaces it rather than duplicating the record.
    await service.blobs.upload_chunk(
        owner,
        workspace_id=workspace_id,
        manifest_id=manifest.id,
        chunk_index=0,
        payload=first,
    )
    await service.blobs.upload_chunk(
        owner,
        workspace_id=workspace_id,
        manifest_id=manifest.id,
        chunk_index=1,
        payload=second,
    )
    completed = await service.blobs.complete(
        owner,
        workspace_id=workspace_id,
        manifest_id=manifest.id,
    )
    assert completed.state == "complete"
    assert (
        await service.blobs.read(owner, workspace_id=workspace_id, manifest_id=manifest.id)
    ) == payload
    assert await service.usage(owner, workspace_id=workspace_id) == {
        "object_count": 0,
        "ciphertext_bytes": 0,
        "blob_bytes": len(payload),
    }

    with pytest.raises(BlobRejectedError):
        await service.blobs.initiate(
            owner,
            workspace_id=workspace_id,
            object_id=object_id,
            total_chunks=2,
            sha256=digest(payload),
        )
    with pytest.raises(BlobRejectedError):
        await service.blobs.upload_chunk(
            owner,
            workspace_id=workspace_id,
            manifest_id=manifest.id,
            chunk_index=0,
            payload=first,
        )

    async with service.database.begin() as connection:
        await service.blobs._blobs.mark_deleted(connection, manifest_id=manifest.id)
    assert (await service.purge_expired())["blobs"] == 0
    later = datetime.now(tz=UTC) + timedelta(days=service.settings.content_retention_days + 1)
    assert (await service.purge_expired(now=later))["blobs"] == 1
    assert not list((tmp_path / "blobs" / workspace_id).glob("**/*.chunk"))


@pytest.mark.asyncio
async def test_blob_initiation_validates_its_declaration(service: SyncService):
    owner = await _owner(service)
    workspace_id = await _workspace(service, owner)

    with pytest.raises(BlobRejectedError, match="disabled"):
        await service.blobs.initiate(
            owner,
            workspace_id=workspace_id,
            object_id=str(uuid4()),
            total_chunks=1,
            sha256=digest(b"x"),
        )
    await _enable_raw_audio(service, owner, workspace_id)

    with pytest.raises(BlobRejectedError, match="at least one chunk"):
        await service.blobs.initiate(
            owner,
            workspace_id=workspace_id,
            object_id=str(uuid4()),
            total_chunks=0,
            sha256=digest(b"x"),
        )
    with pytest.raises(BlobRejectedError, match="SHA-256"):
        await service.blobs.initiate(
            owner,
            workspace_id=workspace_id,
            object_id=str(uuid4()),
            total_chunks=1,
            sha256="z" * 64,
        )
    object_id = str(uuid4())
    await service.blobs.initiate(
        owner,
        workspace_id=workspace_id,
        object_id=object_id,
        total_chunks=1,
        sha256=digest(b"x"),
    )
    with pytest.raises(BlobRejectedError, match="different digest"):
        await service.blobs.initiate(
            owner,
            workspace_id=workspace_id,
            object_id=object_id,
            total_chunks=1,
            sha256=digest(b"y"),
        )
    with pytest.raises(BlobRejectedError, match="does not exist"):
        await service.blobs.upload_chunk(
            owner,
            workspace_id=workspace_id,
            manifest_id=str(uuid4()),
            chunk_index=0,
            payload=b"x",
        )


@pytest.mark.asyncio
async def test_blob_chunks_are_validated_and_verified(service: SyncService):
    owner = await _owner(service)
    workspace_id = await _workspace(service, owner)
    await _enable_raw_audio(service, owner, workspace_id)
    declared = digest(b"q" * CHUNK_BYTES * 2)
    manifest = await service.blobs.initiate(
        owner,
        workspace_id=workspace_id,
        object_id=str(uuid4()),
        total_chunks=2,
        sha256=declared,
    )

    async def _upload(index: int, payload: bytes) -> None:
        await service.blobs.upload_chunk(
            owner,
            workspace_id=workspace_id,
            manifest_id=manifest.id,
            chunk_index=index,
            payload=payload,
        )

    with pytest.raises(BlobRejectedError, match="outside the declared manifest"):
        await _upload(9, b"x" * CHUNK_BYTES)
    with pytest.raises(BlobRejectedError, match="exceeds the configured chunk size"):
        await _upload(0, b"x" * (CHUNK_BYTES + 1))
    with pytest.raises(BlobRejectedError, match="final chunk"):
        await _upload(0, b"x" * 8)
    with pytest.raises(BlobRejectedError, match="cannot be empty"):
        await _upload(1, b"")

    await _upload(0, b"w" * CHUNK_BYTES)
    await _upload(1, b"w" * CHUNK_BYTES)
    with pytest.raises(BlobRejectedError, match="declared digest"):
        await service.blobs.complete(owner, workspace_id=workspace_id, manifest_id=manifest.id)

    with pytest.raises(BlobRejectedError, match="not complete"):
        await service.blobs.read(owner, workspace_id=workspace_id, manifest_id=manifest.id)


@pytest.mark.asyncio
async def test_completion_detects_chunks_altered_in_storage(service: SyncService, tmp_path: Path):
    owner = await _owner(service)
    workspace_id = await _workspace(service, owner)
    await _enable_raw_audio(service, owner, workspace_id)
    payload = b"m" * CHUNK_BYTES
    manifest = await service.blobs.initiate(
        owner,
        workspace_id=workspace_id,
        object_id=str(uuid4()),
        total_chunks=1,
        sha256=digest(payload),
    )
    await service.blobs.upload_chunk(
        owner,
        workspace_id=workspace_id,
        manifest_id=manifest.id,
        chunk_index=0,
        payload=payload,
    )
    stored = next((tmp_path / "blobs" / workspace_id / manifest.id).glob("*.chunk"))
    stored.write_bytes(b"n" * CHUNK_BYTES)
    with pytest.raises(BlobRejectedError, match="no longer matches"):
        await service.blobs.complete(owner, workspace_id=workspace_id, manifest_id=manifest.id)


@pytest.mark.asyncio
async def test_blob_repository_reports_unknown_workspaces(service: SyncService):
    owner = await _owner(service)
    workspace_id = await _workspace(service, owner)
    async with service.database.begin() as connection:
        with pytest.raises(BlobRejectedError, match="does not exist"):
            await service.blobs._blobs.initiate(
                connection,
                workspace_id=str(uuid4()),
                object_id=str(uuid4()),
                total_chunks=1,
                declared_sha256=digest(b"x"),
            )
        with pytest.raises(BlobRejectedError, match="manifest does not exist"):
            await service.blobs._blobs.read(connection, manifest_id=str(uuid4()))
    assert workspace_id


@pytest.mark.asyncio
async def test_audit_records_are_written_and_purged(service: SyncService):
    owner = await _owner(service)
    await _workspace(service, owner)
    async with service.database.begin() as connection:
        from collective_mindgraph.sync_server.tables import audit_events

        kinds = [
            str(row.kind) for row in (await connection.execute(select(audit_events))).fetchall()
        ]
    assert kinds == ["workspace.created"]

    assert (await service.purge_expired())["audit_events"] == 0
    later = datetime.now(tz=UTC) + timedelta(days=service.settings.audit_retention_days + 1)
    assert (await service.purge_expired(now=later))["audit_events"] == 1


@pytest.mark.asyncio
async def test_blob_manifest_rows_carry_the_configured_chunk_size(service: SyncService):
    owner = await _owner(service)
    workspace_id = await _workspace(service, owner)
    await _enable_raw_audio(service, owner, workspace_id)
    await service.blobs.initiate(
        owner,
        workspace_id=workspace_id,
        object_id=str(uuid4()),
        total_chunks=1,
        sha256=digest(b"x"),
    )
    async with service.database.begin() as connection:
        row = (await connection.execute(select(blob_manifests))).fetchone()
    assert row is not None
    assert int(row.chunk_bytes) == CHUNK_BYTES
    assert str(row.state) == "pending"
