"""Outbox durability, agent behaviour, conflicts, backoff, and transport."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from collective_mindgraph.application.ports.sync_transport import (
    RemoteOperationResult,
    RemoteOutcome,
    RemotePullPage,
    RemotePushResult,
    RemoteRecord,
    RetryableTransportError,
    SyncTransportError,
)
from collective_mindgraph.application.sync import (
    BACKGROUND_INTERVAL_SECONDS,
    FOREGROUND_INTERVAL_SECONDS,
    SyncAgent,
)
from collective_mindgraph.application.sync.agent import ConflictNotFoundError
from collective_mindgraph.domain import (
    ConflictResolution,
    OutboxEntry,
    SyncCursor,
    SyncPhase,
)
from collective_mindgraph.domain.identifiers import (
    ConflictId,
    DeviceId,
    OperationId,
    SyncId,
    WorkspaceId,
)
from collective_mindgraph.infrastructure.persistence import (
    SqliteDatabase,
    SqliteOutboxStore,
    initialize_schema,
)
from collective_mindgraph.infrastructure.sync.http_transport import HttpSyncTransport

NOW = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
DEVICE = DeviceId(str(uuid4()))


@pytest.fixture()
def database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(tmp_path / "canonical.sqlite3")
    initialize_schema(database)
    return database


@pytest.fixture()
def store(database: SqliteDatabase) -> SqliteOutboxStore:
    return SqliteOutboxStore(database)


def _workspace(database: SqliteDatabase) -> WorkspaceId:
    with database.connect() as connection:
        row = connection.execute("SELECT id FROM workspaces WHERE is_local = 1").fetchone()
    return WorkspaceId(str(row[0]))


def _entry(
    workspace_id: WorkspaceId,
    *,
    object_id: SyncId | None = None,
    base_revision: int = 0,
    payload: bytes = b"sealed",
    deleted: bool = False,
    operation_id: OperationId | None = None,
) -> OutboxEntry:
    return OutboxEntry(
        operation_id=operation_id or OperationId(str(uuid4())),
        workspace_id=workspace_id,
        object_id=object_id or SyncId(str(uuid4())),
        object_type="transcript",
        base_revision=base_revision,
        local_revision=base_revision + 1,
        client_timestamp=NOW,
        payload=b"" if deleted else payload,
        deleted=deleted,
    )


class _Transport:
    """Records calls and returns scripted answers."""

    def __init__(
        self,
        *,
        push_results: list[RemoteOperationResult] | None = None,
        page: RemotePullPage | None = None,
        push_error: Exception | None = None,
    ) -> None:
        self.push_results = push_results or []
        self.page = page or RemotePullPage(cursor="0")
        self.push_error = push_error
        self.pushed: list[Any] = []
        self.pull_cursors: list[str] = []

    def push(self, *, workspace_id: str, device_id: str, operations: Any) -> RemotePushResult:
        if self.push_error is not None:
            raise self.push_error
        self.pushed.append(list(operations))
        return RemotePushResult(cursor="7", results=tuple(self.push_results))

    def pull(self, *, workspace_id: str, cursor: str, limit: int | None = None) -> RemotePullPage:
        self.pull_cursors.append(cursor)
        return self.page


def _agent(store: SqliteOutboxStore, transport: _Transport, *, applied: list[Any] | None = None):
    sink = applied if applied is not None else []

    def _apply(page: RemotePullPage) -> int:
        sink.append(page)
        return len(page.records)

    return SyncAgent(
        outbox=store,
        transport=transport,
        apply_remote=_apply,
        clock=lambda: NOW,
    )


# Domain -------------------------------------------------------------------


def test_domain_rejects_inconsistent_sync_state():
    workspace_id = WorkspaceId(str(uuid4()))
    with pytest.raises(ValueError):
        SyncCursor(workspace_id=workspace_id, last_pushed_revision=-1)
    with pytest.raises(ValueError):
        SyncCursor(workspace_id=workspace_id, last_pull_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        _entry(workspace_id, payload=b"")
    with pytest.raises(ValueError):
        OutboxEntry(
            operation_id=OperationId(str(uuid4())),
            workspace_id=workspace_id,
            object_id=SyncId(str(uuid4())),
            object_type="transcript",
            base_revision=0,
            local_revision=1,
            client_timestamp=NOW,
            payload=b"sealed",
            deleted=True,
        )
    assert SyncCursor(workspace_id=workspace_id).is_backing_off(now=NOW) is False
    backing_off = SyncCursor(workspace_id=workspace_id, backoff_until=NOW + timedelta(minutes=1))
    assert backing_off.is_backing_off(now=NOW) is True


# Outbox durability --------------------------------------------------------


def test_outbox_survives_restart_and_stays_idempotent(
    database: SqliteDatabase,
    store: SqliteOutboxStore,
):
    workspace_id = _workspace(database)
    entry = _entry(workspace_id)
    store.enqueue(entry)
    store.enqueue(entry)
    assert store.pending_count(workspace_id) == 1

    reopened = SqliteOutboxStore(database)
    pending = reopened.pending(workspace_id, limit=10)
    assert len(pending) == 1
    assert pending[0].operation_id == entry.operation_id
    assert pending[0].payload == b"sealed"

    assert reopened.mark_pushed((entry.operation_id,)) == 1
    assert reopened.pending_count(workspace_id) == 0
    assert reopened.mark_pushed(()) == 0


def test_outbox_records_failures_and_still_returns_them(
    database: SqliteDatabase,
    store: SqliteOutboxStore,
):
    workspace_id = _workspace(database)
    entry = _entry(workspace_id)
    store.enqueue(entry)
    store.mark_failed(entry.operation_id, error="network down")
    retried = store.pending(workspace_id, limit=10)
    assert len(retried) == 1
    assert retried[0].attempt_count == 1
    assert retried[0].last_error == "network down"


def test_outbox_persists_deletions_without_a_payload(
    database: SqliteDatabase,
    store: SqliteOutboxStore,
):
    workspace_id = _workspace(database)
    store.enqueue(_entry(workspace_id, base_revision=2, deleted=True))
    stored = store.pending(workspace_id, limit=10)[0]
    assert stored.deleted is True
    assert stored.payload == b""


def test_cursor_round_trips_and_defaults(database: SqliteDatabase, store: SqliteOutboxStore):
    workspace_id = _workspace(database)
    initial = store.cursor(workspace_id)
    assert initial.remote_cursor == "0"
    assert initial.last_error is None

    store.save_cursor(
        SyncCursor(
            workspace_id=workspace_id,
            remote_cursor="42",
            last_pushed_revision=3,
            last_pull_at=NOW,
            last_push_at=NOW,
            last_error="boom",
            backoff_until=NOW + timedelta(seconds=30),
        )
    )
    restored = SqliteOutboxStore(database).cursor(workspace_id)
    assert restored.remote_cursor == "42"
    assert restored.last_pushed_revision == 3
    assert restored.last_error == "boom"
    assert restored.backoff_until == NOW + timedelta(seconds=30)


# Agent --------------------------------------------------------------------


def test_a_pass_pushes_then_pulls_and_advances_the_cursor(
    database: SqliteDatabase,
    store: SqliteOutboxStore,
):
    workspace_id = _workspace(database)
    entry = _entry(workspace_id)
    store.enqueue(entry)
    transport = _Transport(
        push_results=[
            RemoteOperationResult(
                operation_id=str(entry.operation_id),
                object_id=str(entry.object_id),
                outcome=RemoteOutcome.APPLIED,
                revision=1,
            )
        ],
        page=RemotePullPage(
            cursor="9",
            records=(
                RemoteRecord(
                    object_id=str(uuid4()),
                    object_type="insight",
                    revision=4,
                    key_version=1,
                    deleted=False,
                    server_timestamp=NOW,
                    ciphertext=b"remote",
                    nonce=bytes(12),
                ),
            ),
        ),
    )
    report = _agent(store, transport).run_once(workspace_id, device_id=DEVICE)

    assert report.pushed == 1
    assert report.pulled == 1
    assert report.cursor == "9"
    assert report.made_progress is True
    assert store.pending_count(workspace_id) == 0
    assert store.cursor(workspace_id).remote_cursor == "9"
    assert transport.pull_cursors == ["0"]


def test_duplicates_are_settled_without_counting_as_new_work(
    database: SqliteDatabase,
    store: SqliteOutboxStore,
):
    workspace_id = _workspace(database)
    entry = _entry(workspace_id)
    store.enqueue(entry)
    transport = _Transport(
        push_results=[
            RemoteOperationResult(
                operation_id=str(entry.operation_id),
                object_id=str(entry.object_id),
                outcome=RemoteOutcome.DUPLICATE,
                revision=1,
            )
        ]
    )
    report = _agent(store, transport).run_once(workspace_id, device_id=DEVICE)
    assert report.pushed == 0
    assert report.duplicates == 1
    assert store.pending_count(workspace_id) == 0


def test_a_rejected_change_becomes_a_conflict_rather_than_an_overwrite(
    database: SqliteDatabase,
    store: SqliteOutboxStore,
):
    workspace_id = _workspace(database)
    entry = _entry(workspace_id, payload=b"my version")
    store.enqueue(entry)
    transport = _Transport(
        push_results=[
            RemoteOperationResult(
                operation_id=str(entry.operation_id),
                object_id=str(entry.object_id),
                outcome=RemoteOutcome.CONFLICT,
                server_revision=5,
            )
        ]
    )
    report = _agent(store, transport).run_once(workspace_id, device_id=DEVICE)

    assert report.pushed == 0
    assert len(report.conflicts) == 1
    conflict = report.conflicts[0]
    assert conflict.remote_revision == 5
    assert conflict.local_payload == b"my version"
    assert conflict.is_open is True
    # The rejected operation leaves the queue; it now lives in the inbox.
    assert store.pending_count(workspace_id) == 0
    assert store.open_conflict_count(workspace_id) == 1


def test_status_reports_queue_conflicts_and_phase(
    database: SqliteDatabase,
    store: SqliteOutboxStore,
):
    workspace_id = _workspace(database)
    agent = _agent(store, _Transport())
    settled = agent.status(workspace_id)
    assert settled.phase is SyncPhase.IDLE
    assert settled.is_settled is True

    store.enqueue(_entry(workspace_id))
    assert agent.status(workspace_id).phase is SyncPhase.PUSHING
    assert agent.status(workspace_id).is_settled is False

    # A recorded error outranks a queue: work is waiting precisely because the
    # service could not be reached, so reporting progress would be misleading.
    store.save_cursor(SyncCursor(workspace_id=workspace_id, last_error="offline"))
    assert agent.status(workspace_id).phase is SyncPhase.OFFLINE
    assert agent.status(workspace_id).pending_operations == 1

    store.mark_pushed(tuple(entry.operation_id for entry in store.pending(workspace_id, limit=10)))
    assert agent.status(workspace_id).phase is SyncPhase.OFFLINE

    store.save_cursor(
        SyncCursor(workspace_id=workspace_id, backoff_until=NOW + timedelta(minutes=1))
    )
    assert agent.status(workspace_id).phase is SyncPhase.BACKING_OFF


def test_transient_failures_back_off_and_the_next_pass_is_skipped(
    database: SqliteDatabase,
    store: SqliteOutboxStore,
):
    workspace_id = _workspace(database)
    store.enqueue(_entry(workspace_id))
    transport = _Transport(push_error=RetryableTransportError("service unavailable"))
    agent = _agent(store, transport)

    first = agent.run_once(workspace_id, device_id=DEVICE)
    assert first.error == "service unavailable"
    cursor = store.cursor(workspace_id)
    assert cursor.backoff_until is not None
    assert cursor.backoff_until > NOW

    second = agent.run_once(workspace_id, device_id=DEVICE)
    assert second.skipped_reason is not None
    assert second.made_progress is False
    # The queued change is still there; a transient failure never drops work.
    assert store.pending_count(workspace_id) == 1


def test_a_refusal_is_surfaced_without_backing_off(
    database: SqliteDatabase,
    store: SqliteOutboxStore,
):
    workspace_id = _workspace(database)
    store.enqueue(_entry(workspace_id))
    transport = _Transport(push_error=SyncTransportError("membership removed"))
    report = _agent(store, transport).run_once(workspace_id, device_id=DEVICE)

    assert report.error == "membership removed"
    cursor = store.cursor(workspace_id)
    assert cursor.backoff_until is None
    assert cursor.last_error == "membership removed"


def test_polling_intervals_follow_activity_and_backoff(
    database: SqliteDatabase,
    store: SqliteOutboxStore,
):
    workspace_id = _workspace(database)
    agent = _agent(store, _Transport())
    assert agent.next_interval_seconds(workspace_id, foreground=True) == FOREGROUND_INTERVAL_SECONDS
    assert (
        agent.next_interval_seconds(workspace_id, foreground=False) == BACKGROUND_INTERVAL_SECONDS
    )
    store.save_cursor(
        SyncCursor(workspace_id=workspace_id, backoff_until=NOW + timedelta(seconds=45))
    )
    assert agent.next_interval_seconds(workspace_id, foreground=True) == 45.0


# Conflict resolution ------------------------------------------------------


def _open_conflict(store: SqliteOutboxStore, workspace_id: WorkspaceId):
    return store.record_conflict(
        workspace_id=workspace_id,
        object_id=SyncId(str(uuid4())),
        object_type="transcript",
        local_revision=2,
        remote_revision=5,
        local_payload=b"mine",
        remote_payload=b"theirs",
    )


def test_keeping_the_local_version_requeues_on_top_of_the_remote_revision(
    database: SqliteDatabase,
    store: SqliteOutboxStore,
):
    workspace_id = _workspace(database)
    conflict = _open_conflict(store, workspace_id)
    agent = _agent(store, _Transport())

    entry = agent.resolve(conflict.id, ConflictResolution.LOCAL)
    assert entry is not None
    assert entry.base_revision == 5
    assert entry.local_revision == 6
    assert entry.payload == b"mine"
    assert store.pending_count(workspace_id) == 1
    assert store.open_conflict_count(workspace_id) == 0


def test_keeping_the_remote_version_only_closes_the_conflict(
    database: SqliteDatabase,
    store: SqliteOutboxStore,
):
    workspace_id = _workspace(database)
    conflict = _open_conflict(store, workspace_id)
    agent = _agent(store, _Transport())

    assert agent.resolve(conflict.id, ConflictResolution.REMOTE) is None
    assert store.pending_count(workspace_id) == 0
    assert store.open_conflict_count(workspace_id) == 0
    resolved = store.get_conflict(conflict.id)
    assert resolved is not None
    assert resolved.resolution is ConflictResolution.REMOTE
    assert resolved.is_open is False


def test_a_merged_resolution_requires_the_merged_text(
    database: SqliteDatabase,
    store: SqliteOutboxStore,
):
    workspace_id = _workspace(database)
    conflict = _open_conflict(store, workspace_id)
    agent = _agent(store, _Transport())

    with pytest.raises(ValueError):
        agent.resolve(conflict.id, ConflictResolution.MERGED)
    entry = agent.resolve(conflict.id, ConflictResolution.MERGED, merged_payload=b"both")
    assert entry is not None
    assert entry.payload == b"both"


def test_resolving_an_unknown_or_settled_conflict_fails(
    database: SqliteDatabase,
    store: SqliteOutboxStore,
):
    workspace_id = _workspace(database)
    conflict = _open_conflict(store, workspace_id)
    agent = _agent(store, _Transport())
    agent.resolve(conflict.id, ConflictResolution.REMOTE)

    with pytest.raises(ConflictNotFoundError):
        agent.resolve(conflict.id, ConflictResolution.REMOTE)
    with pytest.raises(ConflictNotFoundError):
        agent.resolve(ConflictId(str(uuid4())), ConflictResolution.LOCAL)


def test_a_second_conflict_replaces_the_open_one_for_the_same_entity(
    database: SqliteDatabase,
    store: SqliteOutboxStore,
):
    workspace_id = _workspace(database)
    object_id = SyncId(str(uuid4()))
    for revision in (3, 4):
        store.record_conflict(
            workspace_id=workspace_id,
            object_id=object_id,
            object_type="transcript",
            local_revision=2,
            remote_revision=revision,
            local_payload=b"mine",
        )
    open_conflicts = store.open_conflicts(workspace_id)
    assert len(open_conflicts) == 1
    assert open_conflicts[0].remote_revision == 4


# Transport ----------------------------------------------------------------


def _transport(responses: list[tuple[int, Any]]) -> tuple[HttpSyncTransport, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    def _request(method: str, url: str, **options: Any) -> tuple[int, Any]:
        calls.append({"method": method, "url": url, **options})
        return responses.pop(0)

    return (
        HttpSyncTransport(
            "https://sync.example.test",
            access_token=lambda: "token",
            request=_request,
        ),
        calls,
    )


def test_transport_encodes_sealed_payloads_and_decodes_results():
    workspace_id = WorkspaceId(str(uuid4()))
    entry = _entry(workspace_id, payload=b"sealed-bytes")
    transport, calls = _transport(
        [
            (
                200,
                {
                    "cursor": "12",
                    "results": [
                        {
                            "operation_id": str(entry.operation_id),
                            "object_id": str(entry.object_id),
                            "outcome": "applied",
                            "revision": 1,
                        }
                    ],
                },
            )
        ]
    )
    result = transport.push(
        workspace_id=str(workspace_id),
        device_id=str(DEVICE),
        operations=[entry],
    )
    assert result.cursor == "12"
    assert result.results[0].outcome is RemoteOutcome.APPLIED
    body = calls[0]["json"]
    assert body["operations"][0]["ciphertext"] == "c2VhbGVkLWJ5dGVz"
    assert calls[0]["headers"]["Authorization"] == "Bearer token"


def test_transport_decodes_a_pull_page():
    transport, calls = _transport(
        [
            (
                200,
                {
                    "cursor": "20",
                    "has_more": True,
                    "records": [
                        {
                            "object_id": str(uuid4()),
                            "object_type": "insight",
                            "revision": 2,
                            "key_version": 1,
                            "deleted": False,
                            "server_timestamp": NOW.isoformat(),
                            "ciphertext": "c2VhbGVk",
                            "nonce": "AAAAAAAAAAAAAAAA",
                        }
                    ],
                },
            )
        ]
    )
    page = transport.pull(workspace_id=str(uuid4()), cursor="5", limit=10)
    assert page.cursor == "20"
    assert page.has_more is True
    assert page.records[0].ciphertext == b"sealed"
    assert calls[0]["params"] == {"cursor": "5", "limit": "10"}


def test_transport_separates_retryable_failures_from_refusals():
    for status in (429, 500, 503):
        transport, _ = _transport([(status, {})])
        with pytest.raises(RetryableTransportError):
            transport.pull(workspace_id=str(uuid4()), cursor="0")
    for status in (401, 403, 409):
        transport, _ = _transport([(status, {"detail": "no"})])
        with pytest.raises(SyncTransportError) as refused:
            transport.pull(workspace_id=str(uuid4()), cursor="0")
        assert not isinstance(refused.value, RetryableTransportError)


def test_transport_treats_an_unreachable_service_as_retryable():
    def _request(method: str, url: str, **options: Any) -> tuple[int, Any]:
        raise OSError("connection refused")

    transport = HttpSyncTransport(
        "https://sync.example.test",
        access_token=lambda: "token",
        request=_request,
    )
    with pytest.raises(RetryableTransportError):
        transport.pull(workspace_id=str(uuid4()), cursor="0")


def test_transport_requires_a_secure_endpoint_and_usable_responses():
    with pytest.raises(SyncTransportError):
        HttpSyncTransport("http://sync.example.test", access_token=lambda: "t")
    transport, _ = _transport([(200, "not-a-document")])
    with pytest.raises(SyncTransportError):
        transport.pull(workspace_id=str(uuid4()), cursor="0")
    transport, _ = _transport(
        [
            (
                200,
                {
                    "cursor": "1",
                    "records": [
                        {
                            "object_id": str(uuid4()),
                            "object_type": "insight",
                            "revision": 1,
                            "key_version": 1,
                            "deleted": False,
                            "server_timestamp": NOW.isoformat(),
                            "ciphertext": "not base64!",
                        }
                    ],
                },
            )
        ]
    )
    with pytest.raises(SyncTransportError):
        transport.pull(workspace_id=str(uuid4()), cursor="0")


# Localhost surface --------------------------------------------------------


def _engine(tmp_path: Path):
    from collective_mindgraph.engine.main import create_app
    from collective_mindgraph.engine.settings import EngineSettings

    root = tmp_path / "engine"
    return create_app(
        EngineSettings(
            data_dir=root / "data",
            temp_dir=root / "temp",
            database_path=root / "collective_mindgraph.sqlite3",
            asr_provider="mock",
            vad_provider="energy",
            diarizer_provider="fallback",
            embedding_provider="mock",
        )
    )


def test_v2_sync_routes_report_status_conflicts_and_resolutions(tmp_path: Path):
    from fastapi.testclient import TestClient

    application = _engine(tmp_path)
    with TestClient(application) as client:
        context = application.state.engine_context
        workspace_id = context.workspaces.local_workspace().id
        outbox = context.outbox

        # Without an agent the surface says so rather than pretending.
        assert client.get(f"/api/v2/sync/{workspace_id}/status").status_code == 503

        transport = _Transport()
        context_agent = SyncAgent(
            outbox=outbox,
            transport=transport,
            apply_remote=lambda page: len(page.records),
            clock=lambda: NOW,
        )
        object.__setattr__(context, "sync_agent", context_agent)

        outbox.enqueue(_entry(workspace_id))
        status = client.get(f"/api/v2/sync/{workspace_id}/status").json()
        assert status["pending_operations"] == 1
        assert status["phase"] == "pushing"
        assert status["is_settled"] is False
        assert status["poll_seconds"] == FOREGROUND_INTERVAL_SECONDS

        conflict = _open_conflict(outbox, workspace_id)
        listed = client.get(f"/api/v2/sync/{workspace_id}/conflicts").json()
        assert [entry["id"] for entry in listed] == [str(conflict.id)]
        assert "local_payload" not in listed[0]

        resolved = client.post(
            f"/api/v2/sync/conflicts/{conflict.id}/resolve",
            json={"resolution": "remote"},
        ).json()
        assert resolved == {"resolved": "remote", "requeued_operation_id": None}

        missing = client.post(
            f"/api/v2/sync/conflicts/{uuid4()}/resolve",
            json={"resolution": "local"},
        )
        assert missing.status_code == 404


def test_v2_run_requires_an_enrolled_device_and_reports_the_pass(tmp_path: Path):
    from fastapi.testclient import TestClient

    application = _engine(tmp_path)
    with TestClient(application) as client:
        context = application.state.engine_context
        workspace_id = context.workspaces.local_workspace().id
        transport = _Transport(page=RemotePullPage(cursor="3"))
        object.__setattr__(
            context,
            "sync_agent",
            SyncAgent(
                outbox=context.outbox,
                transport=transport,
                apply_remote=lambda page: len(page.records),
                clock=lambda: NOW,
            ),
        )
        report = client.post(f"/api/v2/sync/{workspace_id}/run").json()
        assert report["cursor"] == "3"
        assert report["pushed"] == 0
        assert report["error"] is None


def test_v2_merged_resolution_validates_its_payload(tmp_path: Path):
    from fastapi.testclient import TestClient

    application = _engine(tmp_path)
    with TestClient(application) as client:
        context = application.state.engine_context
        workspace_id = context.workspaces.local_workspace().id
        object.__setattr__(
            context,
            "sync_agent",
            SyncAgent(
                outbox=context.outbox,
                transport=_Transport(),
                apply_remote=lambda page: len(page.records),
                clock=lambda: NOW,
            ),
        )
        conflict = _open_conflict(context.outbox, workspace_id)
        bad = client.post(
            f"/api/v2/sync/conflicts/{conflict.id}/resolve",
            json={"resolution": "merged", "merged_payload": "not base64!"},
        )
        assert bad.status_code == 422
        good = client.post(
            f"/api/v2/sync/conflicts/{conflict.id}/resolve",
            json={"resolution": "merged", "merged_payload": "bWVyZ2Vk"},
        ).json()
        assert good["requeued_operation_id"] is not None


def test_domain_invariants_cover_every_synchronization_contract():
    from collective_mindgraph.domain import ConflictRecord, SyncStatus

    workspace_id = WorkspaceId(str(uuid4()))
    object_id = SyncId(str(uuid4()))
    naive = datetime(2026, 1, 1)

    with pytest.raises(ValueError):
        _entry(workspace_id, base_revision=-1)
    with pytest.raises(ValueError):
        OutboxEntry(
            operation_id=OperationId(str(uuid4())),
            workspace_id=workspace_id,
            object_id=object_id,
            object_type="  ",
            base_revision=0,
            local_revision=1,
            client_timestamp=NOW,
            payload=b"x",
        )
    with pytest.raises(ValueError):
        OutboxEntry(
            operation_id=OperationId(str(uuid4())),
            workspace_id=workspace_id,
            object_id=object_id,
            object_type="transcript",
            base_revision=0,
            local_revision=0,
            client_timestamp=NOW,
            payload=b"x",
        )
    with pytest.raises(ValueError):
        OutboxEntry(
            operation_id=OperationId(str(uuid4())),
            workspace_id=workspace_id,
            object_id=object_id,
            object_type="transcript",
            base_revision=0,
            local_revision=1,
            client_timestamp=naive,
            payload=b"x",
        )
    with pytest.raises(ValueError):
        OutboxEntry(
            operation_id=OperationId("not-a-uuid"),
            workspace_id=workspace_id,
            object_id=object_id,
            object_type="transcript",
            base_revision=0,
            local_revision=1,
            client_timestamp=NOW,
            payload=b"x",
        )

    def _conflict(**overrides):
        fields = {
            "id": ConflictId(str(uuid4())),
            "workspace_id": workspace_id,
            "object_id": object_id,
            "object_type": "transcript",
            "local_revision": 1,
            "remote_revision": 2,
            "created_at": NOW,
        }
        fields.update(overrides)
        return ConflictRecord(**fields)

    with pytest.raises(ValueError):
        _conflict(created_at=naive)
    with pytest.raises(ValueError):
        _conflict(resolution=ConflictResolution.LOCAL)
    with pytest.raises(ValueError):
        _conflict(resolved_at=NOW)

    with pytest.raises(ValueError):
        SyncStatus(
            workspace_id=workspace_id,
            phase=SyncPhase.IDLE,
            pending_operations=-1,
            open_conflicts=0,
        )
    with pytest.raises(ValueError):
        SyncStatus(
            workspace_id=WorkspaceId("not-a-uuid"),
            phase=SyncPhase.IDLE,
            pending_operations=0,
            open_conflicts=0,
        )
