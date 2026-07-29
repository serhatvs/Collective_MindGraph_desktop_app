"""Operator entry points: service CLI, admin CLI, and Alembic migrations."""

from __future__ import annotations

import json
from base64 import b64encode
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from collective_mindgraph.sync_server import admin_cli, cli
from collective_mindgraph.sync_server.blob_storage import FilesystemBlobStore
from collective_mindgraph.sync_server.http_support import (
    encode_bytes,
    optional_bytes,
    required_bytes,
)
from collective_mindgraph.sync_server.schemas import EnvelopeRequest, OperationRequest

MIGRATIONS = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "collective_mindgraph"
    / "sync_server"
    / "migrations"
)
EXPECTED_TABLES = {
    "audit_events",
    "blob_chunks",
    "blob_manifests",
    "devices",
    "key_envelopes",
    "memberships",
    "sync_objects",
    "sync_operations",
    "tenants",
    "usage_counters",
    "user_subjects",
    "workspace_cursors",
    "workspaces",
}


def _environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'service.sqlite3').as_posix()}"
    monkeypatch.setenv("CMG_SYNC_DATABASE_URL", url)
    monkeypatch.setenv("CMG_SYNC_BLOB_ROOT", str(tmp_path / "blobs"))
    return url


def test_service_cli_only_starts_the_configured_application(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _environment(tmp_path, monkeypatch)
    monkeypatch.setenv("CMG_SYNC_BOOTSTRAP_TOKENS", "token=operator@example.test")
    started: dict[str, object] = {}

    def _run(app: object, **options: object) -> None:
        started["app"] = app
        started["options"] = options

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", _run)
    assert cli.main(["--host", "0.0.0.0", "--port", "9443", "--log-level", "WARNING"]) == 0
    assert started["options"] == {"host": "0.0.0.0", "port": 9443, "log_level": "warning"}
    assert getattr(started["app"], "title") == "Collective MindGraph Sync"


def test_admin_cli_creates_the_schema_and_purges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    url = _environment(tmp_path, monkeypatch)
    assert admin_cli.main(["create-schema"]) == 0

    engine = create_engine(url.replace("+aiosqlite", ""))
    try:
        assert EXPECTED_TABLES.issubset(set(inspect(engine).get_table_names()))
    finally:
        engine.dispose()

    assert admin_cli.main(["purge"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report == {"audit_events": 0, "blobs": 0, "objects": 0}

    assert admin_cli.main(["show-retention"]) == 0
    windows = json.loads(capsys.readouterr().out)
    assert windows == {"audit_days": 90, "backup_days": 35, "content_days": 30}


def test_migrations_create_and_drop_the_full_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from alembic import command
    from alembic.config import Config

    url = f"sqlite+aiosqlite:///{(tmp_path / 'migrated.sqlite3').as_posix()}"
    monkeypatch.setenv("CMG_SYNC_DATABASE_URL", url)
    configuration = Config(str(MIGRATIONS / "alembic.ini"))
    configuration.set_main_option("script_location", str(MIGRATIONS))

    command.upgrade(configuration, "head")
    engine = create_engine(url.replace("+aiosqlite", ""))
    try:
        assert EXPECTED_TABLES.issubset(set(inspect(engine).get_table_names()))
        command.downgrade(configuration, "base")
        assert EXPECTED_TABLES.isdisjoint(set(inspect(engine).get_table_names()))
    finally:
        engine.dispose()


def test_filesystem_store_reports_missing_and_nested_prefixes(tmp_path: Path):
    store = FilesystemBlobStore(tmp_path / "blobs")
    store.put("workspace/manifest/00000000.chunk", b"sealed")
    store.put("workspace/manifest/nested/00000001.chunk", b"sealed")
    assert store.delete_prefix("workspace/manifest") == 2


def test_base64_helpers_reject_malformed_sealed_fields():
    from fastapi import HTTPException

    assert optional_bytes(None) is None
    assert optional_bytes(encode_bytes(b"sealed")) == b"sealed"
    assert required_bytes(encode_bytes(b"sealed"), "wrapped key") == b"sealed"
    with pytest.raises(HTTPException) as invalid:
        optional_bytes("not base64!")
    assert invalid.value.status_code == 422
    with pytest.raises(HTTPException) as empty:
        required_bytes(encode_bytes(b""), "wrapped key")
    assert empty.value.status_code == 422


def test_request_schemas_validate_sealed_fields():
    with pytest.raises(ValueError):
        OperationRequest(
            operation_id="a",
            object_id="b",
            object_type="transcript",
            base_revision=0,
            key_version=1,
            client_timestamp="2026-01-01T00:00:00+00:00",
            ciphertext="not base64!",
        )
    request = OperationRequest(
        operation_id="a",
        object_id="b",
        object_type="transcript",
        base_revision=0,
        key_version=1,
        client_timestamp="2026-01-01T00:00:00+00:00",
        ciphertext=b64encode(b"sealed").decode("ascii"),
        nonce=b64encode(bytes(12)).decode("ascii"),
    )
    assert request.to_input().ciphertext == b"sealed"
    assert EnvelopeRequest(key_version=1, wrapped_key="AAAA").recipient_device_id is None
