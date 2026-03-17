import json
from urllib.error import URLError

from collective_mindgraph_desktop.transcription import (
    BackendHealthStatus,
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
    captured_requests: list[object] = []

    def fake_opener(request, timeout):
        captured_requests.append((request, timeout))
        if request.full_url.endswith("/summary/conv_123"):
            return FakeHTTPResponse(
                {
                    "conversation_id": "conv_123",
                    "summary": "Short summary.",
                    "topics": [{"label": "Greeting", "start": 0.0, "end": 1.0}],
                    "action_items": ["Reply politely"],
                    "decisions": ["Continue"],
                }
            )
        if request.full_url.endswith("/quality/conv_123"):
            return FakeHTTPResponse(
                {
                    "conversation_id": "conv_123",
                    "segment_count": 2,
                    "speaker_count": 2,
                    "unresolved_segments": 0,
                    "overlap_ratio": 0.0,
                    "avg_asr_confidence": 0.9,
                    "avg_speaker_confidence": 1.0,
                    "word_timing_coverage": 1.0,
                    "corrected_change_ratio": 0.1,
                    "topic_count": 1,
                    "action_item_count": 1,
                    "decision_count": 1,
                    "question_count": 0,
                    "summary_present": True,
                    "warnings": [],
                }
            )
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
    assert result.summary == "Short summary."
    assert result.action_items == ["Reply politely"]
    assert result.decisions == ["Continue"]

    request, timeout = captured_requests[0]
    assert request.full_url == "http://127.0.0.1:8080/transcribe/file"
    assert timeout == 90
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


def test_realtime_backend_transcription_service_fetches_health():
    def fake_opener(request, timeout):
        return FakeHTTPResponse(
            {
                "status": "ok",
                "app_name": "Collective MindGraph Realtime Backend",
                "vad_provider": "silero",
                "asr_provider": "auto",
                "asr_provider_resolved": "faster_whisper",
                "asr_fallback_provider": "mock",
                "diarizer_provider": "pyannote",
                "llm_provider": "bedrock_auto_local",
                "llm_provider_resolved": "lmstudio",
                "llm_fallback_provider": "mock",
            }
        )

    service = RealtimeBackendTranscriptionService(
        config=RealtimeBackendTranscriptionConfig(base_url="http://127.0.0.1:8080"),
        request_opener=fake_opener,
    )

    result = service.fetch_health()

    assert isinstance(result, BackendHealthStatus)
    assert result.status == "ok"
    assert result.asr_provider_resolved == "faster_whisper"
    assert result.llm_provider_resolved == "lmstudio"


def test_realtime_backend_transcription_service_parses_stream_final_payload(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"RIFF....WAVEfmt ")
    requested_urls: list[str] = []

    def fake_opener(request, timeout):
        requested_urls.append(request.full_url)
        if request.full_url.endswith("/quality/conv_stream"):
            return FakeHTTPResponse(
                {
                    "conversation_id": "conv_stream",
                    "segment_count": 1,
                    "speaker_count": 1,
                    "unresolved_segments": 0,
                    "overlap_ratio": 0.0,
                    "avg_asr_confidence": 0.92,
                    "avg_speaker_confidence": 1.0,
                    "word_timing_coverage": 1.0,
                    "corrected_change_ratio": 0.05,
                    "topic_count": 1,
                    "action_item_count": 1,
                    "decision_count": 1,
                    "question_count": 0,
                    "summary_present": True,
                    "warnings": [],
                }
            )
        raise AssertionError(f"Unexpected URL requested: {request.full_url}")

    service = RealtimeBackendTranscriptionService(
        config=RealtimeBackendTranscriptionConfig(base_url="http://127.0.0.1:8080"),
        request_opener=fake_opener,
    )

    result = service.result_from_payload(
        {
            "event": "final_transcript",
            "conversation_id": "conv_stream",
            "segments": [
                {"speaker": "Speaker_1", "corrected_text": "Live final result.", "raw_text": "live final result"}
            ],
            "summary": "Live summary.",
            "topics": [{"label": "Live", "start": 0.0, "end": 1.0}],
            "action_items": ["Keep testing"],
            "decisions": ["Continue streaming"],
            "corrected_text_output": "Speaker_1: Live final result.",
            "speaker_stats": [{"speaker": "Speaker_1", "segment_count": 1}],
            "is_final": True,
        },
        audio_path,
    )

    assert result.text == "Speaker_1: Live final result."
    assert result.summary == "Live summary."
    assert result.action_items == ["Keep testing"]
    assert result.decisions == ["Continue streaming"]
    assert result.quality_report is not None
    assert requested_urls == ["http://127.0.0.1:8080/quality/conv_stream"]


def test_realtime_backend_transcription_service_builds_stream_update(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"RIFF....WAVEfmt ")
    service = RealtimeBackendTranscriptionService(
        config=RealtimeBackendTranscriptionConfig(base_url="http://127.0.0.1:8080")
    )

    update = service.stream_update_from_payload(
        {
            "event": "partial_transcript",
            "conversation_id": "conv_partial",
            "segments": [{"speaker": "Speaker_1", "corrected_text": "Partial line."}],
            "corrected_text_output": "Speaker_1: Partial line.",
            "speaker_stats": [{"speaker": "Speaker_1"}],
            "is_final": False,
        },
        audio_path,
    )

    assert update.conversation_id == "conv_partial"
    assert update.text == "Speaker_1: Partial line."
    assert update.speaker_count == 1
    assert update.is_final is False
