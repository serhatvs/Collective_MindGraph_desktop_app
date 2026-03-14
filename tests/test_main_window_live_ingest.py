import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QWidget

from collective_mindgraph_desktop.database import Database
from collective_mindgraph_desktop.services import CollectiveMindGraphService
from collective_mindgraph_desktop.transcription import TranscriptionResult
import collective_mindgraph_desktop.ui.main_window as main_window_module


class FakeVoiceCommandPanel(QWidget):
    activity_reported = Signal(str)
    transcript_captured = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)


def build_service(tmp_path) -> CollectiveMindGraphService:
    return CollectiveMindGraphService(Database(tmp_path / "collective_mindgraph.sqlite3"))


def build_stream_result(audio_path: str, *, conversation_id: str) -> TranscriptionResult:
    return TranscriptionResult(
        text="Speaker_1: Live final result.\nSpeaker_2: Keep testing.",
        model_id="realtime_backend",
        audio_path=audio_path,
        conversation_id=conversation_id,
        corrected_text_output=(
            "[00:00.000 - 00:01.000] Speaker_1: Live final result.\n"
            "[00:01.000 - 00:02.000] Speaker_2: Keep testing."
        ),
        speaker_count=2,
        summary="Streaming summary.",
        topics=[{"label": "Streaming", "start": 0.0, "end": 2.0}],
        action_items=["Keep testing"],
        decisions=["Continue streaming"],
        speaker_stats=[
            {
                "speaker": "Speaker_1",
                "segment_count": 1,
                "speaking_seconds": 1.0,
                "overlap_segments": 0,
                "first_start": 0.0,
                "last_end": 1.0,
            },
            {
                "speaker": "Speaker_2",
                "segment_count": 1,
                "speaking_seconds": 1.0,
                "overlap_segments": 0,
                "first_start": 1.0,
                "last_end": 2.0,
            },
        ],
        segments=[
            {
                "segment_id": "seg_1",
                "start": 0.0,
                "end": 1.0,
                "speaker": "Speaker_1",
                "raw_text": "live final result",
                "corrected_text": "Live final result.",
                "confidence": 0.94,
                "speaker_confidence": 0.9,
                "overlap": False,
                "notes": [],
            },
            {
                "segment_id": "seg_2",
                "start": 1.0,
                "end": 2.0,
                "speaker": "Speaker_2",
                "raw_text": "keep testing",
                "corrected_text": "Keep testing.",
                "confidence": 0.91,
                "speaker_confidence": 0.88,
                "overlap": False,
                "notes": [],
            },
        ],
    )


def build_window(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_window_module, "VoiceCommandPanel", FakeVoiceCommandPanel)
    service = build_service(tmp_path)
    window = main_window_module.MainWindow(service)
    assert app is not None
    return window, service


def test_main_window_ingests_stream_result_into_new_session(tmp_path, monkeypatch):
    window, service = build_window(tmp_path, monkeypatch)

    window._ingest_transcript(build_stream_result(str(tmp_path / "live.wav"), conversation_id="conv_live_new"))

    sessions = service.list_sessions()

    assert len(sessions) == 1
    detail = service.get_session_detail(sessions[0].id)
    assert detail is not None
    transcript = detail.transcripts[-1]
    assert transcript.text == "Speaker_1: Live final result.\nSpeaker_2: Keep testing."
    assert transcript.id in detail.transcript_analyses
    assert detail.transcript_analyses[transcript.id].backend_conversation_id == "conv_live_new"
    assert len(detail.graph_nodes) == 3
    assert detail.graph_nodes[0].node_text == "Speaker_1: Live final result.\nSpeaker_2: Keep testing."
    assert "Summary:" in detail.graph_nodes[1].node_text
    assert "Decision:" in detail.graph_nodes[2].node_text
    assert len(detail.snapshots) == 1
    window.close()


def test_main_window_appends_stream_result_to_selected_session(tmp_path, monkeypatch):
    window, service = build_window(tmp_path, monkeypatch)
    existing = service.ingest_transcript("Existing transcript to keep session selected.")
    window._selected_session_id = existing.id

    window._ingest_transcript(build_stream_result(str(tmp_path / "live.wav"), conversation_id="conv_live_append"))

    detail = service.get_session_detail(existing.id)

    assert detail is not None
    assert len(detail.transcripts) == 2
    assert detail.transcripts[-1].text == "Speaker_1: Live final result.\nSpeaker_2: Keep testing."
    assert detail.transcripts[-1].id in detail.transcript_analyses
    assert detail.transcript_analyses[detail.transcripts[-1].id].backend_conversation_id == "conv_live_append"
    assert len(detail.graph_nodes) == 4
    assert detail.graph_nodes[-3].branch_type == "main"
    assert detail.graph_nodes[-3].node_text == "Speaker_1: Live final result.\nSpeaker_2: Keep testing."
    assert detail.graph_nodes[-2].branch_type == "side"
    assert detail.graph_nodes[-1].branch_type == "side"
    assert len(detail.snapshots) == 1
    window.close()
