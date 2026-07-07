
import os
import pytest
from pathlib import Path
from datetime import datetime, UTC

# Mocking env for offscreen testing if needed
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collective_mindgraph_desktop.database import Database
from collective_mindgraph_desktop.services import CollectiveMindGraphService
from collective_mindgraph_desktop.transcription import TranscriptionResult

def test_collective_mindgraph_product_loop(tmp_path):
    # 1. Setup Service with temporary database
    db_path = tmp_path / "test_memory.sqlite3"
    service = CollectiveMindGraphService(Database(db_path))
    
    # 2. Session Creation
    session = service.create_session("Technical Memory Test", "DEV-01")
    assert session.id is not None
    assert session.title == "Technical Memory Test"
    
    # 3. Memory Ingest (Simulate Backend Result)
    # This proves the loop from transcript -> structured extraction -> storage
    result = TranscriptionResult(
        conversation_id="loop_test_conv",
        model_id="faster-whisper-mock",
        audio_path="test_audio.wav",
        text="Merhaba. Transcript kalitesini artırmamız gerekiyor. FastAPI endpointini test edeceğiz.",
        raw_text_output="merhaba transcript kalitesini artırmamız gerekiyor fastapi endpointini test edeceğiz",
        corrected_text_output="Merhaba. Transcript kalitesini artırmamız gerekiyor. FastAPI endpointini test edeceğiz.",
        summary="Testing FastAPI endpoints and improving transcript quality.",
        topics=[{"label": "FastAPI", "start": 0.0, "end": 10.0}],
        action_items=[{
            "title": "FastAPI endpointini test edeceğiz",
            "responsible_person": "Serhat",
            "source_segment_id": "seg_1"
        }],
        decisions=[{
            "decision": "Transcript kalitesini artırmamız gerekiyor",
            "source_segment_id": "seg_1"
        }],
        segments=[{
            "segment_id": "seg_1",
            "start": 0.0,
            "end": 10.0,
            "speaker": "Serhat",
            "raw_text": "merhaba transcript kalitesini artırmamız gerekiyor fastapi endpointini test edeceğiz",
            "corrected_text": "Merhaba. Transcript kalitesini artırmamız gerekiyor. FastAPI endpointini test edeceğiz."
        }],
        people=["Serhat"]
    )
    
    ingested_session = service.ingest_transcription_result(result, session_id=session.id)
    assert ingested_session.id == session.id
    
    # 4. Verify Structured Storage (Insights)
    detail = service.get_session_detail(session.id)
    assert len(detail.transcript_analyses) == 1
    analysis = list(detail.transcript_analyses.values())[0]
    
    assert analysis.summary is not None
    assert len(analysis.action_items) == 1
    assert analysis.action_items[0].title == "FastAPI endpointini test edeceğiz"
    assert analysis.action_items[0].source_segment_id == "seg_1"
    
    assert len(analysis.decisions) == 1
    assert "Transcript kalitesini" in analysis.decisions[0].decision
    
    assert len(analysis.topics) == 1
    assert analysis.topics[0].label == "FastAPI"
    
    # 5. Verify Graph Persistence
    # Root node + 2 side nodes (summary and insights)
    assert len(detail.graph_nodes) >= 3
    
    # 6. Global Memory Search Proof
    # Since search happens via backend in real app, we verify that the service
    # layer has prepared the data such that a keyword search would find it.
    # For this test, we can check the database directly for queryability.
    with service._database.connect() as conn:
        # Check task queryability
        task_row = conn.execute("SELECT * FROM transcript_analyses WHERE transcript_id = ?", (analysis.transcript_id,)).fetchone()
        assert "FastAPI" in task_row["action_items_json"]
        assert "decisions_json" in task_row.keys()
        
    # 7. UI Page Metadata (Verify naming/framing exists)
    from collective_mindgraph_desktop.ui.main_window import MainWindow
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(service)
    
    tab_texts = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    assert "Session Memory" in tab_texts
    assert "Knowledge Audit" in tab_texts
    assert "Extracted Notes" in tab_texts
    assert "Review Suggestions" in tab_texts
    assert "Global Search" in tab_texts
    
    print("Product loop test passed: Session -> Memory -> Extraction -> Searchable Trace.")

if __name__ == "__main__":
    # If run directly, needs a pytest-like environment or just call the function
    # Note: tmp_path is a pytest fixture.
    pass
