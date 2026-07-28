"""Localhost-only JSON and multipart HTTP transport."""

from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .contracts import EngineSettings


@dataclass(frozen=True, slots=True)
class EngineClientError(RuntimeError):
    code: str
    message: str
    retryable: bool = False
    status_code: int | None = None
    details: dict[str, object] | None = None

    def __str__(self) -> str:
        return self.message


def is_engine_offline_error(error: BaseException) -> bool:
    """Return whether a failure means no local engine accepted the connection."""
    return isinstance(error, EngineClientError) and error.code == "engine_offline"


class LocalHttpTransport:
    def __init__(self, settings: EngineSettings) -> None:
        self._settings = settings
        parsed = urllib.parse.urlparse(settings.base_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
            "127.0.0.1",
            "localhost",
            "::1",
        }:
            raise ValueError("The desktop engine client only accepts localhost URLs.")
        self._base_url = settings.base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, object] | None = None,
        body: dict[str, object] | None = None,
        expect_json: bool = True,
    ) -> dict[str, object]:
        url = self._url(path, query)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        return self._send(request, expect_json=expect_json)

    def multipart(
        self,
        path: str,
        file_path: Path,
        fields: dict[str, str | None],
    ) -> dict[str, object]:
        boundary = f"----mindgraph-{uuid4().hex}"
        preamble = bytearray()
        for name, value in fields.items():
            if value is None:
                continue
            safe_name = _header_value(name)
            preamble.extend(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{safe_name}"\r\n\r\n'
                    f"{value}\r\n"
                ).encode()
            )
        preamble.extend(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="upload"; '
                f'filename="{_header_value(file_path.name)}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode()
        )
        epilogue = f"\r\n--{boundary}--\r\n".encode("ascii")
        content_length = len(preamble) + file_path.stat().st_size + len(epilogue)
        parsed = urllib.parse.urlsplit(self._url(path))
        connection_type = (
            http.client.HTTPSConnection
            if parsed.scheme == "https"
            else http.client.HTTPConnection
        )
        connection = connection_type(
            parsed.hostname,
            parsed.port,
            timeout=self._settings.timeout_seconds,
        )
        target = parsed.path or "/"
        if parsed.query:
            target = f"{target}?{parsed.query}"
        try:
            connection.putrequest("POST", target)
            connection.putheader(
                "Content-Type",
                f"multipart/form-data; boundary={boundary}",
            )
            connection.putheader("Content-Length", str(content_length))
            connection.putheader("Accept", "application/json")
            connection.endheaders()
            connection.send(preamble)
            with file_path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    connection.send(chunk)
            connection.send(epilogue)
            response = connection.getresponse()
            raw = response.read()
        except TimeoutError as exc:
            raise EngineClientError(
                code="engine_timeout",
                message="The local engine did not respond in time.",
                retryable=True,
            ) from exc
        except (http.client.HTTPException, OSError) as exc:
            raise EngineClientError(
                code="engine_offline",
                message="The local engine is unavailable.",
                retryable=True,
            ) from exc
        finally:
            connection.close()
        if response.status >= 400:
            _raise_http_error(response.status, str(response.reason), raw)
        return _decode(raw) if raw else {}

    def _send(
        self,
        request: urllib.request.Request,
        *,
        expect_json: bool = True,
    ) -> dict[str, object]:
        try:
            with urllib.request.urlopen(
                request,
                timeout=self._settings.timeout_seconds,
            ) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                _raise_http_error(exc.code, str(exc.reason), raw)
            except EngineClientError as error:
                raise error from exc
        except TimeoutError as exc:
            raise EngineClientError(
                code="engine_timeout",
                message="The local engine did not respond in time.",
                retryable=True,
            ) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise EngineClientError(
                    code="engine_timeout",
                    message="The local engine did not respond in time.",
                    retryable=True,
                ) from exc
            raise EngineClientError(
                code="engine_offline",
                message="The local engine is unavailable.",
                retryable=True,
            ) from exc
        return _decode(raw) if expect_json and raw else {}

    def _url(
        self,
        path: str,
        query: dict[str, object] | None = None,
    ) -> str:
        values = {
            key: value for key, value in (query or {}).items() if value is not None and value != ""
        }
        suffix = f"?{urllib.parse.urlencode(values)}" if values else ""
        return f"{self._base_url}{path}{suffix}"


def _raise_http_error(status: int, reason: str, raw: bytes) -> None:
    try:
        payload = _decode(raw)
    except EngineClientError:
        payload = {}
    raise EngineClientError(
        code=str(payload.get("code") or f"http_{status}"),
        message=str(payload.get("message") or payload.get("detail") or reason),
        retryable=bool(payload.get("retryable", status >= 500)),
        status_code=status,
        details=dict(payload["details"]) if isinstance(payload.get("details"), dict) else {},
    )


def _header_value(value: str) -> str:
    return value.replace("\r", "_").replace("\n", "_").replace('"', "_")


def _decode(raw: bytes) -> dict[str, object]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EngineClientError("invalid_response", "Engine returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise EngineClientError("invalid_response", "Engine returned an invalid payload.")
    return payload
