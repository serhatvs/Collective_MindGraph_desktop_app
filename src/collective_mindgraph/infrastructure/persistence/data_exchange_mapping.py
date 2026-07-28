"""Canonical and legacy data-exchange value mapping."""

from __future__ import annotations

import json

from collective_mindgraph.domain import KnowledgeNodeKind, RelationshipKind


def object_value(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def raw_import_value(
    table: str,
    column: str,
    row: dict[str, object],
) -> object:
    if column in row:
        return row[column]
    defaults: dict[tuple[str, str], object] = {
        ("recordings", "storage_status"): "managed",
        ("recordings", "keep_audio"): 0,
        ("processing_jobs", "retryable"): 0,
    }
    return defaults.get((table, column))


def safe_import_value(
    table: str,
    column: str,
    row: dict[str, object],
) -> object:
    value = raw_import_value(table, column, row)
    if table == "recordings" and column == "storage_status":
        return "deleted" if value == "deleted" else "missing"
    if table == "recordings" and column == "deleted_at" and row.get("storage_status") != "deleted":
        return None
    if table == "processing_jobs":
        status = str(row.get("status") or "")
        if column == "status" and status in {"pending", "running"}:
            return "failed"
        if column == "error" and status in {"pending", "running"}:
            return row.get("error") or "imported_without_runtime"
        if column == "retryable" and status in {"pending", "running"}:
            return 0
    return value


def review_value(attributes: dict[str, object]) -> str:
    current = str(attributes.get("review") or attributes.get("review_status") or "pending")
    return {"approved": "accepted", "completed": "accepted", "edited": "accepted"}.get(
        current.casefold(),
        current.casefold()
        if current.casefold() in {"pending", "accepted", "rejected"}
        else "pending",
    )


def node_kind(value: object) -> str:
    normalized = str(value or "entity").casefold()
    if normalized == "session":
        normalized = "meeting"
    allowed = {item.value for item in KnowledgeNodeKind}
    return normalized if normalized in allowed else KnowledgeNodeKind.ENTITY.value


def relationship_kind(value: object) -> str:
    normalized = str(value or "related_to").casefold()
    mapping = {
        "session_has_segment": "contains",
        "segment_mentions_topic": "mentions",
        "segment_creates_task": "creates",
        "segment_supports_decision": "supports",
        "task_assigned_to_person": "assigned_to",
        "node_merged_into": "merged_into",
    }
    normalized = mapping.get(normalized, normalized)
    allowed = {item.value for item in RelationshipKind}
    return normalized if normalized in allowed else RelationshipKind.RELATED_TO.value
