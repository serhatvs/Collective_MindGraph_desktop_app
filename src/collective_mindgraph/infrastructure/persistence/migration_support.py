"""Shared helpers for deterministic legacy-data imports."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .row_mapping import dump_json

MIGRATION_NAMESPACE = uuid.UUID("d262c324-8549-4a59-ab83-6135e586b828")


def stable_id(*parts: object) -> str:
    rendered = ":".join(str(part) for part in parts)
    return str(uuid.uuid5(MIGRATION_NAMESPACE, rendered))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def open_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def safe_json(value: object, fallback: object) -> object:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str) or not value.strip():
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def normalized_timestamp(value: object | None = None) -> str:
    if value:
        rendered = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(rendered)
        except ValueError:
            parsed = datetime.now(tz=UTC)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.isoformat()
    return datetime.now(tz=UTC).isoformat()


def map_meeting_status(value: object, *, has_transcript: bool) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "archived":
        return "archived"
    if normalized == "failed":
        return "failed"
    if normalized in {"recording", "processing"}:
        return normalized
    return "ready" if has_transcript or normalized == "completed" else "draft"


def map_review(metadata: dict[str, object]) -> tuple[str, bool]:
    raw = str(metadata.get("review_status", "pending")).strip().lower()
    if raw in {"approved", "accepted", "edited"}:
        return "accepted", raw == "edited" or bool(metadata.get("edited_by_user"))
    if raw in {"rejected", "merged"} or bool(metadata.get("disabled")):
        return "rejected", bool(metadata.get("edited_by_user"))
    return "pending", bool(metadata.get("edited_by_user"))


def map_node_kind(value: object) -> str:
    normalized = str(value or "").strip().lower()
    aliases = {"session": "meeting"}
    supported = {
        "meeting",
        "segment",
        "note",
        "task",
        "decision",
        "topic",
        "person",
        "document",
        "project",
        "entity",
        "risk",
        "open_question",
        "follow_up",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in supported else "note"


def map_edge_kind(value: object) -> str:
    normalized = str(value or "").strip().upper()
    if "MERGED_INTO" in normalized:
        return "merged_into"
    if "ASSIGNED_TO" in normalized:
        return "assigned_to"
    if "SUPPORTS" in normalized:
        return "supports"
    if "CREATES" in normalized:
        return "creates"
    if "CONTAINS" in normalized or "HAS_" in normalized:
        return "contains"
    if "RELATED_TO" in normalized:
        return "related_to"
    if "DERIVED_FROM" in normalized:
        return "derived_from"
    return "mentions"


def record_source(
    destination: sqlite3.Connection,
    *,
    source_hash: str,
    source_path: Path,
    source_kind: str,
    details: dict[str, object],
) -> None:
    destination.execute(
        """
        INSERT OR IGNORE INTO migration_sources(
            source_hash, source_path, source_kind, imported_at, details_json
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            source_hash,
            str(source_path),
            source_kind,
            datetime.now(tz=UTC).isoformat(),
            dump_json(details),
        ),
    )
