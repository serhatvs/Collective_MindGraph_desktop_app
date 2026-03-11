from pathlib import Path

from collective_mindgraph_desktop.transcription import (
    AmazonNovaTranscriptionConfig,
    AmazonNovaTranscriptionService,
    DIRECT_AUDIO_UPLOAD_LIMIT_BYTES,
)


class FakeBedrockClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def test_transcription_service_builds_converse_request_for_wav(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"RIFF....WAVEfmt ")
    fake_client = FakeBedrockClient(
        {
            "output": {
                "message": {
                    "content": [
                        {"text": "Hello world."},
                    ]
                }
            }
        }
    )

    service = AmazonNovaTranscriptionService(
        config=AmazonNovaTranscriptionConfig(region_name="us-west-2"),
        client=fake_client,
    )
    result = service.transcribe_file(audio_path)

    assert result.text == "Hello world."
    assert result.audio_path == str(audio_path.resolve())
    assert fake_client.calls
    request = fake_client.calls[0]
    assert request["modelId"] == "us.amazon.nova-2-lite-v1:0"
    assert request["messages"][0]["content"][0]["audio"]["format"] == "wav"
    assert request["messages"][0]["content"][0]["audio"]["source"]["bytes"] == audio_path.read_bytes()


def test_transcription_service_rejects_unsupported_audio_format(tmp_path):
    audio_path = tmp_path / "sample.txt"
    audio_path.write_text("not audio", encoding="utf-8")
    service = AmazonNovaTranscriptionService(
        config=AmazonNovaTranscriptionConfig(region_name="us-west-2"),
        client=FakeBedrockClient({}),
    )

    try:
        service.transcribe_file(audio_path)
    except ValueError as exc:
        assert "Unsupported audio format" in str(exc)
    else:
        raise AssertionError("Expected unsupported format error.")


def test_transcription_service_rejects_files_over_direct_upload_limit(tmp_path, monkeypatch):
    audio_path = tmp_path / "large.wav"
    audio_path.write_bytes(b"0")

    service = AmazonNovaTranscriptionService(
        config=AmazonNovaTranscriptionConfig(region_name="us-west-2"),
        client=FakeBedrockClient({}),
    )

    original_stat = Path.stat

    def fake_stat(self, *args, **kwargs):
        stat_result = original_stat(self, *args, **kwargs)
        if self == audio_path:
            return stat_result.__class__(
                (
                    stat_result.st_mode,
                    stat_result.st_ino,
                    stat_result.st_dev,
                    stat_result.st_nlink,
                    stat_result.st_uid,
                    stat_result.st_gid,
                    DIRECT_AUDIO_UPLOAD_LIMIT_BYTES + 1,
                    stat_result.st_atime,
                    stat_result.st_mtime,
                    stat_result.st_ctime,
                )
            )
        return stat_result

    monkeypatch.setattr(Path, "stat", fake_stat)

    try:
        service.transcribe_file(audio_path)
    except ValueError as exc:
        assert "25 MB direct upload limit" in str(exc)
    else:
        raise AssertionError("Expected file size limit error.")
