import json

from collective_mindgraph_desktop.transcription import (
    RealtimeBackendTranscriptionConfig,
    RealtimeBackendTranscriptionSettingsStore,
)


def test_realtime_backend_settings_store_round_trips_config(tmp_path):
    settings_path = tmp_path / "transcription_settings.json"
    store = RealtimeBackendTranscriptionSettingsStore(settings_path)
    config = RealtimeBackendTranscriptionConfig(
        base_url="http://127.0.0.1:8080",
        language="tr",
        request_timeout_seconds=180,
        stream_live_transcription=True,
        stream_flush_interval_ms=900,
        audio_input_device_id="{device-id}",
        audio_input_device_label="USB Microphone",
        auto_stop_enabled=True,
        auto_stop_min_speech_seconds=0.4,
        auto_stop_silence_seconds=1.5,
        auto_stop_silence_threshold=0.02,
        wake_trigger_enabled=True,
        wake_phrase="command wake",
        shutdown_phrase="command shut",
        wake_cooldown_seconds=2.5,
    )

    saved_path = store.save(config)
    loaded = store.load()

    assert saved_path == settings_path.resolve()
    assert loaded == config
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert payload["base_url"] == "http://127.0.0.1:8080"
    assert payload["audio_input_device_id"] == "{device-id}"
    assert payload["audio_input_device_label"] == "USB Microphone"
    assert payload["stream_live_transcription"] is True
    assert payload["wake_phrase"] == "command wake"
    assert payload["auto_stop_silence_seconds"] == 1.5


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
    assert loaded.audio_input_device_id is None
    assert loaded.wake_phrase
    assert loaded.shutdown_phrase
