import sys
import tempfile
import types
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
import starlette.formparsers as formparsers
import starlette.requests as requests_module

python_multipart = types.ModuleType("python_multipart")
python_multipart.__version__ = "0.0.20"
sys.modules.setdefault("python_multipart", python_multipart)

from app.api.routes import router
from app.models import ConversationTranscript, QualityReport, TopicSegment, TranscriptSegment


def _parse_options_header(value: str | bytes | None) -> tuple[bytes, dict[bytes, bytes]]:
    if value is None:
        return b"", {}
    if isinstance(value, str):
        raw_value = value.encode("latin-1")
    else:
        raw_value = value
    parts = [part.strip() for part in raw_value.split(b";") if part.strip()]
    if not parts:
        return b"", {}
    options: dict[bytes, bytes] = {}
    for part in parts[1:]:
        if b"=" not in part:
            continue
        key, item_value = part.split(b"=", 1)
        options[key.strip().lower()] = item_value.strip().strip(b'"')
    return parts[0].lower(), options


class _FakeQuerystringParser:
    def __init__(self, callbacks: dict[str, object]) -> None:
        self._callbacks = callbacks
        self._buffer = bytearray()
        self._parsed = False

    def write(self, data: bytes) -> None:
        self._buffer.extend(data)
        if not self._parsed:
            self._emit_fields()

    def _emit_fields(self) -> None:
        self._parsed = True
        if not self._buffer:
            self._callbacks["on_end"]()
            return
        for field in bytes(self._buffer).split(b"&"):
            if not field:
                continue
            name, _, value = field.partition(b"=")
            self._callbacks["on_field_start"]()
            self._callbacks["on_field_name"](name, 0, len(name))
            self._callbacks["on_field_data"](value, 0, len(value))
            self._callbacks["on_field_end"]()
        self._callbacks["on_end"]()

    def finalize(self) -> None:
        if not self._parsed:
            self._emit_fields()


class _FakeMultipartParser:
    def __init__(self, boundary: str | bytes, callbacks: dict[str, object]) -> None:
        self._boundary = boundary.encode("latin-1") if isinstance(boundary, str) else boundary
        self._callbacks = callbacks
        self._buffer = bytearray()
        self._parsed = False

    def write(self, data: bytes) -> None:
        self._buffer.extend(data)
        if not self._parsed and (b"--" + self._boundary + b"--") in self._buffer:
            self._emit_parts()

    def _emit_parts(self) -> None:
        self._parsed = True
        boundary_marker = b"--" + self._boundary
        for part in bytes(self._buffer).split(boundary_marker):
            candidate = part.strip()
            if not candidate or candidate == b"--":
                continue
            if candidate.endswith(b"--"):
                candidate = candidate[:-2]
            candidate = candidate.strip(b"\r\n")
            header_blob, _, content = candidate.partition(b"\r\n\r\n")
            self._callbacks["on_part_begin"]()
            for header in header_blob.split(b"\r\n"):
                if not header:
                    continue
                name, _, value = header.partition(b":")
                name = name.strip()
                value = value.strip()
                self._callbacks["on_header_field"](name, 0, len(name))
                self._callbacks["on_header_value"](value, 0, len(value))
                self._callbacks["on_header_end"]()
            self._callbacks["on_headers_finished"]()
            content = content.rstrip(b"\r\n")
            self._callbacks["on_part_data"](content, 0, len(content))
            self._callbacks["on_part_end"]()
        self._callbacks["on_end"]()

    def finalize(self) -> None:
        if not self._parsed:
            self._emit_parts()


formparsers.multipart = types.SimpleNamespace(
    MultipartParser=_FakeMultipartParser,
    QuerystringParser=_FakeQuerystringParser,
)
formparsers.parse_options_header = _parse_options_header
requests_module.MultiPartParser = formparsers.MultiPartParser
requests_module.FormParser = formparsers.FormParser
requests_module.parse_options_header = _parse_options_header


class StubProviderInfo:
    def __init__(self, provider_name: str | None = None, fallback_provider_name: str | None = None) -> None:
        self.provider_name = provider_name
        self.fallback_provider_name = fallback_provider_name


