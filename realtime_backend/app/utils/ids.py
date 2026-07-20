"""ID generation helpers."""

from __future__ import annotations

from uuid import uuid4


_MAX_CONVERSATION_ID_LENGTH = 128
_WINDOWS_RESERVED_NAMES = {
    "AUX",
    "CON",
    "NUL",
    "PRN",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def new_conversation_id() -> str:
    return f"conv_{uuid4().hex}"


def validate_conversation_id(value: str) -> str:
    """Return a filesystem-safe conversation ID or raise ``ValueError``."""

    candidate = str(value)
    if not candidate or len(candidate) > _MAX_CONVERSATION_ID_LENGTH:
        raise ValueError(
            f"conversation_id must contain 1-{_MAX_CONVERSATION_ID_LENGTH} characters."
        )
    if candidate in {".", ".."} or candidate.endswith("."):
        raise ValueError("conversation_id cannot be a relative path or end with a period.")
    if any(not (character.isalnum() or character in {"-", "_", "."}) for character in candidate):
        raise ValueError(
            "conversation_id may contain only letters, numbers, hyphens, underscores, and periods."
        )
    if candidate.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
        raise ValueError("conversation_id uses a reserved Windows filename.")
    return candidate


def new_segment_id() -> str:
    return f"seg_{uuid4().hex}"
