import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QApplication

from collective_mindgraph_desktop.database import Database
from collective_mindgraph_desktop.services import CollectiveMindGraphService
from collective_mindgraph_desktop.transcription import TranscriptionResult
from collective_mindgraph_desktop.ui.session_detail_panel import SessionDetailPanel


def build_service(tmp_path) -> CollectiveMindGraphService:
    return CollectiveMindGraphService(Database(tmp_path / "collective_mindgraph.sqlite3"))


def build_transcription_result(audio_path: str) -> TranscriptionResult:
    return TranscriptionResult(
        text="Speaker_1: first idea\nSpeaker_2: second note\nSpeaker_1: third follow up",
        model_id="realtime_backend",
        audio_path=audio_path,
        conversation_id="conv_panel_tools",
        corrected_text_output=(
            "[00:00.000 - 00:01.000] Speaker_1: First idea.\n"
            "[00:01.000 - 00:02.000] Speaker_2: Second note.\n"
            "[00:02.000 - 00:03.000] Speaker_1: Third follow up."
        ),
        segments=[
            {
                "segment_id": "seg_1",
                "start": 0.0,
                "end": 1.0,
                "speaker": "Speaker_1",
                "raw_text": "first idea",
                "corrected_text": "First idea.",
                "confidence": 0.95,
                "speaker_confidence": 0.9,
                "overlap": False,
                "notes": [],
            },
            {
                "segment_id": "seg_2",
                "start": 1.0,
                "end": 2.0,
                "speaker": "Speaker_2",
                "raw_text": "second note",
                "corrected_text": "Second note.",
                "confidence": 0.94,
                "speaker_confidence": 0.89,
                "overlap": False,
                "notes": [],
            },
            {
                "segment_id": "seg_3",
                "start": 2.0,
                "end": 3.0,
                "speaker": "Speaker_1",
                "raw_text": "third follow up",
                "corrected_text": "Third follow up.",
                "confidence": 0.92,
                "speaker_confidence": 0.88,
                "overlap": False,
                "notes": [],
            },
        ],
    )


def build_panel_with_detail(tmp_path):
    app = QApplication.instance() or QApplication([])
    service = build_service(tmp_path)
    session = service.ingest_transcription_result(build_transcription_result(str(tmp_path / "sample.wav")))
    detail = service.get_session_detail(session.id)

    assert app is not None
    assert detail is not None

    panel = SessionDetailPanel()
    panel.set_detail(detail)
    return panel, detail


def test_session_detail_panel_bulk_speaker_tools_update_rows(tmp_path):
    panel, detail = build_panel_with_detail(tmp_path)

    panel.segment_table.setCurrentCell(0, 2)
    panel.speaker_bulk_edit.setText("Hasan")
    panel.rename_speaker_button.click()

    assert panel.segment_table.item(0, 2).text() == "Hasan"
    assert panel.segment_table.item(1, 2).text() == "Speaker_2"
    assert panel.segment_table.item(2, 2).text() == "Hasan"

    panel.speaker_bulk_edit.setText("Merged")
    selection_model = panel.segment_table.selectionModel()
    selection_model.clearSelection()
    for row_index in (0, 1):
        selection_model.select(
            panel.segment_table.model().index(row_index, 0),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
        )
    panel.apply_speaker_to_selection_button.click()

    assert detail.transcript_analyses
    assert panel.segment_table.item(0, 2).text() == "Merged"
    assert panel.segment_table.item(1, 2).text() == "Merged"
    assert panel.segment_table.item(2, 2).text() == "Hasan"
    panel.close()


def test_session_detail_panel_move_merge_and_save_emit_expected_segments(tmp_path):
    panel, detail = build_panel_with_detail(tmp_path)
    transcript_id = detail.transcripts[-1].id
    emitted: list[tuple[int, object]] = []
    panel.analysis_corrections_requested.connect(lambda item_id, segments: emitted.append((item_id, segments)))

    panel.segment_table.setCurrentCell(2, 0)
    panel.move_segment_up_button.click()
    panel.move_segment_up_button.click()

    assert panel.segment_table.item(0, 0).data(0x0100) == "seg_3"
    assert panel.segment_table.item(1, 0).data(0x0100) == "seg_1"

    panel.segment_table.setCurrentCell(0, 0)
    panel.merge_next_button.click()

    assert panel.segment_table.rowCount() == 2
    assert panel.segment_table.item(0, 1).text() == "00:01.000"
    assert panel.segment_table.item(0, 2).text() == "Speaker_1"
    assert panel.segment_table.item(0, 3).text() == "Third follow up. First idea."
    assert panel.segment_table.item(0, 4).text() == "third follow up first idea"

    panel.save_corrections_button.click()

    assert len(emitted) == 1
    emitted_transcript_id, emitted_segments = emitted[0]
    assert emitted_transcript_id == transcript_id
    assert [item.segment_id for item in emitted_segments] == ["seg_3", "seg_2"]
    assert [item.corrected_text for item in emitted_segments] == [
        "Third follow up. First idea.",
        "Second note.",
    ]
    panel.close()