class StubTranscriptionService:
    def __init__(
        self,
        transcript: ConversationTranscript | None,
        *,
        asr_provider: StubProviderInfo | None = None,
        llm_provider: StubProviderInfo | None = None,
        transcribe_error: Exception | None = None,
    ) -> None:
        self._transcript = transcript
        self.requested_ids: list[str] = []
        self.transcribe_requests: list[dict[str, object]] = []
        self._transcribe_error = transcribe_error
        self._pipeline = types.SimpleNamespace(
            _asr=asr_provider or StubProviderInfo(),
            _llm_postprocessor=types.SimpleNamespace(_provider=llm_provider or StubProviderInfo()),
        )

    def get_transcript(self, conversation_id: str) -> ConversationTranscript | None:
        self.requested_ids.append(conversation_id)
        if self._transcript is None or self._transcript.conversation_id != conversation_id:
            return None
        return self._transcript

    async def transcribe_file(
        self,
        source_path: Path,
        *,
        language: str | None = None,
        source: str = "",
    ) -> ConversationTranscript:
        self.transcribe_requests.append(
            {
                "source_path": source_path,
                "language": language,
                "source": source,
                "bytes": source_path.read_bytes(),
            }
        )
        if self._transcribe_error is not None:
            raise self._transcribe_error
        assert self._transcript is not None
        return self._transcript


class StubQualityService:
    def __init__(self, report: QualityReport) -> None:
        self._report = report
        self.requested_transcripts: list[ConversationTranscript] = []

    def build_report(self, transcript: ConversationTranscript) -> QualityReport:
        self.requested_transcripts.append(transcript)
        return self._report


def build_client(
    transcript: ConversationTranscript | None,
    report: QualityReport,
    *,
    settings: object | None = None,
    asr_provider: StubProviderInfo | None = None,
    llm_provider: StubProviderInfo | None = None,
    transcribe_error: Exception | None = None,
) -> tuple[TestClient, StubTranscriptionService, StubQualityService]:
    app = FastAPI()
    transcription_service = StubTranscriptionService(
        transcript,
        asr_provider=asr_provider,
        llm_provider=llm_provider,
        transcribe_error=transcribe_error,
    )
    quality_service = StubQualityService(report)
    app.state.settings = settings or types.SimpleNamespace(
        app_name="Collective MindGraph Realtime Backend",
        vad_provider="silero",
        asr_provider="auto",
        diarizer_provider="pyannote",
        llm_provider="bedrock_auto_local",
        temp_dir=Path(tempfile.gettempdir()),
    )
    app.state.transcription_service = transcription_service
    app.state.quality_service = quality_service
    app.state.id_factory = lambda: "route_test"
    app.include_router(router)
    return TestClient(app), transcription_service, quality_service


