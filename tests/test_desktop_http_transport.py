from __future__ import annotations

from pathlib import Path

from collective_mindgraph.desktop.contracts import EngineSettings
from collective_mindgraph.desktop.http_transport import (
    EngineClientError,
    LocalHttpTransport,
    is_engine_offline_error,
)
from collective_mindgraph.desktop.ui.workspaces.capture import (
    CaptureWorkspace,
    _remove_uploaded_spool,
)


class _Response:
    status = 202
    reason = "Accepted"

    def read(self) -> bytes:
        return b'{"id":"job-1","status":"pending"}'


class _Connection:
    latest: _Connection | None = None

    def __init__(self, host: str, port: int | None, *, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.target = ""
        self.headers: dict[str, str] = {}
        self.send_sizes: list[int] = []
        self.closed = False
        _Connection.latest = self

    def putrequest(self, method: str, target: str) -> None:
        assert method == "POST"
        self.target = target

    def putheader(self, name: str, value: str) -> None:
        self.headers[name] = value

    def endheaders(self) -> None:
        return None

    def send(self, data: bytes | bytearray) -> None:
        self.send_sizes.append(len(data))

    def getresponse(self) -> _Response:
        return _Response()

    def close(self) -> None:
        self.closed = True


def test_multipart_upload_streams_large_files_in_bounded_chunks(monkeypatch, tmp_path: Path):
    upload = tmp_path / "large.wav"
    upload.write_bytes(b"a" * (2 * 1024 * 1024 + 17))
    monkeypatch.setattr(
        "collective_mindgraph.desktop.http_transport.http.client.HTTPConnection",
        _Connection,
    )
    transport = LocalHttpTransport(
        EngineSettings(base_url="http://127.0.0.1:8080", timeout_seconds=4.0)
    )

    payload = transport.multipart(
        "/api/v1/meetings/4/recordings",
        upload,
        {"language": "tr", "quality_mode": "balanced"},
    )

    connection = _Connection.latest
    assert connection is not None
    assert payload == {"id": "job-1", "status": "pending"}
    assert connection.target == "/api/v1/meetings/4/recordings"
    assert connection.host == "127.0.0.1"
    assert connection.port == 8080
    assert connection.timeout == 4.0
    assert connection.closed
    assert connection.send_sizes[1:-1] == [1024 * 1024, 1024 * 1024, 17]
    assert sum(connection.send_sizes) == int(connection.headers["Content-Length"])


def test_only_connection_refusal_is_classified_as_engine_offline():
    assert is_engine_offline_error(
        EngineClientError("engine_offline", "unavailable", retryable=True)
    )
    assert not is_engine_offline_error(
        EngineClientError("engine_timeout", "slow", retryable=True)
    )
    assert not is_engine_offline_error(
        EngineClientError("validation_error", "invalid", status_code=422)
    )
    assert not is_engine_offline_error(RuntimeError("unexpected"))


def test_successful_fallback_upload_removes_its_spool_file(tmp_path: Path):
    spool = tmp_path / "capture.wav"
    spool.write_bytes(b"pcm")

    assert _remove_uploaded_spool(spool) is None
    assert not spool.exists()


def test_live_fallback_marks_only_the_spool_for_cleanup(tmp_path: Path):
    spool = tmp_path / "capture.wav"
    calls: list[tuple[Path, int | None, bool]] = []

    class _Workspace:
        _live_meeting_id = 17

        def process_path(
            self,
            source: Path,
            *,
            meeting_id: int | None,
            cleanup_source_on_success: bool,
        ) -> None:
            calls.append((source, meeting_id, cleanup_source_on_success))

    CaptureWorkspace._live_fallback(_Workspace(), str(spool))  # type: ignore[arg-type]

    assert calls == [(spool, 17, True)]
