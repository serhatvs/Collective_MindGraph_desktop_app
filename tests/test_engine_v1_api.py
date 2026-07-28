import time
import wave
from io import BytesIO

from fastapi.testclient import TestClient

from collective_mindgraph.domain import MeetingId
from collective_mindgraph.engine.main import create_app
from collective_mindgraph.engine.settings import EngineSettings


def _settings(tmp_path) -> EngineSettings:
    return EngineSettings(
        data_dir=tmp_path / "engine-data",
        temp_dir=tmp_path / "engine-temp",
        database_path=tmp_path / "collective_mindgraph.sqlite3",
        asr_provider="mock",
        vad_provider="energy",
        diarizer_provider="fallback",
        embedding_provider="mock",
        llm_provider="disabled",
    )


def _wav_bytes() -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16_000)
        recording.writeframes(b"\x00\x00" * 1_600)
    return output.getvalue()


def test_v1_meeting_dashboard_and_health_flow(tmp_path):
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["status"] == "degraded"
        assert health.json()["transcription"] == "degraded"
        assert health.json()["embeddings"] == "disabled"
        assert health.json()["database_path"].endswith("collective_mindgraph.sqlite3")

        created = client.post(
            "/api/v1/meetings",
            json={"title": "Architecture Review", "input_device": "MIC-1"},
        )
        assert created.status_code == 201
        meeting_id = created.json()["id"]
        assert created.json()["status"] == "draft"

        listed = client.get("/api/v1/meetings", params={"query": "Architecture"})
        assert listed.status_code == 200
        assert listed.json()["total"] == 1
        assert listed.json()["items"][0]["id"] == meeting_id

        dashboard = client.get("/api/v1/dashboard")
        assert dashboard.status_code == 200
        assert dashboard.json()["total_meetings"] == 1
        assert dashboard.json()["recent_meetings"][0]["title"] == "Architecture Review"

        archived = client.patch(
            f"/api/v1/meetings/{meeting_id}",
            json={"title": "Architecture Review Updated", "archived": True},
        )
        assert archived.status_code == 200
        assert archived.json()["title"] == "Architecture Review Updated"
        assert archived.json()["status"] == "archived"


def test_v1_pagination_and_typed_validation_errors(tmp_path):
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        invalid = client.post("/api/v1/meetings", json={"title": ""})
        assert invalid.status_code == 422
        assert set(invalid.json()) == {
            "code",
            "message",
            "details",
            "retryable",
        }
        assert invalid.json()["retryable"] is False

        for index in range(3):
            response = client.post(
                "/api/v1/meetings",
                json={"title": f"Meeting {index}"},
            )
            assert response.status_code == 201

        first = client.get("/api/v1/meetings", params={"limit": 2}).json()
        assert len(first["items"]) == 2
        assert first["next_cursor"]
        second = client.get(
            "/api/v1/meetings",
            params={"limit": 2, "cursor": first["next_cursor"]},
        ).json()
        assert len(second["items"]) == 1
        assert second["next_cursor"] is None


def test_openapi_contains_the_complete_product_surface(tmp_path):
    app = create_app(_settings(tmp_path))
    paths = set(app.openapi()["paths"])

    assert {
        "/api/v1/dashboard",
        "/api/v1/meetings",
        "/api/v1/meetings/{meeting_id}",
        "/api/v1/meetings/{meeting_id}/recordings",
        "/api/v1/meetings/{meeting_id}/transcript",
        "/api/v1/transcript-segments/{segment_id}",
        "/api/v1/insights",
        "/api/v1/insights/{insight_id}/review",
        "/api/v1/memory/search",
        "/api/v1/memory/ask",
        "/api/v1/knowledge/nodes",
        "/api/v1/knowledge/edges",
        "/api/v1/jobs",
        "/api/v1/jobs/{job_id}",
        "/api/v1/jobs/{job_id}/cancel",
        "/api/v1/jobs/{job_id}/retry",
        "/api/v1/settings",
        "/api/v1/health",
        "/api/v1/import",
        "/api/v1/export",
        "/transcribe/file",
        "/transcript/{conversation_id}",
        "/summary/{conversation_id}",
        "/quality/{conversation_id}",
        "/query",
        "/reason",
        "/memory/ask",
        "/jobs",
        "/health",
    } <= paths


def test_recording_upload_persists_stable_source_identity(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        meeting_id = client.post(
            "/api/v1/meetings",
            json={"title": "Uploaded recording"},
        ).json()["id"]

        response = client.post(
            f"/api/v1/meetings/{meeting_id}/recordings",
            files={"upload": ("sample.wav", _wav_bytes(), "audio/wav")},
        )

        assert response.status_code == 202
        assert response.json()["recording_id"]
        job_id = response.json()["id"]
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            job = client.get(f"/api/v1/jobs/{job_id}").json()
            if job["status"] in {"succeeded", "failed", "cancelled"}:
                break
            time.sleep(0.02)
        assert job["status"] == "succeeded"
        assert job["result_transcript_id"] is not None
        recordings = client.app.state.engine_context.recordings.list_for_meeting(
            MeetingId(meeting_id)
        )
        assert len(recordings) == 1
        assert recordings[0].source_uri.startswith("managed://")
        assert recordings[0].storage_status.value == "deleted"
        managed_path = client.app.state.engine_context.recording_storage.resolve(
            recordings[0].source_uri
        )
        assert not managed_path.exists()


def test_legacy_health_contract_remains_available(tmp_path):
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert "asr_provider" in payload