def test_transcribe_file_route_returns_transcript_renderings_and_stats():
    transcript = ConversationTranscript(
        conversation_id="conv_upload_route",
        source="upload",
        segments=[
            TranscriptSegment(
                segment_id="seg_1",
                start=0.0,
                end=1.0,
                speaker="Speaker_1",
                raw_text="hello upload",
                corrected_text="Hello upload.",
            )
        ],
    )
    report = QualityReport(
        conversation_id="unused",
        segment_count=0,
        speaker_count=0,
        unresolved_segments=0,
        overlap_ratio=0.0,
        avg_asr_confidence=None,
        avg_speaker_confidence=None,
        word_timing_coverage=0.0,
        corrected_change_ratio=0.0,
        topic_count=0,
        action_item_count=0,
        decision_count=0,
        question_count=0,
        summary_present=False,
        warnings=[],
    )
    client, transcription_service, _quality_service = build_client(transcript, report)

    response = client.post(
        "/transcribe/file",
        files={"upload": ("sample.flac", b"fake-flac-bytes", "audio/flac")},
        data={"language": "en"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "transcript": transcript.model_dump(mode="json"),
        "text_output": "[00:00.000 - 00:01.000] Speaker_1: Hello upload.",
        "raw_text_output": "[00:00.000 - 00:01.000] Speaker_1: hello upload",
        "corrected_text_output": "[00:00.000 - 00:01.000] Speaker_1: Hello upload.",
        "speaker_stats": [
            {
                "speaker": "Speaker_1",
                "segment_count": 1,
                "speaking_seconds": 1.0,
                "overlap_segments": 0,
                "first_start": 0.0,
                "last_end": 1.0,
            }
        ],
    }
    assert len(transcription_service.transcribe_requests) == 1
    request = transcription_service.transcribe_requests[0]
    assert Path(request["source_path"]).suffix == ".flac"
    assert request["language"] == "en"
    assert request["source"] == "upload"
    assert request["bytes"] == b"fake-flac-bytes"
    assert not Path(request["source_path"]).exists()


def test_transcribe_file_route_requires_upload_field():
    report = QualityReport(
        conversation_id="unused",
        segment_count=0,
        speaker_count=0,
        unresolved_segments=0,
        overlap_ratio=0.0,
        avg_asr_confidence=None,
        avg_speaker_confidence=None,
        word_timing_coverage=0.0,
        corrected_change_ratio=0.0,
        topic_count=0,
        action_item_count=0,
        decision_count=0,
        question_count=0,
        summary_present=False,
        warnings=[],
    )
    client, transcription_service, _quality_service = build_client(None, report)

    response = client.post("/transcribe/file", data={"language": "en"})

    assert response.status_code == 422
    assert transcription_service.transcribe_requests == []


def test_transcribe_file_route_cleans_up_temp_file_when_transcription_raises(tmp_path):
    report = QualityReport(
        conversation_id="unused",
        segment_count=0,
        speaker_count=0,
        unresolved_segments=0,
        overlap_ratio=0.0,
        avg_asr_confidence=None,
        avg_speaker_confidence=None,
        word_timing_coverage=0.0,
        corrected_change_ratio=0.0,
        topic_count=0,
        action_item_count=0,
        decision_count=0,
        question_count=0,
        summary_present=False,
        warnings=[],
    )
    client, transcription_service, _quality_service = build_client(
        None,
        report,
        settings=types.SimpleNamespace(
            app_name="Collective MindGraph Realtime Backend",
            vad_provider="silero",
            asr_provider="auto",
            diarizer_provider="pyannote",
            llm_provider="bedrock_auto_local",
            temp_dir=tmp_path,
        ),
        transcribe_error=RuntimeError("transcription exploded"),
    )

    with pytest.raises(RuntimeError, match="transcription exploded"):
        client.post(
            "/transcribe/file",
            files={"upload": ("sample.flac", b"fake-flac-bytes", "audio/flac")},
            data={"language": "en"},
        )

    assert len(transcription_service.transcribe_requests) == 1
    request = transcription_service.transcribe_requests[0]
    assert request["bytes"] == b"fake-flac-bytes"
    assert request["language"] == "en"
    assert request["source"] == "upload"
    assert request["source_path"] == tmp_path / "upload_route_test.flac"
    assert not Path(request["source_path"]).exists()


def test_health_route_returns_provider_and_fallback_status():
    report = QualityReport(
        conversation_id="unused",
        segment_count=0,
        speaker_count=0,
        unresolved_segments=0,
        overlap_ratio=0.0,
        avg_asr_confidence=None,
        avg_speaker_confidence=None,
        word_timing_coverage=0.0,
        corrected_change_ratio=0.0,
        topic_count=0,
        action_item_count=0,
        decision_count=0,
        question_count=0,
        summary_present=False,
        warnings=[],
    )
    client, _transcription_service, _quality_service = build_client(
        None,
        report,
        settings=types.SimpleNamespace(
            app_name="Realtime Backend",
            vad_provider="silero",
            asr_provider="auto",
            diarizer_provider="pyannote",
            llm_provider="bedrock_auto_local",
        ),
        asr_provider=StubProviderInfo("deepgram", "faster_whisper"),
        llm_provider=StubProviderInfo("bedrock", "lmstudio"),
    )

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app_name": "Realtime Backend",
        "vad_provider": "silero",
        "asr_provider": "auto",
        "asr_provider_resolved": "deepgram",
        "asr_fallback_provider": "faster_whisper",
        "diarizer_provider": "pyannote",
        "llm_provider": "bedrock_auto_local",
        "llm_provider_resolved": "bedrock",
        "llm_fallback_provider": "lmstudio",
    }


