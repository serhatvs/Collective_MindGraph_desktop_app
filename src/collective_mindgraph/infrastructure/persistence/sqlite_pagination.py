"""Opaque cursor helpers for SQLite result pages."""

from __future__ import annotations

import base64
import binascii


def decode_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii")
        offset = int(decoded)
    except (ValueError, UnicodeError, binascii.Error) as exc:
        raise ValueError("Invalid pagination cursor.") from exc
    if offset < 0:
        raise ValueError("Invalid pagination cursor.")
    return offset


def encode_offset(offset: int, total: int) -> str | None:
    if offset >= total:
        return None
    return base64.urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii")
