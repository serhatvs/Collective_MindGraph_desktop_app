import json

from PySide6.QtWidgets import QApplication

from collective_mindgraph_desktop.database import Database
from collective_mindgraph_desktop.services import CollectiveMindGraphService
from collective_mindgraph_desktop.transcription import TranscriptionResult
from collective_mindgraph_desktop.ui.pages.knowledge_graph_page import KnowledgeGraphPage


def _service(tmp_path) -> CollectiveMindGraphService:
    return CollectiveMindGraphService(Database(tmp_path / "source_trace.sqlite3"))


def test_extracted_task_retains_explicit_segment_preview_and_timestamps(tmp_path):
    service = _service(tmp_path)
    result = TranscriptionResult(
        conversation_id="trace-1",
        model_id="test",
        audio_path="sample.wav",
        text="Clean segment text",
        action_items=[
            {
                "title": "Send the launch checklist",
                "responsible_person": "Aylin",
                "source_segment_id": "s1",
            }
        ],
        segments=[
            {
                "segment_id": "s1",
                "start": 12.5,
                "end": 18.75,
                "speaker": "Aylin",
                "raw_text": "raw segment text",
                "corrected_text": "Clean segment text",
            }
        ],
    )

    session = service.ingest_transcription_result(result)
    nodes = service.get_session_graph_data(session.id)["nodes"]
    task_node = next(node for node in nodes if node["type"] == "TASK")

    assert task_node["source_segment_id"] == "s1"
    assert task_node["source_timestamp_start"] == 12.5
    assert task_node["source_timestamp_end"] == 18.75
    assert task_node["source_text_preview"] == "Clean segment text"

    metadata = json.loads(task_node["metadata_json"])
    assert metadata["source_segment_id"] == "s1"
    assert metadata["source_timestamp_start"] == 12.5
    assert metadata["source_timestamp_end"] == 18.75
    assert metadata["source_preview"] == "Clean segment text"

    mapped = service.production_graph.get_node(task_node["id"])
    assert mapped is not None
    assert mapped.source is not None
    assert mapped.source.id == task_node["source_reference_id"]
    assert mapped.source.segment_id == "s1"
    assert mapped.source.text_preview == "Clean segment text"


def test_segment_source_preview_prefers_cleaned_text(tmp_path):
    service = _service(tmp_path)
    result = TranscriptionResult(
        conversation_id="trace-2",
        model_id="test",
        audio_path="sample.wav",
        text="Cleaned words",
        segments=[
            {
                "segment_id": "s2",
                "start": 1.0,
                "end": 2.0,
                "raw_text": "raw words",
                "corrected_text": "Cleaned words",
            }
        ],
    )

    session = service.ingest_transcription_result(result)
    nodes = service.get_session_graph_data(session.id)["nodes"]
    segment_node = next(node for node in nodes if node["type"] == "SEGMENT")

    assert segment_node["source_segment_id"] == "s2"
    assert segment_node["source_text_preview"] == "Cleaned words"


def test_graph_trace_uses_explicit_segment_id_before_node_id_fallback():
    QApplication.instance() or QApplication([])
    page = KnowledgeGraphPage()
    captured: list[tuple[str, str]] = []
    page.source_trace_requested.connect(lambda session_id, segment_id: captured.append((session_id, segment_id)))
    page._selected_node = {
        "id": "seg_1_wrong",
        "type": "SEGMENT",
        "source_session_id": "7",
        "source_segment_id": "s1",
        "metadata_json": "{}",
    }

    page._handle_trace_click()

    assert captured == [("7", "s1")]


def test_graph_trace_handles_missing_optional_source_metadata_safely():
    QApplication.instance() or QApplication([])
    page = KnowledgeGraphPage()
    captured: list[tuple[str, str]] = []
    page.source_trace_requested.connect(lambda session_id, segment_id: captured.append((session_id, segment_id)))
    page._selected_node = {
        "id": "task_without_source",
        "type": "TASK",
        "metadata_json": "{not valid json",
    }

    page._handle_trace_click()

    assert captured == []
