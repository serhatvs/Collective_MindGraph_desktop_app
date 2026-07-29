"""Single-use workspace recovery codes with a verifiable checksum."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable

RECOVERY_ENTROPY_BYTES = 32
CHECKSUM_CHARACTERS = 2
GROUP_SIZE = 6
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_DECODE = {character: index for index, character in enumerate(_ALPHABET)}
_ALIASES = {"I": "1", "L": "1", "O": "0", "U": "V"}


class InvalidRecoveryCodeError(ValueError):
    """Raised when a recovery code is malformed or fails its checksum."""


class ChecksummedRecoveryCodeFactory:
    """Generates 256-bit Crockford base32 recovery codes."""

    def __init__(self, entropy_source: Callable[[int], bytes] | None = None) -> None:
        self._entropy = entropy_source or os.urandom

    def generate(self) -> str:
        """Return a grouped recovery code for one-time display to the user."""

        entropy = self._entropy(RECOVERY_ENTROPY_BYTES)
        body = _encode(entropy)
        code = body + _checksum(body)
        return "-".join(
            code[index : index + GROUP_SIZE] for index in range(0, len(code), GROUP_SIZE)
        )

    def normalize(self, code: str) -> str:
        """Return the canonical code, rejecting typos and bad checksums."""

        compact = "".join(
            _ALIASES.get(character, character)
            for character in code.strip().upper()
            if not character.isspace() and character not in {"-", "_"}
        )
        expected_length = _encoded_length(RECOVERY_ENTROPY_BYTES) + CHECKSUM_CHARACTERS
        if len(compact) != expected_length:
            raise InvalidRecoveryCodeError("Recovery code has an unexpected length.")
        if any(character not in _DECODE for character in compact):
            raise InvalidRecoveryCodeError("Recovery code contains unsupported characters.")
        body, checksum = compact[:-CHECKSUM_CHARACTERS], compact[-CHECKSUM_CHARACTERS:]
        if _checksum(body) != checksum:
            raise InvalidRecoveryCodeError("Recovery code checksum does not match.")
        return compact


def _encode(payload: bytes) -> str:
    bits = int.from_bytes(payload, "big")
    length = _encoded_length(len(payload))
    characters = []
    for position in range(length - 1, -1, -1):
        characters.append(_ALPHABET[(bits >> (position * 5)) & 0x1F])
    return "".join(characters)


def _encoded_length(byte_length: int) -> int:
    return (byte_length * 8 + 4) // 5


def _checksum(body: str) -> str:
    digest = hashlib.sha256(body.encode("ascii")).digest()
    value = int.from_bytes(digest[:2], "big")
    return "".join(
        _ALPHABET[(value >> (position * 5)) & 0x1F]
        for position in range(CHECKSUM_CHARACTERS - 1, -1, -1)
    )


__all__ = [
    "CHECKSUM_CHARACTERS",
    "RECOVERY_ENTROPY_BYTES",
    "ChecksummedRecoveryCodeFactory",
    "InvalidRecoveryCodeError",
]
