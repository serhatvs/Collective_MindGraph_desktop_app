"""Display formatting and safe names for transcript annotation."""

from __future__ import annotations

from typing import Any


def confidence_label(segment: dict[str, Any]) -> str:
    confidence = (segment.get("confidence_metadata") or {}).get("confidence")
    try:
        return "—" if confidence is None else f"{float(confidence):.3f}"
    except (TypeError, ValueError):
        return "—"


def format_milliseconds(milliseconds: int) -> str:
    seconds, millis = divmod(max(0, milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


def safe_directory_name(value: str) -> str:
    cleaned = "_".join(value.strip().split())
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in cleaned)
