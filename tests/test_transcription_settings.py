import json

from collective_mindgraph_desktop.transcription import (
    RealtimeBackendTranscriptionConfig,
    RealtimeBackendTranscriptionSettingsStore,
)
from collective_mindgraph_desktop.ui.widgets import TranscriptionSettingsDialog


def test_realtime_backend_settings_store_round_trips_config(tmp_path):
    settings_path = tmp_path / "transcription_settings.json"
    store = RealtimeBackendTranscriptionSettingsStore(settings_path)
    config = RealtimeBackendTranscriptionConfig(
        base_url="http://127.0.0.1:9091",
        language="tr",
        transcription_quality_mode="balanced",
        session_glossary_terms=["Collective MindGraph", "ozel terim"],
        user_hotwords=["Serhat"],
        request_timeout_seconds=180,
        stream_live_transcription=False,
        stream_flush_interval_ms=900,
        audio_input_device_id="{device-id}",
        audio_input_device_label="USB Microphone",
        auto_stop_enabled=False,
        auto_stop_min_speech_seconds=0.4,
        auto_stop_silence_seconds=1.5,
        auto_stop_silence_threshold=0.02,
        wake_trigger_enabled=False,
        wake_phrase="command wake",
        shutdown_phrase="command shut",
        wake_cooldown_seconds=2.5,
        embeddings_enabled=False,
        embedding_provider="sentence_transformers",
        embedding_model_path="models/multilingual-e5-base",
        embedding_dimension=768,
        allow_remote_model_download=True,
    )

    saved_path = store.save(config)
    loaded = store.load()

    assert saved_path == settings_path.resolve()
    assert loaded == config
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert payload["base_url"] == "http://127.0.0.1:9091"
    assert payload["audio_input_device_id"] == "{device-id}"
    assert payload["audio_input_device_label"] == "USB Microphone"
    assert payload["stream_live_transcription"] is False
    assert payload["wake_phrase"] == "command wake"
    assert payload["auto_stop_silence_seconds"] == 1.5


def test_realtime_backend_settings_store_ignores_stale_payload_shape(tmp_path):
    settings_path = tmp_path / "transcription_settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "model_id": "stale-model-id",
                "region_name": "stale-region",
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


def test_transcription_settings_dialog_preserves_auto_stop_silence(qtbot):
    config = RealtimeBackendTranscriptionConfig(auto_stop_silence_seconds=2.75)
    dialog = TranscriptionSettingsDialog(config)
    qtbot.addWidget(dialog)

    dialog.auto_stop_silence_spin.setValue(3.5)

    assert dialog.config().auto_stop_silence_seconds == 3.5


def test_transcription_settings_dialog_preserves_hidden_config_fields(qtbot):
    config = RealtimeBackendTranscriptionConfig(
        transcription_quality_mode="bad_mic_recovery",
        session_glossary_terms=["Collective MindGraph", "proje terimi"],
        user_hotwords=["ozel isim"],
        embedding_provider="sentence_transformers",
        embedding_dimension=1024,
        allow_remote_model_download=True,
    )
    dialog = TranscriptionSettingsDialog(config)
    qtbot.addWidget(dialog)

    updated = dialog.config()

    assert updated.transcription_quality_mode == "bad_mic_recovery"
    assert updated.session_glossary_terms == ["Collective MindGraph", "proje terimi"]
    assert updated.user_hotwords == ["ozel isim"]
    assert updated.embedding_provider == "sentence_transformers"
    assert updated.embedding_dimension == 1024
    assert updated.allow_remote_model_download is True
