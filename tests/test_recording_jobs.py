from __future__ import annotations

import asyncio
import threading
import time

from fastapi.testclient import TestClient

from collective_mindgraph.domain import (
    MeetingId,
    Recording,
    RecordingId,
    RecordingStorageStatus,
)
from collective_mindgraph.engine.main import create_app
from collective_mindgraph.engine.settings import EngineSettings
from collective_mindgraph.infrastructure.transcription.recording_processor import (
    RecordingProcessor,
)
from test_engine_v1_api import _wav_bytes


def _settings(tmp_path) -> EngineSettings:
    return EngineSettings(
        data_dir=tmp_path / "data",
        temp_dir=tmp_path / "temp",
        database_path=tmp_path / "data" / "collective_mindgraph.sqlite3",
        asr_provider="mock",
        vad_provider="energy",
        diarizer_provider="fallback",
        embedding_provider="disabled",
        llm_provider="disabled",
    )


def _wait_for_terminal(client: TestClient, job_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        payload = client.get(f"/api/v1/jobs/{job_id}").json()
        if payload["status"] in {"succeeded", "failed", "cancelled"}:
            return payload
        time.sleep(0.02)
    raise AssertionError("processing job did not reach a terminal state")


def _upload(client: TestClient, meeting_id: int):
    return client.post(
        f"/api/v1/meetings/{meeting_id}/recordings",
        files={"upload": ("sample.wav", _wav_bytes(), "audio/wav")},
    )


def test_running_job_is_actually_cancelled_and_retry_keeps_lineage(
    tmp_path,
    monkeypatch,
):
    started = threading.Event()

    async def slow_process(self, *_args, **_kwargs):
        started.set()
        await asyncio.sleep(30)

    monkeypatch.setattr(RecordingProcessor, "process_audio_path", slow_process)
    with TestClient(create_app(_settings(tmp_path))) as client:
        meeting_id = client.post(
            "/api/v1/meetings",
            json={"title": "Cancellation"},
        ).json()["id"]
        queued = _upload(client, meeting_id)
        assert queued.status_code == 202
        original = queued.json()
        assert started.wait(2)

        cancelled = client.post(f"/api/v1/jobs/{original['id']}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        assert cancelled.json()["retryable"] is True
        recording = client.app.state.engine_context.recordings.get(
            RecordingId(original["recording_id"])
        )
        assert recording is not None
        assert recording.storage_status is RecordingStorageStatus.RETAINED
        assert client.app.state.engine_context.recording_storage.resolve(
            recording.source_uri
        ).is_file()

        retried = client.post(f"/api/v1/jobs/{original['id']}/retry")
        assert retried.status_code == 202
        assert retried.json()["parent_job_id"] == original["id"]
        assert retried.json()["recording_id"] == original["recording_id"]
        client.post(f"/api/v1/jobs/{retried.json()['id']}/cancel")


def test_failed_job_retains_audio_and_reports_retryable_error(tmp_path, monkeypatch):
    async def failing_process(self, *_args, **_kwargs):
        raise RuntimeError("simulated ASR failure")

    monkeypatch.setattr(RecordingProcessor, "process_audio_path", failing_process)
    with TestClient(create_app(_settings(tmp_path))) as client:
        meeting_id = client.post(
            "/api/v1/meetings",
            json={"title": "Failure"},
        ).json()["id"]
        queued = _upload(client, meeting_id).json()
        failed = _wait_for_terminal(client, str(queued["id"]))

        assert failed["status"] == "failed"
        assert failed["retryable"] is True
        assert "simulated ASR failure" in str(failed["error"])
        recording = client.app.state.engine_context.recordings.get(
            RecordingId(str(failed["recording_id"]))
        )
        assert recording is not None
        assert recording.storage_status is RecordingStorageStatus.RETAINED


def test_restart_marks_interrupted_job_as_retryable_failure(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        context = client.app.state.engine_context
        meeting_id = MeetingId(
            client.post("/api/v1/meetings", json={"title": "Restart"}).json()["id"]
        )
        recording_id = RecordingId("restart-recording")
        path, source_uri = context.recording_storage.allocate(
            meeting_id,
            recording_id,
            "restart.wav",
        )
        path.write_bytes(_wav_bytes())
        recording = Recording(
            id=recording_id,
            meeting_id=meeting_id,
            source_uri=source_uri,
            duration_seconds=None,
            captured_at=context.get_meeting(meeting_id).created_at,
        )
        context.recordings.save(recording)
        interrupted = context.process_recording.create_job(
            meeting_id=meeting_id,
            recording_id=recording_id,
        )

    with TestClient(create_app(settings)) as restarted:
        recovered = restarted.get(f"/api/v1/jobs/{interrupted.id}").json()
        assert recovered["status"] == "failed"
        assert recovered["error"] == "engine_restarted"
        assert recovered["retryable"] is True
