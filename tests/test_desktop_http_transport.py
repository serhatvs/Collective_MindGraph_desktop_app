from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QSettings

from collective_mindgraph.desktop.contracts import (
    EngineSettings,
    MeetingTranscript,
    ProcessingJob,
)
from collective_mindgraph.desktop.http_transport import (
    EngineClientError,
    LocalHttpTransport,
    is_engine_offline_error,
)
from collective_mindgraph.desktop.language_catalog import LanguageCatalog
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
    assert not is_engine_offline_error(EngineClientError("engine_timeout", "slow", retryable=True))
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


def test_successful_capture_fallback_upload_cleans_spool_after_transcript_load(
    qtbot,
    tmp_path: Path,
):
    now = datetime.now(tz=UTC)
    job = ProcessingJob(
        id="job-17",
        meeting_id=17,
        recording_id="recording-17",
        parent_job_id=None,
        result_transcript_id=23,
        kind="transcription",
        status="succeeded",
        progress=100,
        message="complete",
        error=None,
        retryable=False,
        created_at=now,
        updated_at=now,
    )
    transcript = MeetingTranscript(
        id=23,
        meeting_id=17,
        conversation_id="conversation-17",
        provider="mock",
        language="tr",
        raw_text="ham",
        corrected_text="düzeltilmiş",
        segments=(),
    )

    class _Client:
        settings = EngineSettings()

        def ingest_recording(self, meeting_id, source, preferences):
            assert meeting_id == 17
            assert source.name == "capture.wav"
            return job

        def wait_for_job(self, job_id):
            assert job_id == job.id
            return job

        def get_transcript(self, meeting_id):
            assert meeting_id == 17
            return transcript

    class _ImmediatePresenter:
        def submit(self, operation, *, succeeded, failed):
            try:
                result = operation()
            except Exception as error:
                failed(error)
            else:
                succeeded(result)

    settings = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    catalog = LanguageCatalog(settings)
    workspace = CaptureWorkspace(
        _Client(),  # type: ignore[arg-type]
        catalog,
        _ImmediatePresenter(),  # type: ignore[arg-type]
    )
    qtbot.addWidget(workspace)
    spool = tmp_path / "capture.wav"
    spool.write_bytes(b"pcm")

    workspace.process_path(spool, meeting_id=17, cleanup_source_on_success=True)

    assert not spool.exists()
    assert workspace._transcript.toPlainText() == "düzeltilmiş"
