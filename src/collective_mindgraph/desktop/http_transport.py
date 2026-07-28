"""Localhost-only JSON and multipart HTTP transport."""

from __future__ import annotations

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
        body = bytearray()
        for name, value in fields.items():
            if value is None:
                continue
            body.extend(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    f"{value}\r\n"
                ).encode()
            )
        body.extend(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="upload"; '
                f'filename="{file_path.name}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode()
        )
        body.extend(file_path.read_bytes())
        body.extend(f"\r\n--{boundary}--\r\n".encode("ascii"))
        request = urllib.request.Request(
            self._url(path),
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        return self._send(request)

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
            payload = _decode(raw)
            raise EngineClientError(
                code=str(payload.get("code") or f"http_{exc.code}"),
                message=str(payload.get("message") or payload.get("detail") or exc.reason),
                retryable=bool(payload.get("retryable", exc.code >= 500)),
                status_code=exc.code,
                details=(
                    dict(payload["details"]) if isinstance(payload.get("details"), dict) else {}
                ),
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
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


def _decode(raw: bytes) -> dict[str, object]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EngineClientError("invalid_response", "Engine returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise EngineClientError("invalid_response", "Engine returned an invalid payload.")
    return payload
