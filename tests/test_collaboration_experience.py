"""Comments, mentions, activity, and the localhost collaboration surface."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from collective_mindgraph.domain import ActivityKind, Comment, extract_mentions
from collective_mindgraph.domain.collaboration import MAX_COMMENT_CHARACTERS, ActivityEvent
from collective_mindgraph.domain.identifiers import (
    ActivityEventId,
    CommentId,
    SyncId,
    WorkspaceId,
)
from collective_mindgraph.infrastructure.persistence import (
    SqliteCollaborationStore,
    SqliteDatabase,
    initialize_schema,
)

NOW = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)


@pytest.fixture()
def database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(tmp_path / "canonical.sqlite3")
    initialize_schema(database)
    return database


@pytest.fixture()
def store(database: SqliteDatabase) -> SqliteCollaborationStore:
    return SqliteCollaborationStore(database)


def _workspace(database: SqliteDatabase) -> WorkspaceId:
    with database.connect() as connection:
        row = connection.execute("SELECT id FROM workspaces WHERE is_local = 1").fetchone()
    return WorkspaceId(str(row[0]))


# Mentions -----------------------------------------------------------------


def test_mentions_are_parsed_once_in_order_and_case_folded():
    body = "cc @Ada@example.test and @bob@example.test, again @ada@example.test"
    assert extract_mentions(body) == ("ada@example.test", "bob@example.test")


def test_mention_parsing_ignores_addresses_that_are_not_mentions():
    assert extract_mentions("write to ada@example.test directly") == ()
    assert extract_mentions("no mentions here") == ()
    assert extract_mentions("@notanaddress") == ()
    assert extract_mentions("email@host@example.test") == ()


# Domain -------------------------------------------------------------------


def _comment(**overrides) -> Comment:
    fields = {
        "id": CommentId(str(uuid4())),
        "workspace_id": WorkspaceId(str(uuid4())),
        "target_type": "meeting",
        "target_sync_id": SyncId(str(uuid4())),
        "body": "looks right",
        "author_subject": "ada@example.test",
        "created_at": NOW,
        "updated_at": NOW,
    }
    fields.update(overrides)
    return Comment(**fields)


def test_comment_invariants_reject_unusable_input():
    naive = datetime(2026, 1, 1)
    for override in (
        {"body": "   "},
        {"body": "x" * (MAX_COMMENT_CHARACTERS + 1)},
        {"author_subject": " "},
        {"target_type": " "},
        {"created_at": naive},
        {"updated_at": naive},
        {"id": CommentId("not-a-uuid")},
        {"parent_id": CommentId("not-a-uuid")},
    ):
        with pytest.raises(ValueError):
            _comment(**override)
    assert _comment().is_reply is False
    assert _comment(parent_id=CommentId(str(uuid4()))).is_reply is True


def test_activity_invariants_reject_unusable_input():
    workspace_id = WorkspaceId(str(uuid4()))
    with pytest.raises(ValueError):
        ActivityEvent(
            id=ActivityEventId(str(uuid4())),
            workspace_id=workspace_id,
            kind=ActivityKind.COMMENT_ADDED,
            created_at=datetime(2026, 1, 1),
        )
    with pytest.raises(ValueError):
        ActivityEvent(
            id=ActivityEventId(str(uuid4())),
            workspace_id=workspace_id,
            kind=ActivityKind.COMMENT_ADDED,
            created_at=NOW,
            object_sync_id=SyncId("not-a-uuid"),
        )


# Store --------------------------------------------------------------------


def test_comments_append_and_keep_their_thread_order(
    database: SqliteDatabase,
    store: SqliteCollaborationStore,
):
    workspace_id = _workspace(database)
    target = SyncId(str(uuid4()))
    first = store.add_comment(
        workspace_id=workspace_id,
        target_type="meeting",
        target_sync_id=target,
        body="first",
        author_subject="ada@example.test",
    )
    reply = store.add_comment(
        workspace_id=workspace_id,
        target_type="meeting",
        target_sync_id=target,
        body="second",
        author_subject="bob@example.test",
        parent_id=first.id,
    )
    thread = store.comments_for(workspace_id, target_type="meeting", target_sync_id=target)
    assert [entry.body for entry in thread] == ["first", "second"]
    assert thread[1].parent_id == first.id
    assert thread[1].is_reply is True
    assert reply.author_subject == "bob@example.test"

    # A different entity has its own thread.
    assert (
        store.comments_for(
            workspace_id,
            target_type="meeting",
            target_sync_id=SyncId(str(uuid4())),
        )
        == ()
    )


def test_a_reply_requires_an_existing_parent(
    database: SqliteDatabase,
    store: SqliteCollaborationStore,
):
    workspace_id = _workspace(database)
    with pytest.raises(ValueError):
        store.add_comment(
            workspace_id=workspace_id,
            target_type="meeting",
            target_sync_id=SyncId(str(uuid4())),
            body="orphan",
            author_subject="ada@example.test",
            parent_id=CommentId(str(uuid4())),
        )


def test_commenting_records_activity_including_one_event_per_mention(
    database: SqliteDatabase,
    store: SqliteCollaborationStore,
):
    workspace_id = _workspace(database)
    store.add_comment(
        workspace_id=workspace_id,
        target_type="insight",
        target_sync_id=SyncId(str(uuid4())),
        body="@ada@example.test and @bob@example.test please review",
        author_subject="cleo@example.test",
    )
    activity = store.recent_activity(workspace_id)
    kinds = [event.kind for event in activity]
    assert kinds.count(ActivityKind.MEMBER_MENTIONED) == 2
    assert kinds.count(ActivityKind.COMMENT_ADDED) == 1
    mentioned = {
        event.details["subject"]
        for event in activity
        if event.kind is ActivityKind.MEMBER_MENTIONED
    }
    assert mentioned == {"ada@example.test", "bob@example.test"}


def test_mentions_of_returns_only_matching_comments_newest_first(
    database: SqliteDatabase,
    store: SqliteCollaborationStore,
):
    workspace_id = _workspace(database)
    target = SyncId(str(uuid4()))
    for body in ("no mention", "@ada@example.test first", "@ada@example.test second"):
        store.add_comment(
            workspace_id=workspace_id,
            target_type="meeting",
            target_sync_id=target,
            body=body,
            author_subject="bob@example.test",
        )
    found = store.mentions_of(workspace_id, "ADA@example.test")
    assert [entry.body for entry in found] == [
        "@ada@example.test second",
        "@ada@example.test first",
    ]
    assert store.mentions_of(workspace_id, "nobody@example.test") == ()
    assert len(store.mentions_of(workspace_id, "ada@example.test", limit=1)) == 1


def test_activity_is_append_only_and_newest_first(
    database: SqliteDatabase,
    store: SqliteCollaborationStore,
):
    workspace_id = _workspace(database)
    for kind in (ActivityKind.MEETING_ADDED, ActivityKind.INSIGHT_REVIEWED):
        store.record_activity(
            workspace_id=workspace_id,
            kind=kind,
            actor_subject="ada@example.test",
            details={"note": "recorded"},
        )
    activity = store.recent_activity(workspace_id, limit=1)
    assert len(activity) == 1
    assert activity[0].details == {"note": "recorded"}
    assert store.recent_activity(workspace_id, limit=0) != ()


def test_unreadable_activity_details_degrade_to_empty(
    database: SqliteDatabase,
    store: SqliteCollaborationStore,
):
    workspace_id = _workspace(database)
    event = store.record_activity(workspace_id=workspace_id, kind=ActivityKind.MEETING_ADDED)
    with database.connect() as connection:
        connection.execute(
            "UPDATE activity_events SET details_json = ? WHERE id = ?",
            ("not-json", str(event.id)),
        )
    assert store.recent_activity(workspace_id)[0].details == {}


# Localhost surface --------------------------------------------------------


@pytest.fixture()
def engine(tmp_path: Path):
    from collective_mindgraph.engine.main import create_app
    from collective_mindgraph.engine.settings import EngineSettings

    root = tmp_path / "engine"
    application = create_app(
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
    with TestClient(application) as client:
        yield client, application


def test_the_surface_adds_comments_and_reports_mentions(engine):
    client, application = engine
    workspace_id = application.state.engine_context.workspaces.local_workspace().id
    target = str(uuid4())

    created = client.post(
        f"/api/v2/collaboration/{workspace_id}/comments",
        json={
            "target_type": "meeting",
            "target_sync_id": target,
            "body": "@ada@example.test can you check this",
            "author_subject": "bob@example.test",
        },
    )
    assert created.status_code == 201
    assert created.json()["mentions"] == ["ada@example.test"]

    thread = client.get(
        f"/api/v2/collaboration/{workspace_id}/comments",
        params={"target_type": "meeting", "target_sync_id": target},
    ).json()
    assert len(thread) == 1

    mentions = client.get(
        f"/api/v2/collaboration/{workspace_id}/mentions",
        params={"subject": "ada@example.test"},
    ).json()
    assert len(mentions) == 1

    activity = client.get(f"/api/v2/collaboration/{workspace_id}/activity").json()
    assert {entry["kind"] for entry in activity} == {"comment.added", "member.mentioned"}
    assert client.get("/api/v2/collaboration/kinds").json() == [kind.value for kind in ActivityKind]


def test_the_surface_rejects_unusable_comments(engine):
    client, application = engine
    workspace_id = application.state.engine_context.workspaces.local_workspace().id
    body = {
        "target_type": "meeting",
        "target_sync_id": str(uuid4()),
        "body": "hello",
        "author_subject": "ada@example.test",
    }
    assert (
        client.post(
            f"/api/v2/collaboration/{workspace_id}/comments",
            json={**body, "body": ""},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v2/collaboration/{workspace_id}/comments",
            json={**body, "parent_id": str(uuid4())},
        ).status_code
        == 422
    )
    assert (
        client.get(
            f"/api/v2/collaboration/{workspace_id}/activity",
            params={"limit": 0},
        ).status_code
        == 422
    )


def test_local_only_use_still_works_without_any_account(engine):
    """Collaboration storage is local; nothing here requires sign-in."""

    client, application = engine
    workspace_id = application.state.engine_context.workspaces.local_workspace().id
    assert client.get(f"/api/v2/collaboration/{workspace_id}/activity").json() == []
    assert client.get("/api/v1/dashboard").status_code == 200
