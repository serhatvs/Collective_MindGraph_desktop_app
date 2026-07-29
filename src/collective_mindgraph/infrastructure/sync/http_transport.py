"""HTTP transport for `/sync/v1`.

Payloads are already sealed before they reach this module. It base64-encodes
them for transport and never inspects, logs, or reshapes their contents.
"""

from __future__ import annotations

from base64 import b64decode, b64encode
from collections.abc import Callable, Sequence
from typing import Any

from collective_mindgraph.application.ports.sync_transport import (
    RemoteOperationResult,
    RemoteOutcome,
    RemotePullPage,
    RemotePushResult,
    RemoteRecord,
    RetryableTransportError,
    SyncTransportError,
)
from collective_mindgraph.infrastructure.persistence.row_mapping import parse_timestamp

DEFAULT_TIMEOUT_SECONDS = 30.0
# 5xx and 429 mean "try again"; 4xx means the request itself was wrong.
RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


class HttpSyncTransport:
    """Talks to one deployment on behalf of one authenticated user."""

    def __init__(
        self,
        base_url: str,
        *,
        access_token: Callable[[], str],
        request: Callable[..., Any] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not base_url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise SyncTransportError("The sync service must be reached over HTTPS.")
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._request = request or _httpx_request
        self._timeout = timeout_seconds

    def push(
        self,
        *,
        workspace_id: str,
        device_id: str,
        operations: Sequence[Any],
    ) -> RemotePushResult:
        """Send one batch of sealed operations."""

        payload = {
            "device_id": device_id,
            "operations": [_encode_operation(entry) for entry in operations],
        }
        body = self._call(
            "POST",
            f"/sync/v1/workspaces/{workspace_id}/push",
            json=payload,
        )
        return RemotePushResult(
            cursor=str(body.get("cursor", "0")),
            results=tuple(_decode_result(entry) for entry in body.get("results", [])),
        )

    def pull(
        self,
        *,
        workspace_id: str,
        cursor: str,
        limit: int | None = None,
    ) -> RemotePullPage:
        """Fetch one page of sealed changes after a cursor."""

        parameters: dict[str, str] = {"cursor": cursor}
        if limit is not None:
            parameters["limit"] = str(limit)
        body = self._call(
            "GET",
            f"/sync/v1/workspaces/{workspace_id}/pull",
            params=parameters,
        )
        return RemotePullPage(
            cursor=str(body.get("cursor", cursor)),
            has_more=bool(body.get("has_more", False)),
            records=tuple(_decode_record(entry) for entry in body.get("records", [])),
        )

    def _call(self, method: str, path: str, **options: Any) -> dict[str, Any]:
        try:
            status, body = self._request(
                method,
                f"{self._base_url}{path}",
                headers={"Authorization": f"Bearer {self._access_token()}"},
                timeout=self._timeout,
                **options,
            )
        except Exception as error:  # noqa: BLE001 - any transport fault is retryable
            raise RetryableTransportError(f"The sync service is unreachable: {error}") from error
        if status in RETRYABLE_STATUS:
            raise RetryableTransportError(f"The sync service is unavailable ({status}).")
        if status >= 400:
            detail = body.get("detail") if isinstance(body, dict) else None
            raise SyncTransportError(f"The sync service refused the request: {detail or status}")
        if not isinstance(body, dict):
            raise SyncTransportError("The sync service returned an unusable response.")
        return body


def _encode_operation(entry: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "operation_id": str(entry.operation_id),
        "object_id": str(entry.object_id),
        "object_type": entry.object_type,
        "base_revision": entry.base_revision,
        "key_version": getattr(entry, "key_version", 1),
        "client_timestamp": entry.client_timestamp.isoformat(),
        "deleted": bool(entry.deleted),
    }
    if not entry.deleted:
        payload["ciphertext"] = b64encode(entry.payload).decode("ascii")
        payload["nonce"] = b64encode(getattr(entry, "nonce", b"\x00" * 12)).decode("ascii")
    return payload


def _decode_result(entry: Any) -> RemoteOperationResult:
    return RemoteOperationResult(
        operation_id=str(entry["operation_id"]),
        object_id=str(entry["object_id"]),
        outcome=RemoteOutcome(str(entry["outcome"])),
        revision=entry.get("revision"),
        server_revision=entry.get("server_revision"),
    )


def _decode_record(entry: Any) -> RemoteRecord:
    return RemoteRecord(
        object_id=str(entry["object_id"]),
        object_type=str(entry["object_type"]),
        revision=int(entry["revision"]),
        key_version=int(entry["key_version"]),
        deleted=bool(entry["deleted"]),
        server_timestamp=parse_timestamp(str(entry["server_timestamp"])),
        ciphertext=_decode_bytes(entry.get("ciphertext")),
        nonce=_decode_bytes(entry.get("nonce")),
    )


def _decode_bytes(value: object) -> bytes | None:
    if not isinstance(value, str):
        return None
    try:
        return b64decode(value, validate=True)
    except ValueError as error:
        raise SyncTransportError("The sync service returned a malformed payload.") from error


def _httpx_request(  # pragma: no cover - network boundary
    method: str,
    url: str,
    **options: Any,
) -> tuple[int, Any]:
    import httpx

    response = httpx.request(method, url, **options)
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None


__all__ = ["RETRYABLE_STATUS", "HttpSyncTransport"]
