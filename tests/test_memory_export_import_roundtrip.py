import json

from collective_mindgraph.core.memory_graph import EdgeType
from collective_mindgraph_desktop.database import Database
from collective_mindgraph_desktop.services import CollectiveMindGraphService
from collective_mindgraph_desktop.transcription import TranscriptionResult


def _service(tmp_path, name: str) -> CollectiveMindGraphService:
    return CollectiveMindGraphService(Database(tmp_path / name))


def test_memory_export_import_preserves_graph_review_and_source_state(tmp_path):
    service = _service(tmp_path, "source.sqlite3")
    result = TranscriptionResult(
        conversation_id="roundtrip-1",
        model_id="test-model",
        audio_path="meeting.wav",
        text="Clean segment text",
        raw_text_output="raw transcript text",
        corrected_text_output="cleaned transcript text",
        action_items=[{"title": "Send checklist", "source_segment_id": "s1"}],
        decisions=[{"decision": "Use SQLite export", "source_segment_id": "s1"}],
        topics=[{"label": "Export safety", "start": 4.0, "end": 9.5}],
        segments=[
            {
                "segment_id": "s1",
                "start": 4.0,
                "end": 9.5,
                "speaker": "Aylin",
                "raw_text": "raw segment text",
                "corrected_text": "Clean segment text",
                "confidence": 0.92,
            }
        ],
        metadata={
            "entities": [{"title": "SQLite", "source_segment_id": "s1"}],
            "risks": [
                {"title": "Import may drop metadata", "source_segment_id": "s1"},
                {"title": "Roundtrip may lose source refs", "source_segment_id": "s1"},
            ],
            "open_questions": [{"title": "Who validates imports?", "source_segment_id": "s1"}],
            "follow_ups": [{"title": "Run import smoke test", "source_segment_id": "s1"}],
            "extraction_mode": "test",
        },
    )

    session = service.ingest_transcription_result(result)
    detail = service.get_session_detail(session.id)
    assert detail is not None
    transcript_id = detail.transcripts[0].id
    with service._database.connect() as conn:
        conn.execute(
            "UPDATE transcript_analyses SET metadata_json = ? WHERE transcript_id = ?",
            (
                json.dumps(
                    {
                        "language": "tr",
                        "transcription_profile": "max_quality",
                        "source_session_id": str(session.id),
                    }
                ),
                transcript_id,
            ),
        )

    graph = service.get_session_graph_data(session.id)
    task = next(node for node in graph["nodes"] if node["type"] == "TASK")
    entity = next(node for node in graph["nodes"] if node["type"] == "ENTITY")
    risks = [node for node in graph["nodes"] if node["type"] == "RISK"]
    assert len(risks) == 2

    assert service.update_node(task["id"], {"review_status": "approved"})
    assert service.update_node(entity["id"], {"review_status": "rejected", "disabled": True})
    assert service.merge_nodes(risks[1]["id"], risks[0]["id"])

    export_path = tmp_path / "memory_export.json"
    payload = service.export_session(session.id, export_path)
    assert payload["transcripts"][0]["text"] == "Clean segment text"
    assert payload["transcript_analyses"][0]["raw_text_output"] == "raw transcript text"
    assert payload["v2_production_graph"]["source_references"]

    imported_service = _service(tmp_path, "imported.sqlite3")
    imported = imported_service.import_session(export_path)
    imported_detail = imported_service.get_session_detail(imported.id)
    assert imported_detail is not None
    assert imported_detail.transcripts[0].text == "Clean segment text"
    imported_analysis = next(iter(imported_detail.transcript_analyses.values()))
    assert imported_analysis.raw_text_output == "raw transcript text"
    assert imported_analysis.corrected_text_output == "cleaned transcript text"
    assert imported_analysis.metadata["language"] == "tr"
    assert imported_analysis.metadata["transcription_profile"] == "max_quality"
    assert imported_analysis.segments[0].segment_id == "s1"
    assert imported_analysis.segments[0].start == 4.0
    assert imported_analysis.segments[0].end == 9.5

    imported_graph = imported_service.get_session_graph_data(imported.id)
    imported_types = {node["type"] for node in imported_graph["nodes"]}
    assert {"TASK", "DECISION", "TOPIC", "ENTITY", "RISK", "OPEN_QUESTION", "FOLLOW_UP"} <= imported_types

    imported_task = next(node for node in imported_graph["nodes"] if node["type"] == "TASK")
    imported_task_meta = json.loads(imported_task["metadata_json"])
    assert imported_task_meta["review_status"] == "approved"
    assert imported_task_meta["source_session_id"] == str(imported.id)
    assert imported_task_meta["source_segment_id"] == "s1"
    assert imported_task["source_session_id"] == str(imported.id)
    assert imported_task["source_segment_id"] == "s1"
    assert imported_task["source_text_preview"] == "Clean segment text"
    assert imported_task["source_timestamp_start"] == 4.0
    assert imported_task["source_timestamp_end"] == 9.5

    imported_entity = next(node for node in imported_graph["nodes"] if node["type"] == "ENTITY")
    entity_meta = json.loads(imported_entity["metadata_json"])
    assert entity_meta["review_status"] == "rejected"
    assert entity_meta["disabled"] is True

    imported_risks = [node for node in imported_graph["nodes"] if node["type"] == "RISK"]
    merged_source = next(node for node in imported_risks if json.loads(node["metadata_json"]).get("review_status") == "merged")
    merged_target = next(node for node in imported_risks if json.loads(node["metadata_json"]).get("merged_source_node_ids"))
    source_meta = json.loads(merged_source["metadata_json"])
    target_meta = json.loads(merged_target["metadata_json"])
    assert source_meta["merged_into_node_id"] == merged_target["id"]
    assert merged_source["id"] in target_meta["merged_source_node_ids"]
    assert any(edge["edge_type"] == EdgeType.NODE_MERGED_INTO.value for edge in imported_graph["edges"])


def test_import_accepts_old_minimal_v2_export(tmp_path):
    export_path = tmp_path / "old_export.json"
    export_path.write_text(
        json.dumps(
            {
                "session": {"title": "Old Export", "device_id": "DEV", "status": "active"},
                "transcripts": [],
                "graph_nodes": [],
                "snapshots": [],
                "transcript_analyses": [],
                "v2_production_graph": {
                    "source_references": [{"id": "ref-old", "session_id": "old-session"}],
                    "nodes": [
                        {
                            "id": "task-old",
                            "type": "TASK",
                            "title": "Legacy task",
                            "metadata_json": {"review_status": "approved", "source_session_id": "old-session"},
                            "source_reference_id": "ref-old",
                        }
                    ],
                    "edges": [],
                },
            }
        ),
        encoding="utf-8",
    )

    service = _service(tmp_path, "old_import.sqlite3")
    imported = service.import_session(export_path)
    graph = service.get_session_graph_data(imported.id)
    task = graph["nodes"][0]
    metadata = json.loads(task["metadata_json"])

    assert task["id"] == "task-old"
    assert task["source_session_id"] == str(imported.id)
    assert task["source_segment_id"] is None
    assert task["source_text_preview"] is None
    assert metadata["review_status"] == "approved"
    assert metadata["source_session_id"] == str(imported.id)
