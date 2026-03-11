"""ID generation helpers."""

from __future__ import annotations

from uuid import uuid4


def new_conversation_id() -> str:
    return f"conv_{uuid4().hex}"


def new_segment_id() -> str:
    return f"seg_{uuid4().hex}"
