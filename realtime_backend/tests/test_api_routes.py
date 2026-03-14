import sys
import types

from fastapi import FastAPI
from fastapi.testclient import TestClient

python_multipart = types.ModuleType("python_multipart")
python_multipart.__version__ = "0.0.20"
sys.modules.setdefault("python_multipart", python_multipart)

from app.api.routes import router
from app.models import ConversationTranscript, QualityReport, TopicSegment, TranscriptSegment


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
    ) -> None:
        self._transcript = transcript
        self.requested_ids: list[str] = []
        self._pipeline = types.SimpleNamespace(
            _asr=asr_provider or StubProviderInfo(),
            _llm_postprocessor=types.SimpleNamespace(_provider=llm_provider or StubProviderInfo()),
        )

    def get_transcript(self, conversation_id: str) -> ConversationTranscript | None:
        self.requested_ids.append(conversation_id)
        if self._transcript is None or self._transcript.conversation_id != conversation_id:
            return None
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
) -> tuple[TestClient, StubTranscriptionService, StubQualityService]:
    app = FastAPI()
    transcription_service = StubTranscriptionService(
        transcript,
        asr_provider=asr_provider,
        llm_provider=llm_provider,
    )
    quality_service = StubQualityService(report)
    app.state.settings = settings or types.SimpleNamespace(
        app_name="Collective MindGraph Realtime Backend",
        vad_provider="silero",
        asr_provider="auto",
        diarizer_provider="pyannote",
        llm_provider="bedrock_auto_local",
    )
    app.state.transcription_service = transcription_service
    app.state.quality_service = quality_service
    app.include_router(router)
    return TestClient(app), transcription_service, quality_service


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
