import json

from collective_mindgraph_desktop.transcription import (
    AmazonNovaTranscriptionConfig,
    AmazonNovaTranscriptionSettingsStore,
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