def test_health_route_allows_missing_resolved_provider_fields():
    report = QualityReport(
        conversation_id="unused",
        segment_count=0,
        speaker_count=0,
        unresolved_segments=0,
        overlap_ratio=0.0,
        avg_asr_confidence=None,
        avg_speaker_confidence=None,
        word_timing_coverage=0.0,
        corrected_change_ratio=0.0,
        topic_count=0,
        action_item_count=0,
        decision_count=0,
        question_count=0,
        summary_present=False,
        warnings=[],
    )
    client, _transcription_service, _quality_service = build_client(None, report)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app_name": "Collective MindGraph Realtime Backend",
        "vad_provider": "silero",
        "asr_provider": "auto",
        "asr_provider_resolved": None,
        "asr_fallback_provider": None,
        "diarizer_provider": "pyannote",
        "llm_provider": "bedrock_auto_local",
        "llm_provider_resolved": None,
        "llm_fallback_provider": None,
    }


def test_quality_route_returns_built_report():
    transcript = ConversationTranscript(
        conversation_id="conv_quality_route",
        source="test",
        summary="Short summary.",
        segments=[
            TranscriptSegment(
                segment_id="seg_1",
                start=0.0,
                end=1.0,
                speaker="Speaker_1",
                raw_text="hello",
                corrected_text="Hello.",
            )
        ],
    )
    report = QualityReport(
        conversation_id="conv_quality_route",
        segment_count=1,
        speaker_count=1,
        unresolved_segments=0,
        overlap_ratio=0.0,
        avg_asr_confidence=0.98,
        avg_speaker_confidence=0.91,
        word_timing_coverage=1.0,
        corrected_change_ratio=0.1,
        topic_count=0,
        action_item_count=0,
        decision_count=0,
        question_count=0,
        summary_present=True,
        warnings=[],
    )
    client, transcription_service, quality_service = build_client(transcript, report)

    response = client.get("/quality/conv_quality_route")

    assert response.status_code == 200
    assert response.json() == report.model_dump(mode="json")
    assert transcription_service.requested_ids == ["conv_quality_route"]
    assert quality_service.requested_transcripts == [transcript]


def test_quality_route_returns_404_when_transcript_is_missing():
    report = QualityReport(
        conversation_id="unused",
        segment_count=0,
        speaker_count=0,
        unresolved_segments=0,
        overlap_ratio=0.0,
        avg_asr_confidence=None,
        avg_speaker_confidence=None,
        word_timing_coverage=0.0,
        corrected_change_ratio=0.0,
        topic_count=0,
        action_item_count=0,
        decision_count=0,
        question_count=0,
        summary_present=False,
        warnings=[],
    )
    client, transcription_service, quality_service = build_client(None, report)

    response = client.get("/quality/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Transcript not found."}
    assert transcription_service.requested_ids == ["missing"]
    assert quality_service.requested_transcripts == []


def test_summary_route_returns_summary_payload():
    transcript = ConversationTranscript(
        conversation_id="conv_summary_route",
        source="test",
        summary="Ship next Tuesday.",
        topics=[TopicSegment(label="Launch", start=0.0, end=1.0)],
        action_items=["Speaker_1: Send launch checklist"],
        decisions=["Speaker_2: Freeze scope"],
        segments=[
            TranscriptSegment(
                segment_id="seg_1",
                start=0.0,
                end=1.0,
                speaker="Speaker_1",
                raw_text="ship next tuesday",
                corrected_text="Ship next Tuesday.",
            )
        ],
    )
    report = QualityReport(
        conversation_id="conv_summary_route",
        segment_count=1,
        speaker_count=1,
        unresolved_segments=0,
        overlap_ratio=0.0,
        avg_asr_confidence=None,
        avg_speaker_confidence=None,
        word_timing_coverage=1.0,
        corrected_change_ratio=0.0,
        topic_count=1,
        action_item_count=1,
        decision_count=1,
        question_count=0,
        summary_present=True,
        warnings=[],
    )
    client, transcription_service, _quality_service = build_client(transcript, report)

    response = client.get("/summary/conv_summary_route")

    assert response.status_code == 200
    assert response.json() == {
        "conversation_id": "conv_summary_route",
        "summary": "Ship next Tuesday.",
        "topics": [{"label": "Launch", "start": 0.0, "end": 1.0}],
        "action_items": ["Speaker_1: Send launch checklist"],
        "decisions": ["Speaker_2: Freeze scope"],
    }
    assert transcription_service.requested_ids == ["conv_summary_route"]


