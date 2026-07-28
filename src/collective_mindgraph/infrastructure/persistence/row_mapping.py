"""Shared SQLite value conversion for persistence adapters."""

from __future__ import annotations

import json
from datetime import UTC, datetime


def parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def dump_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def load_object(value: str | None) -> dict[str, object]:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}
    return dict(loaded) if isinstance(loaded, dict) else {}


def load_string_tuple(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    try:
        loaded = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return ()
    if not isinstance(loaded, list):
        return ()
    return tuple(str(item) for item in loaded)
