"""Operating-system protected storage for this device's private key material."""

from __future__ import annotations

import ctypes
import hashlib
import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

SECRET_EXTENSION = ".secret"
DPAPI_ENTROPY = b"collective-mindgraph/device-secret/v1"
_CRYPTPROTECT_UI_FORBIDDEN = 0x01

ProtectFunction = Callable[[bytes], bytes]
UnprotectFunction = Callable[[bytes], bytes]


class DeviceSecretUnavailableError(RuntimeError):
    """Raised when protected device material exists but cannot be unsealed."""


class ProtectedFileSecretStore:
    """Stores sealed secrets as owner-only files under a private directory.

    The seal and unseal callables decide the actual protection. On Windows the
    factory supplies DPAPI user-scope protection; elsewhere the callables are
    identity functions and the store is development-only, which the desktop
    surfaces honestly rather than implying stronger protection.
    """

    def __init__(
        self,
        directory: Path,
        *,
        seal: ProtectFunction | None = None,
        unseal: UnprotectFunction | None = None,
        protected: bool = False,
    ) -> None:
        self._directory = directory.expanduser().resolve()
        self._seal = seal or (lambda payload: payload)
        self._unseal = unseal or (lambda payload: payload)
        self.protected = protected

    def store(self, name: str, secret: bytes) -> None:
        """Seal and atomically persist one named secret."""

        if not secret:
            raise ValueError("Device secrets cannot be empty.")
        self._directory.mkdir(parents=True, exist_ok=True)
        _restrict(self._directory)
        destination = self._path(name)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=self._directory,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(self._seal(secret))
                stream.flush()
                os.fsync(stream.fileno())
            _restrict(temporary)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

    def load(self, name: str) -> bytes | None:
        """Return one unsealed secret, or ``None`` when it was never stored."""

        path = self._path(name)
        if not path.exists():
            return None
        try:
            return self._unseal(path.read_bytes())
        except OSError as error:
            raise DeviceSecretUnavailableError(
                "Protected device material could not be read."
            ) from error

    def delete(self, name: str) -> None:
        """Remove one stored secret if it exists."""

        self._path(name).unlink(missing_ok=True)

    def _path(self, name: str) -> Path:
        if not name.strip():
            raise ValueError("Secret name is required.")
        digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
        return self._directory / f"{digest}{SECRET_EXTENSION}"


def create_device_secret_store(
    directory: Path,
    *,
    platform: str | None = None,
) -> ProtectedFileSecretStore:
    """Return the strongest secret store the target platform supports."""

    if (platform or sys.platform) == "win32":
        return ProtectedFileSecretStore(
            directory,
            seal=dpapi_protect,
            unseal=dpapi_unprotect,
            protected=True,
        )
    return ProtectedFileSecretStore(directory)


class _DataBlob(ctypes.Structure):
    _fields_ = (
        ("cbData", ctypes.c_uint32),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    )


def dpapi_protect(payload: bytes) -> bytes:  # pragma: no cover - platform specific
    """Protect bytes with Windows DPAPI under the current user account."""

    return _dpapi_call(payload, protect=True)


def dpapi_unprotect(payload: bytes) -> bytes:  # pragma: no cover - platform specific
    """Unprotect bytes previously sealed by :func:`dpapi_protect`."""

    return _dpapi_call(payload, protect=False)


def _dpapi_call(payload: bytes, *, protect: bool) -> bytes:  # pragma: no cover - Windows only
    windll = getattr(ctypes, "windll")
    crypt32 = windll.crypt32
    kernel32 = windll.kernel32
    # The buffers must outlive the call because the blobs only hold pointers.
    source_buffer = ctypes.create_string_buffer(payload, len(payload))
    entropy_buffer = ctypes.create_string_buffer(DPAPI_ENTROPY, len(DPAPI_ENTROPY))
    source = _blob(source_buffer)
    entropy = _blob(entropy_buffer)
    result = _DataBlob()
    function = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    succeeded = function(
        ctypes.byref(source),
        None,
        ctypes.byref(entropy),
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(result),
    )
    if not succeeded:
        raise DeviceSecretUnavailableError(
            "Windows DPAPI rejected the device secret for this user account."
        )
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(result.pbData)


def _blob(buffer: ctypes.Array[ctypes.c_char]) -> _DataBlob:  # pragma: no cover - Windows only
    return _DataBlob(len(buffer), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))


def _restrict(path: Path) -> None:
    if sys.platform == "win32":
        return
    path.chmod(0o700 if path.is_dir() else 0o600)


__all__ = [
    "DPAPI_ENTROPY",
    "DeviceSecretUnavailableError",
    "ProtectedFileSecretStore",
    "create_device_secret_store",
    "dpapi_protect",
    "dpapi_unprotect",
]