def test_summary_route_returns_404_when_transcript_is_missing():
    report = QualityReport(
        conversation_id="unused",
        segment_count=0,
        speaker_count=0,
        unresolved_segments=0,
        overlap_ratio=0.0,
        avg_asr_confidence=None,
        avg_speaker_confidence=None,
        word_timing_coverage=0.0,
        corrected_change_ratio=0.0,
        topic_count=0,
        action_item_count=0,
        decision_count=0,
        question_count=0,
        summary_present=False,
        warnings=[],
    )
    client, transcription_service, _quality_service = build_client(None, report)

    response = client.get("/summary/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Transcript not found."}
    assert transcription_service.requested_ids == ["missing"]


def test_transcript_route_returns_renderings_and_speaker_stats():
    transcript = ConversationTranscript(
        conversation_id="conv_transcript_route",
        source="test",
        segments=[
            TranscriptSegment(
                segment_id="seg_1",
                start=0.0,
                end=1.25,
                speaker="Speaker_1",
                raw_text="hello there",
                corrected_text="Hello there.",
            ),
            TranscriptSegment(
                segment_id="seg_2",
                start=1.5,
                end=2.0,
                speaker="Speaker_2",
                raw_text="ready now",
                corrected_text="Ready now.",
                overlap=True,
            ),
        ],
    )
    report = QualityReport(
        conversation_id="conv_transcript_route",
        segment_count=2,
        speaker_count=2,
        unresolved_segments=0,
        overlap_ratio=0.5,
        avg_asr_confidence=None,
        avg_speaker_confidence=None,
        word_timing_coverage=0.0,
        corrected_change_ratio=0.0,
        topic_count=0,
        action_item_count=0,
        decision_count=0,
        question_count=0,
        summary_present=False,
        warnings=[],
    )
    client, transcription_service, _quality_service = build_client(transcript, report)

    response = client.get("/transcript/conv_transcript_route")

    assert response.status_code == 200
    assert response.json() == {
        "transcript": transcript.model_dump(mode="json"),
        "renderings": {
            "raw_text_output": (
                "[00:00.000 - 00:01.250] Speaker_1: hello there\n"
                "[00:01.500 - 00:02.000] Speaker_2: ready now"
            ),
            "corrected_text_output": (
                "[00:00.000 - 00:01.250] Speaker_1: Hello there.\n"
                "[00:01.500 - 00:02.000] Speaker_2: Ready now."
            ),
        },
        "speaker_stats": [
            {
                "speaker": "Speaker_1",
                "segment_count": 1,
                "speaking_seconds": 1.25,
                "overlap_segments": 0,
                "first_start": 0.0,
                "last_end": 1.25,
            },
            {
                "speaker": "Speaker_2",
                "segment_count": 1,
                "speaking_seconds": 0.5,
                "overlap_segments": 1,
                "first_start": 1.5,
                "last_end": 2.0,
            },
        ],
    }
    assert transcription_service.requested_ids == ["conv_transcript_route"]


def test_transcript_route_returns_404_when_transcript_is_missing():
    report = QualityReport(
        conversation_id="unused",
        segment_count=0,
        speaker_count=0,
        unresolved_segments=0,
        overlap_ratio=0.0,
        avg_asr_confidence=None,
        avg_speaker_confidence=None,
        word_timing_coverage=0.0,
        corrected_change_ratio=0.0,
        topic_count=0,
        action_item_count=0,
        decision_count=0,
        question_count=0,
        summary_present=False,
        warnings=[],
    )
    client, transcription_service, _quality_service = build_client(None, report)

    response = client.get("/transcript/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Transcript not found."}
    assert transcription_service.requested_ids == ["missing"]
