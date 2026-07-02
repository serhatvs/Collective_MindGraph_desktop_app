import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from collective_mindgraph_desktop.transcription import (
    EvidenceChain,
    EvidenceStep,
    MemoryAskResponse,
    RealtimeBackendTranscriptionConfig,
    RealtimeBackendTranscriptionService,
)
from collective_mindgraph_desktop.ui.components.ask_memory_panel import AskMemoryPanel


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _ask_service_for_payload(payload: dict[str, object]) -> RealtimeBackendTranscriptionService:
    def fake_opener(_request, timeout=None):
        return FakeHTTPResponse(payload)

    return RealtimeBackendTranscriptionService(
        config=RealtimeBackendTranscriptionConfig(base_url="http://127.0.0.1:8080"),
        request_opener=fake_opener,
    )


def test_desktop_ask_memory_parses_full_backend_payload():
    service = _ask_service_for_payload(
        {
            "query": "FastAPI?",
            "mode": "llm_assisted",
            "mode_requested": "llm_assisted",
            "mode_used": "evidence_only_fallback",
            "answer_type": "fallback_to_evidence_only",
            "answer_validation_status": "rejected_unsupported_terms",
            "short_answer": "FastAPI test et.",
            "confidence_level": "high",
            "evidence_coverage_score": 0.42,
            "source_session_ids": ["s1"],
            "source_segment_ids": ["seg1"],
            "used_sources": ["Evidence 1"],
            "rejected_sources": ["unknown"],
            "rejected_terms": ["Pytest"],
            "missing_evidence_note": "No tool choice was recorded.",
            "warnings": ["LLM answer contained unsupported information and was rejected."],
            "sentence_validations": [
                {
                    "sentence": "FastAPI test et.",
                    "supported": True,
                    "sources": ["Evidence 1"],
                    "unsupported_terms": [],
                },
                {
                    "sentence": "Pytest kullan.",
                    "supported": False,
                    "sources": [],
                    "unsupported_terms": ["Pytest"],
                },
            ],
            "evidence_chains": [
                {
                    "steps": [
                        {
                            "node_id": "task_1",
                            "node_type": "TASK",
                            "text": "FastAPI endpointini test et",
                            "edge_type": "SEGMENT_CREATES_TASK",
                            "direction": "out",
                            "source_reference_id": "source_ref_1",
                            "source_session_id": "s1",
                            "source_segment_id": "seg1",
                            "text_preview": "Clean segment preview",
                            "start_time": 3.5,
                            "end_time": 8.25,
                            "edge_path": ["SEGMENT_CREATES_TASK"],
                        }
                    ],
                    "explanation": "Task from segment.",
                }
            ],
        }
    )

    response = service.ask_memory("FastAPI?", mode="llm_assisted")

    assert response.short_answer == "FastAPI test et."
    assert response.mode_used == "evidence_only_fallback"
    assert response.answer_validation_status == "rejected_unsupported_terms"
    assert response.evidence_coverage_score == 0.42
    assert response.source_session_ids == ["s1"]
    assert response.source_segment_ids == ["seg1"]
    assert response.used_sources == ["Evidence 1"]
    assert response.rejected_sources == ["unknown"]
    assert response.rejected_terms == ["Pytest"]
    assert response.sentence_validations[1].unsupported_terms == ["Pytest"]
    step = response.evidence_chains[0].steps[0]
    assert step.node_id == "task_1"
    assert step.source_reference_id == "source_ref_1"
    assert step.source_session_id == "s1"
    assert step.source_segment_id == "seg1"
    assert step.text_preview == "Clean segment preview"
    assert step.start_time == 3.5
    assert step.end_time == 8.25
    assert step.edge_path == ["SEGMENT_CREATES_TASK"]


