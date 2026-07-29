"""Authenticated, passphrase-encrypted user backup archives."""

from __future__ import annotations

import json
import os
import tempfile
from base64 import b64decode, b64encode
from collections.abc import Mapping
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

BACKUP_EXTENSION = ".cmgbackup"
BACKUP_FORMAT = "collective_mindgraph_encrypted_backup"
BACKUP_FORMAT_VERSION = 1
_SALT_BYTES = 16
_NONCE_BYTES = 12
_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1


class InvalidBackupError(ValueError):
    """Raised when an encrypted backup cannot be authenticated or decoded."""


def write_encrypted_backup(
    path: Path,
    payload: Mapping[str, object],
    *,
    passphrase: str,
) -> Path:
    """Encrypt a canonical export and atomically write a ``.cmgbackup`` file."""

    destination = _validated_destination(path)
    password = _validated_passphrase(passphrase)
    salt = os.urandom(_SALT_BYTES)
    nonce = os.urandom(_NONCE_BYTES)
    metadata: dict[str, object] = {
        "format": BACKUP_FORMAT,
        "format_version": BACKUP_FORMAT_VERSION,
        "kdf": {
            "name": "scrypt",
            "salt": _encode(salt),
            "n": _SCRYPT_N,
            "r": _SCRYPT_R,
            "p": _SCRYPT_P,
        },
        "cipher": {
            "name": "AES-256-GCM",
            "nonce": _encode(nonce),
        },
    }
    plaintext = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    ciphertext = AESGCM(_derive_key(password, salt)).encrypt(
        nonce,
        plaintext,
        _associated_data(metadata),
    )
    archive = {**metadata, "ciphertext": _encode(ciphertext)}
    encoded = json.dumps(archive, separators=(",", ":"), sort_keys=True).encode("utf-8")
    _atomic_write(destination, encoded)
    return destination


def read_encrypted_backup(path: Path, *, passphrase: str) -> dict[str, object]:
    """Authenticate and decrypt a ``.cmgbackup`` file."""

    password = _validated_passphrase(passphrase)
    try:
        archive = json.loads(path.read_text(encoding="utf-8"))
        metadata, salt, nonce, ciphertext = _validated_archive(archive)
        plaintext = AESGCM(_derive_key(password, salt)).decrypt(
            nonce,
            ciphertext,
            _associated_data(metadata),
        )
        payload = json.loads(plaintext.decode("utf-8"))
    except (InvalidTag, OSError, UnicodeError, ValueError, TypeError, KeyError) as error:
        raise InvalidBackupError(
            "Backup authentication failed or the archive is invalid."
        ) from error
    if not isinstance(payload, dict):
        raise InvalidBackupError("Backup payload must be a JSON object.")
    return {str(key): value for key, value in payload.items()}


def _validated_destination(path: Path) -> Path:
    destination = path.expanduser().resolve()
    if destination.suffix.lower() != BACKUP_EXTENSION:
        raise ValueError(f"Backup path must use the {BACKUP_EXTENSION} extension.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def _validated_passphrase(passphrase: str) -> bytes:
    encoded = passphrase.encode("utf-8")
    if len(encoded) < 12:
        raise ValueError("Backup passphrase must contain at least 12 UTF-8 bytes.")
    return encoded


def _derive_key(password: bytes, salt: bytes) -> bytes:
    return Scrypt(
        salt=salt,
        length=32,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    ).derive(password)


def _validated_archive(
    archive: object,
) -> tuple[dict[str, object], bytes, bytes, bytes]:
    if not isinstance(archive, dict):
        raise InvalidBackupError("Backup archive must be a JSON object.")
    if (
        archive.get("format") != BACKUP_FORMAT
        or archive.get("format_version") != BACKUP_FORMAT_VERSION
    ):
        raise InvalidBackupError("Unsupported backup format.")
    kdf = archive.get("kdf")
    cipher = archive.get("cipher")
    if not isinstance(kdf, dict) or not isinstance(cipher, dict):
        raise InvalidBackupError("Backup cryptographic metadata is missing.")
    if (
        kdf.get("name") != "scrypt"
        or kdf.get("n") != _SCRYPT_N
        or kdf.get("r") != _SCRYPT_R
        or kdf.get("p") != _SCRYPT_P
        or cipher.get("name") != "AES-256-GCM"
    ):
        raise InvalidBackupError("Unsupported backup cryptographic parameters.")
    salt = _decode(kdf["salt"])
    nonce = _decode(cipher["nonce"])
    ciphertext = _decode(archive["ciphertext"])
    if len(salt) != _SALT_BYTES or len(nonce) != _NONCE_BYTES:
        raise InvalidBackupError("Backup cryptographic parameters are invalid.")
    metadata: dict[str, object] = {
        "format": archive["format"],
        "format_version": archive["format_version"],
        "kdf": kdf,
        "cipher": cipher,
    }
    return metadata, salt, nonce, ciphertext


def _associated_data(metadata: Mapping[str, object]) -> bytes:
    return json.dumps(metadata, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _encode(value: bytes) -> str:
    return b64encode(value).decode("ascii")


def _decode(value: object) -> bytes:
    if not isinstance(value, str):
        raise InvalidBackupError("Backup binary field is invalid.")
    return b64decode(value, validate=True)


def _atomic_write(destination: Path, data: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


__all__ = [
    "BACKUP_EXTENSION",
    "BACKUP_FORMAT",
    "BACKUP_FORMAT_VERSION",
    "InvalidBackupError",
    "read_encrypted_backup",
    "write_encrypted_backup",
]
