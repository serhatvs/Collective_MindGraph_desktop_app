from __future__ import annotations

from fastapi.testclient import TestClient

from collective_mindgraph.application import GetDashboard
from collective_mindgraph.engine.main import create_app
from collective_mindgraph.engine.settings import EngineSettings


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


def test_runtime_settings_publish_new_bundle_only_after_validation(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        context = client.app.state.engine_context
        original_bundle = context.runtime.snapshot()
        original_preferences = context.preferences.load()

        invalid = client.put(
            "/api/v1/settings",
            json={"asr_provider": "cloud-provider"},
        )

        assert invalid.status_code == 422
        assert invalid.json()["code"] == "invalid_request"
        assert context.runtime.snapshot() is original_bundle
        assert context.settings.asr_provider == "mock"
        assert context.preferences.load() == original_preferences

        updated = client.put(
            "/api/v1/settings",
            json={"language": "en", "retain_raw_audio": True},
        )
        assert updated.status_code == 200
        assert context.runtime.snapshot() is not original_bundle
        assert original_bundle.settings.default_language != "en"
        assert context.runtime.snapshot().settings.default_language == "en"
        assert context.settings.retain_raw_audio is True


def test_invalid_embedding_path_rolls_back_runtime_and_preferences(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        context = client.app.state.engine_context
        original_bundle = context.runtime.snapshot()

        response = client.put(
            "/api/v1/settings",
            json={"embedding_provider": "sentence_transformer"},
        )

        assert response.status_code == 422
        assert context.runtime.snapshot() is original_bundle
        assert context.settings.embedding_provider == "disabled"
        assert context.preferences.load().get("embedding_provider") is None


def test_invalid_transcription_quality_rolls_back_runtime_and_preferences(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        context = client.app.state.engine_context
        original_bundle = context.runtime.snapshot()

        response = client.put(
            "/api/v1/settings",
            json={"transcription_quality": "unbounded"},
        )

        assert response.status_code == 422
        assert context.runtime.snapshot() is original_bundle
        assert context.settings.transcription_quality_mode == "max_quality"
        assert context.preferences.load().get("transcription_quality_mode") is None


def test_health_uses_actual_mock_and_disabled_adapter_state(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        payload = client.get("/api/v1/health").json()

    assert payload["status"] == "degraded"
    assert payload["transcription"] == "degraded"
    assert payload["embeddings"] == "disabled"
    assert payload["local_llm"] == "disabled"


def test_unexpected_v1_error_is_typed_and_hides_internal_detail(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        GetDashboard,
        "__call__",
        lambda _self: (_ for _ in ()).throw(RuntimeError("secret internal detail")),
    )
    with TestClient(
        create_app(_settings(tmp_path)),
        raise_server_exceptions=False,
    ) as client:
        response = client.get("/api/v1/dashboard")

    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "The local engine could not complete the request.",
        "details": {},
        "retryable": True,
    }
    assert "secret internal detail" not in response.text


def test_openapi_routes_reference_typed_error_envelopes(tmp_path):
    schema = create_app(_settings(tmp_path)).openapi()
    responses = schema["paths"]["/api/v1/meetings/{meeting_id}"]["get"]["responses"]

    assert responses["404"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ErrorResponse"
    )
    assert responses["500"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ErrorResponse"
    )
