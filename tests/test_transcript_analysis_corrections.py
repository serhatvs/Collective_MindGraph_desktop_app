import os
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from collective_mindgraph_desktop.database import Database
from collective_mindgraph_desktop.services import CollectiveMindGraphService, SnapshotHasher
from collective_mindgraph_desktop.transcription import TranscriptionResult
from collective_mindgraph_desktop.ui.session_detail_panel import SessionDetailPanel


def build_service(tmp_path) -> CollectiveMindGraphService:
    return CollectiveMindGraphService(Database(tmp_path / "collective_mindgraph.sqlite3"))


def build_transcription_result(audio_path: str) -> TranscriptionResult:
    return TranscriptionResult(
        text="Speaker_1: hello\nSpeaker_2: ready now",
        model_id="realtime_backend",
        audio_path=audio_path,
        conversation_id="conv_analysis_edits",
        raw_text_output=(
            "[00:00.000 - 00:01.000] Speaker_1: hello\n"
            "[00:01.000 - 00:02.000] Speaker_2: ready now"
        ),
        corrected_text_output=(
            "[00:00.000 - 00:01.000] Speaker_1: Hello.\n"
            "[00:01.000 - 00:02.000] Speaker_2: Ready now."
        ),
        summary="Short exchange.",
        topics=[{"label": "Greeting", "start": 0.0, "end": 2.0}],
        action_items=["Keep listening"],
        decisions=["Continue recording"],
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
                "raw_text": "hello",
                "corrected_text": "Hello.",
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
                "raw_text": "ready now",
                "corrected_text": "Ready now.",
                "confidence": 0.92,
                "speaker_confidence": 0.88,
                "overlap": False,
                "notes": [],
            },
        ],
        quality_report={
            "segment_count": 2,
            "speaker_count": 2,
            "unresolved_segments": 0,
            "overlap_ratio": 0.0,
            "avg_asr_confidence": 0.935,
            "avg_speaker_confidence": 0.89,
            "word_timing_coverage": 1.0,
            "corrected_change_ratio": 0.2,
            "topic_count": 1,
            "action_item_count": 1,
            "decision_count": 1,
            "question_count": 0,
            "summary_present": True,
            "warnings": [],
        },
    )


def test_save_transcript_analysis_corrections_rebuilds_persisted_views(tmp_path):
    service = build_service(tmp_path)
    session = service.ingest_transcription_result(build_transcription_result(str(tmp_path / "sample.wav")))

    detail = service.get_session_detail(session.id)

    assert detail is not None
    transcript = detail.transcripts[-1]
    analysis = detail.transcript_analyses[transcript.id]
    previous_snapshot_hash = detail.snapshots[0].hash_sha256
    summary_node_text = detail.graph_nodes[1].node_text
    decision_node_text = detail.graph_nodes[2].node_text

    service.save_transcript_analysis_corrections(
        transcript.id,
        [
            replace(analysis.segments[1], speaker="Ayla", corrected_text="Ready."),
            replace(analysis.segments[0], speaker="Hasan", corrected_text="Hello world."),
        ],
    )

    refreshed_detail = service.get_session_detail(session.id)

    assert refreshed_detail is not None
    assert refreshed_detail.transcripts[-1].text == "Ayla: Ready.\nHasan: Hello world."
    assert refreshed_detail.graph_nodes[0].node_text == "Ayla: Ready.\nHasan: Hello world."
    assert refreshed_detail.graph_nodes[1].node_text == summary_node_text
    assert refreshed_detail.graph_nodes[2].node_text == decision_node_text
    assert len(refreshed_detail.snapshots) == 1
    assert refreshed_detail.snapshots[0].node_count == len(refreshed_detail.graph_nodes)
    assert refreshed_detail.snapshots[0].hash_sha256 == SnapshotHasher.compute(refreshed_detail.graph_nodes)
    assert refreshed_detail.snapshots[0].hash_sha256 != previous_snapshot_hash

    refreshed_analysis = refreshed_detail.transcript_analyses[transcript.id]
    assert [item.speaker for item in refreshed_analysis.segments] == ["Ayla", "Hasan"]
    assert refreshed_analysis.corrected_text_output.splitlines() == [
        "[00:01.000 - 00:02.000] Ayla: Ready.",
        "[00:00.000 - 00:01.000] Hasan: Hello world.",
    ]
    assert [item.speaker for item in refreshed_analysis.speaker_stats] == ["Ayla", "Hasan"]
    assert refreshed_analysis.quality_report is not None
    assert refreshed_analysis.quality_report.segment_count == 2
    assert refreshed_analysis.quality_report.speaker_count == 2
    assert refreshed_analysis.quality_report.unresolved_segments == 0


def test_session_detail_panel_emits_edited_segments_in_ui_order(tmp_path):
    app = QApplication.instance() or QApplication([])
    service = build_service(tmp_path)
    session = service.ingest_transcription_result(build_transcription_result(str(tmp_path / "sample.wav")))
    detail = service.get_session_detail(session.id)

    assert app is not None
    assert detail is not None
    transcript = detail.transcripts[-1]
    analysis = detail.transcript_analyses[transcript.id]

    panel = SessionDetailPanel()
    emitted: list[tuple[int, object]] = []
    panel.analysis_corrections_requested.connect(lambda transcript_id, segments: emitted.append((transcript_id, segments)))

    panel.set_detail(detail)
    panel.segment_table.setCurrentCell(1, 0)
    panel.segment_table.selectRow(1)
    panel.move_segment_up_button.click()
    panel.segment_table.item(0, 2).setText("Ayla")
    panel.segment_table.item(0, 3).setText("Ready.")
    panel.segment_table.item(1, 2).setText("Hasan")
    panel.segment_table.item(1, 3).setText("Hello world.")

    panel.save_corrections_button.click()

    assert len(emitted) == 1
    emitted_transcript_id, emitted_segments = emitted[0]
    assert emitted_transcript_id == transcript.id
    assert [item.segment_id for item in emitted_segments] == [
        analysis.segments[1].segment_id,
        analysis.segments[0].segment_id,
    ]
    assert [item.speaker for item in emitted_segments] == ["Ayla", "Hasan"]
    assert [item.corrected_text for item in emitted_segments] == ["Ready.", "Hello world."]