def test_desktop_ask_memory_parses_minimal_payload_with_safe_defaults():
    service = _ask_service_for_payload(
        {
            "answer": "No evidence.",
            "confidence": "insufficient",
        }
    )

    response = service.ask_memory("Unknown?")

    assert response.short_answer == "No evidence."
    assert response.confidence_level == "insufficient"
    assert response.mode == "evidence_only"
    assert response.mode_used == "evidence_only"
    assert response.answer_validation_status == "accepted"
    assert response.evidence_coverage_score == 0.0
    assert response.used_sources == []
    assert response.rejected_terms == []
    assert response.evidence_chains == []


def test_ask_memory_panel_renders_full_and_minimal_responses_without_qtbot():
    app = QApplication.instance() or QApplication([])
    panel = AskMemoryPanel()

    full_response = MemoryAskResponse(
        query="FastAPI?",
        mode="llm_assisted",
        answer_type="fallback_to_evidence_only",
        short_answer="FastAPI test et.",
        confidence_level="high",
        mode_used="evidence_only_fallback",
        answer_validation_status="rejected_unsupported_terms",
        evidence_coverage_score=0.0,
        used_sources=["Evidence 1"],
        rejected_terms=["Pytest"],
        source_session_ids=["s1"],
        source_segment_ids=["seg1"],
    )
    minimal_response = MemoryAskResponse(
        query="Unknown?",
        mode="evidence_only",
        answer_type="evidence_only",
        short_answer="No evidence.",
        confidence_level="insufficient",
    )

    panel._handle_finished(full_response)
    assert "FastAPI test et." in panel.answer_box.toPlainText()

    panel._handle_finished(minimal_response)
    assert "No evidence." in panel.answer_box.toPlainText()

    panel.deleteLater()
    app.processEvents()


def test_ask_memory_panel_source_button_prefers_per_evidence_metadata():
    app = QApplication.instance() or QApplication([])
    panel = AskMemoryPanel()
    captured: list[tuple[str, str]] = []
    panel.source_navigation_requested.connect(lambda session_id, segment_id: captured.append((session_id, segment_id)))

    response = MemoryAskResponse(
        query="FastAPI?",
        mode="evidence_only",
        answer_type="evidence_only",
        short_answer="FastAPI test et.",
        confidence_level="high",
        source_session_ids=["fallback_session"],
        source_segment_ids=["fallback_segment"],
        evidence_chains=[
            EvidenceChain(
                steps=[
                    EvidenceStep(
                        node_id="task_1",
                        node_type="TASK",
                        text="FastAPI endpointini test et",
                        source_session_id="exact_session",
                        source_segment_id="exact_segment",
                        text_preview="Exact preview text",
                        start_time=1.0,
                        end_time=2.5,
                    )
                ]
            )
        ],
    )

    panel._handle_finished(response)
    open_buttons = [button for button in panel.findChildren(type(panel.ask_button)) if button.text() == "Open Source"]
    assert open_buttons
    open_buttons[0].click()

    assert captured == [("exact_session", "exact_segment")]
    assert "Exact preview text" in " ".join(label.text() for label in panel.findChildren(type(panel.evidence_label)))

    panel.deleteLater()
    app.processEvents()


def test_ask_memory_panel_source_button_falls_back_to_response_sources():
    app = QApplication.instance() or QApplication([])
    panel = AskMemoryPanel()
    captured: list[tuple[str, str]] = []
    panel.source_navigation_requested.connect(lambda session_id, segment_id: captured.append((session_id, segment_id)))

    response = MemoryAskResponse(
        query="FastAPI?",
        mode="evidence_only",
        answer_type="evidence_only",
        short_answer="FastAPI test et.",
        confidence_level="high",
        source_session_ids=["fallback_session"],
        source_segment_ids=["fallback_segment"],
        evidence_chains=[
            EvidenceChain(
                steps=[
                    EvidenceStep(
                        node_id="task_1",
                        node_type="TASK",
                        text="FastAPI endpointini test et",
                    )
                ]
            )
        ],
    )

    panel._handle_finished(response)
    open_buttons = [button for button in panel.findChildren(type(panel.ask_button)) if button.text() == "Open Source"]
    assert open_buttons
    open_buttons[0].click()

    assert captured == [("fallback_session", "fallback_segment")]

    panel.deleteLater()
    app.processEvents()
