import sys
import types

from fastapi import FastAPI
from fastapi.testclient import TestClient

python_multipart = types.ModuleType("python_multipart")
python_multipart.__version__ = "0.0.20"
sys.modules.setdefault("python_multipart", python_multipart)

from app.api.routes import router
from app.models import ConversationTranscript, QualityReport, TopicSegment, TranscriptSegment


class StubTranscriptionService:
    def __init__(self, transcript: ConversationTranscript | None) -> None:
        self._transcript = transcript
        self.requested_ids: list[str] = []

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
) -> tuple[TestClient, StubTranscriptionService, StubQualityService]:
    app = FastAPI()
    transcription_service = StubTranscriptionService(transcript)
    quality_service = StubQualityService(report)
    app.state.transcription_service = transcription_service
    app.state.quality_service = quality_service
    app.include_router(router)
    return TestClient(app), transcription_service, quality_service


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
