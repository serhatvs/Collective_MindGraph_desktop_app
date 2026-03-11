import json

from collective_mindgraph_desktop.transcription import (
    AmazonNovaTranscriptionConfig,
    AmazonNovaTranscriptionSettingsStore,
    RealtimeBackendTranscriptionConfig,
    RealtimeBackendTranscriptionSettingsStore,
)


def test_transcription_settings_store_round_trips_config(tmp_path):
    settings_path = tmp_path / "transcription_settings.json"
    store = AmazonNovaTranscriptionSettingsStore(settings_path)
    config = AmazonNovaTranscriptionConfig(
        model_id="us.amazon.nova-lite-v1:0",
        region_name="us-east-1",
        max_tokens=2048,
        temperature=0.2,
        top_p=0.8,
        prompt_text="Return only transcript text.",
    )

    saved_path = store.save(config)
    loaded = store.load()

    assert saved_path == settings_path.resolve()
    assert loaded == config
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert payload["region_name"] == "us-east-1"
    assert payload["model_id"] == "us.amazon.nova-lite-v1:0"


def test_transcription_settings_store_falls_back_to_env_defaults_when_missing(tmp_path):
    settings_path = tmp_path / "missing_transcription_settings.json"
    store = AmazonNovaTranscriptionSettingsStore(settings_path)

    loaded = store.load()

    assert isinstance(loaded, AmazonNovaTranscriptionConfig)
    assert loaded.model_id


def test_realtime_backend_settings_store_round_trips_config(tmp_path):
    settings_path = tmp_path / "transcription_settings.json"
    store = RealtimeBackendTranscriptionSettingsStore(settings_path)
    config = RealtimeBackendTranscriptionConfig(
        base_url="http://127.0.0.1:8080",
        language="tr",
        request_timeout_seconds=180,
    )

    saved_path = store.save(config)
    loaded = store.load()

    assert saved_path == settings_path.resolve()
    assert loaded == config
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert payload["base_url"] == "http://127.0.0.1:8080"


def test_realtime_backend_settings_store_ignores_old_nova_payload_shape(tmp_path):
    settings_path = tmp_path / "transcription_settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "model_id": "us.amazon.nova-2-lite-v1:0",
                "region_name": "us-east-1",
                "max_tokens": 2048,
            }
        ),
        encoding="utf-8",
    )
    store = RealtimeBackendTranscriptionSettingsStore(settings_path)

    loaded = store.load()

    assert isinstance(loaded, RealtimeBackendTranscriptionConfig)
    assert loaded.base_url
