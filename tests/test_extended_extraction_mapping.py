import pytest
import json
from collective_mindgraph_desktop.services import CollectiveMindGraphService
from collective_mindgraph_desktop.transcription import TranscriptionResult
from realtime_backend.app.models import TopicSegment as TranscriptTopic, TaskItem as TranscriptTaskItem, DecisionItem as TranscriptDecisionItem

from collective_mindgraph_desktop.database import Database

def test_extended_extraction_mapping(tmp_path):
    db_path = tmp_path / "test_memory.sqlite3"
    service = CollectiveMindGraphService(Database(db_path))
    session = service.sessions.create("Test", "MIC", "active", "2026-05-21 00:00:00")
    
    seg_id = f"s_{session.id}_1"
    
    metadata = {
        "entities": [
            {"title": "FastAPI", "source_segment_id": seg_id},
            {"title": "SQLite", "source_segment_id": seg_id},
        ],
        "risks": [{"title": "Data loss if power fails", "source_segment_id": seg_id}],
        "open_questions": [{"title": "Who will handle the deployment?", "source_segment_id": seg_id}],
        "follow_ups": [{"title": "Check with DevOps tomorrow", "source_segment_id": seg_id}],
        "extraction_mode": "test_explicit",
    }
    
    t_result = TranscriptionResult(
        conversation_id=str(session.id),
        model_id="test",
        audio_path="test.wav",
        text="Sample",
        corrected_text_output="Sample",
        segments=[{"segment_id": seg_id, "start": 0.0, "end": 10.0, "speaker": "Unknown", "raw_text": "Sample", "corrected_text": "Sample"}],
        metadata=metadata
    )
    
    service.ingest_transcription_result(t_result, session_id=session.id)
    
    # Verify V2 Graph Nodes
    v2_data = service.get_session_graph_data(session.id)
    nodes = v2_data["nodes"]
    
    node_types = [n["type"] for n in nodes]
    assert "ENTITY" in node_types
    assert "RISK" in node_types
    assert "OPEN_QUESTION" in node_types
    assert "FOLLOW_UP" in node_types
    
    # Verify titles
    titles = [n["title"] for n in nodes]
    assert "FastAPI" in titles
    assert "SQLite" in titles
    assert "Data loss if power fails" in titles
    assert "Who will handle the deployment?" in titles
    assert "Check with DevOps tomorrow" in titles

    for node_type in ("ENTITY", "RISK", "OPEN_QUESTION", "FOLLOW_UP"):
        node = next(n for n in nodes if n["type"] == node_type)
        meta = json.loads(node["metadata_json"])
        assert meta["review_status"] == "pending"
        assert meta["source_session_id"] == str(session.id)
        assert meta["source_segment_id"] == seg_id
        assert meta["source_timestamp_start"] == 0.0
        assert meta["source_timestamp_end"] == 10.0
        assert meta["source_preview"] == "Sample"
        assert node["source_reference_id"]
        assert node["source_session_id"] == str(session.id)
        assert node["source_segment_id"] == seg_id
        assert node["source_text_preview"] == "Sample"
        assert node["source_timestamp_start"] == 0.0
        assert node["source_timestamp_end"] == 10.0

    segment_node = next(n for n in nodes if n["type"] == "SEGMENT")
    edge_sources = {edge["target_node_id"]: edge["source_node_id"] for edge in v2_data["edges"]}
    for node_type in ("ENTITY", "RISK", "OPEN_QUESTION", "FOLLOW_UP"):
        node = next(n for n in nodes if n["type"] == node_type)
        assert edge_sources[node["id"]] == segment_node["id"]


def test_extended_extraction_mapping_accepts_legacy_string_metadata(tmp_path):
    service = CollectiveMindGraphService(Database(tmp_path / "legacy_extended.sqlite3"))

    t_result = TranscriptionResult(
        conversation_id="legacy",
        model_id="test",
        audio_path="test.wav",
        text="Sample",
        segments=[{"segment_id": "s1", "start": 0.0, "end": 1.0, "raw_text": "Sample", "corrected_text": "Sample"}],
        metadata={
            "entities": ["FastAPI", "FastAPI"],
            "risks": ["Data loss"],
            "open_questions": ["Who owns deployment?"],
            "follow_ups": ["Check DevOps"],
        },
    )

    session = service.ingest_transcription_result(t_result)
    nodes = service.get_session_graph_data(session.id)["nodes"]
    titles = [n["title"] for n in nodes]

    assert titles.count("FastAPI") == 1
    assert "Data loss" in titles
    assert "Who owns deployment?" in titles
    assert "Check DevOps" in titles
