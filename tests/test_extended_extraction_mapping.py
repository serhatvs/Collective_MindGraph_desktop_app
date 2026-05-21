import pytest
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
        "entities": ["FastAPI", "SQLite"],
        "risks": ["Data loss if power fails"],
        "open_questions": ["Who will handle the deployment?"],
        "follow_ups": ["Check with DevOps tomorrow"]
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
