import json
from urllib.error import URLError

from collective_mindgraph_desktop.transcription import (
    RealtimeBackendTranscriptionConfig,
    RealtimeBackendTranscriptionService,
)


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_realtime_backend_transcription_service_posts_file_and_extracts_dialogue(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"RIFF....WAVEfmt ")
    captured: dict[str, object] = {}

    def fake_opener(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeHTTPResponse(
            {
                "transcript": {
                    "conversation_id": "conv_123",
                    "segments": [
                        {"speaker": "Speaker_1", "corrected_text": "Hello there."},
                        {"speaker": "Speaker_2", "corrected_text": "Hi."},
                    ],
                },
                "raw_text_output": "[00:00.0] Speaker_1: hello there",
                "corrected_text_output": "[00:00.0] Speaker_1: Hello there.",
                "speaker_stats": [
                    {"speaker": "Speaker_1"},
                    {"speaker": "Speaker_2"},
                ],
            }
        )

    service = RealtimeBackendTranscriptionService(
        config=RealtimeBackendTranscriptionConfig(
            base_url="http://127.0.0.1:8080",
            language="en",
            request_timeout_seconds=90,
        ),
        request_opener=fake_opener,
    )

    result = service.transcribe_file(audio_path)

    assert result.text == "Speaker_1: Hello there.\nSpeaker_2: Hi."
    assert result.audio_path == str(audio_path.resolve())
    assert result.conversation_id == "conv_123"
    assert result.speaker_count == 2

    request = captured["request"]
    assert request.full_url == "http://127.0.0.1:8080/transcribe/file"
    assert captured["timeout"] == 90
    assert b'name="upload"' in request.data
    assert b'name="language"' in request.data
    assert b"sample.wav" in request.data


def test_realtime_backend_transcription_service_reports_connection_failures(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"RIFF....WAVEfmt ")

    def failing_opener(_request, timeout=None):
        raise URLError("connection refused")

    service = RealtimeBackendTranscriptionService(
        config=RealtimeBackendTranscriptionConfig(base_url="http://127.0.0.1:8080"),
        request_opener=failing_opener,
    )

    try:
        service.transcribe_file(audio_path)
    except ValueError as exc:
        assert "not reachable" in str(exc)
    else:
        raise AssertionError("Expected connection failure to be surfaced.")
