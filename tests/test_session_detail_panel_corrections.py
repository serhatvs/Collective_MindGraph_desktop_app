from dataclasses import replace
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QApplication

from collective_mindgraph_desktop.database import Database
from collective_mindgraph_desktop.models import GraphNode, Session, SessionDetail, Transcript
from collective_mindgraph_desktop.services import CollectiveMindGraphService
from collective_mindgraph_desktop.transcription import TranscriptionResult
from collective_mindgraph_desktop.ui.session_detail_panel import SessionDetailPanel


def build_service(tmp_path) -> CollectiveMindGraphService:
    return CollectiveMindGraphService(Database(tmp_path / "collective_mindgraph.sqlite3"))


def build_transcription_result(
    audio_path: str,
    quality_report: dict[str, object] | None = None,
    speaker_stats: list[dict[str, object]] | None = None,
    topics: list[dict[str, object]] | None = None,
    decisions: list[str] | None = None,
    action_items: list[str] | None = None,
) -> TranscriptionResult:
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
        topics=topics or [],
        decisions=decisions or [],
        action_items=action_items or [],
        speaker_stats=speaker_stats or [],
        quality_report=quality_report,
    )


def build_panel_with_detail(
    tmp_path,
    quality_report: dict[str, object] | None = None,
    speaker_stats: list[dict[str, object]] | None = None,
    topics: list[dict[str, object]] | None = None,
    decisions: list[str] | None = None,
    action_items: list[str] | None = None,
):
    app = QApplication.instance() or QApplication([])
    service = build_service(tmp_path)
    session = service.ingest_transcription_result(
        build_transcription_result(
            str(tmp_path / "sample.wav"),
            quality_report=quality_report,
            speaker_stats=speaker_stats,
            topics=topics,
            decisions=decisions,
            action_items=action_items,
        )
    )
    detail = service.get_session_detail(session.id)

    assert app is not None
    assert detail is not None

    panel = SessionDetailPanel()
    panel.set_detail(detail)
    return panel, detail


def test_session_detail_panel_shows_transcript_placeholder_without_transcripts(tmp_path):
    app = QApplication.instance() or QApplication([])
    service = build_service(tmp_path)
    session = service.create_session("Empty Session", "VOICE-MIC")
    detail = service.get_session_detail(session.id)

    assert app is not None
    assert detail is not None

    panel = SessionDetailPanel()
    panel.set_detail(detail)

    assert panel.transcript_list.count() == 1
    assert panel.transcript_list.item(0).text() == "No transcripts recorded for this session yet."
    assert not panel.transcript_list.item(0).flags()
    panel.close()


def test_session_detail_panel_renders_transcript_tooltips_and_selects_latest(tmp_path):
    app = QApplication.instance() or QApplication([])
    service = build_service(tmp_path)
    first_result = build_transcription_result(str(tmp_path / "sample_1.wav"))
    session = service.ingest_transcription_result(first_result)
    second_result = replace(
        build_transcription_result(str(tmp_path / "sample_2.wav")),
        conversation_id="conv_panel_tools_followup",
        text="Speaker_1: final follow up",
        corrected_text_output="Speaker_1: Final follow up.",
    )
    service.ingest_transcription_result(second_result, session_id=session.id)
    detail = service.get_session_detail(session.id)

    assert app is not None
    assert detail is not None

    panel = SessionDetailPanel()
    panel.set_detail(detail)

    assert panel.transcript_list.count() == 2
    assert panel.transcript_list.currentRow() == 1
    assert "Confidence" in panel.transcript_list.item(0).text()
    assert panel.transcript_list.item(1).toolTip() == detail.transcripts[-1].text
    assert panel.transcript_list.item(1).data(0x0100) == detail.transcripts[-1].id
    panel.close()


def test_session_detail_panel_shows_graph_placeholder_without_nodes(tmp_path):
    app = QApplication.instance() or QApplication([])
    service = build_service(tmp_path)
    session = service.create_session("Empty Session", "VOICE-MIC")
    detail = service.get_session_detail(session.id)

    assert app is not None
    assert detail is not None

    panel = SessionDetailPanel()
    panel.set_detail(detail)

    assert panel.graph_tree.topLevelItemCount() == 1
    assert panel.graph_tree.topLevelItem(0).text(0) == "No graph nodes yet."
    panel.close()


def test_session_detail_panel_groups_orphan_graph_nodes_under_unlinked_bucket():
    app = QApplication.instance() or QApplication([])
    detail = SessionDetail(
        session=Session(
            id=1,
            title="Synthetic Session",
            device_id="VOICE-MIC",
            status="active",
            created_at="2026-03-14T12:00:00Z",
            updated_at="2026-03-14T12:00:00Z",
        ),
        transcripts=[
            Transcript(
                id=1,
                session_id=1,
                text="Full transcript text for orphan tooltip.",
                confidence=0.95,
                created_at="2026-03-14T12:00:00Z",
            )
        ],
        graph_nodes=[
            GraphNode(
                id=1,
                session_id=1,
                transcript_id=1,
                parent_node_id=None,
                branch_type="root",
                branch_slot=None,
                node_text="Root node",
                override_reason=None,
                created_at="2026-03-14T12:00:00Z",
            ),
            GraphNode(
                id=2,
                session_id=1,
                transcript_id=1,
                parent_node_id=999,
                branch_type="main",
                branch_slot=None,
                node_text="Orphan node",
                override_reason=None,
                created_at="2026-03-14T12:01:00Z",
            ),
        ],
        snapshots=[],
        transcript_analyses={},
    )

    assert app is not None

    panel = SessionDetailPanel()
    panel.set_detail(detail)

    assert panel.graph_tree.topLevelItemCount() == 2
    assert panel.graph_tree.topLevelItem(0).text(0) == "Root node"
    assert panel.graph_tree.topLevelItem(1).text(0) == "Unlinked"
    assert (
        panel.graph_tree.topLevelItem(1).toolTip(0)
        == "Nodes with missing or invalid parent references."
    )
    assert panel.graph_tree.topLevelItem(1).childCount() == 1
    assert panel.graph_tree.topLevelItem(1).child(0).text(0) == "Orphan node"
    assert (
        panel.graph_tree.topLevelItem(1).child(0).toolTip(2)
        == "Full transcript text for orphan tooltip."
    )
    panel.close()


def test_session_detail_panel_renders_graph_branch_labels_and_truncated_transcript_tooltips():
    app = QApplication.instance() or QApplication([])
    transcript_text = (
        "Speaker_1: This is a deliberately long transcript excerpt that should truncate in the graph "
        "table while keeping the full text in the tooltip."
    )
    detail = SessionDetail(
        session=Session(
            id=1,
            title="Synthetic Session",
            device_id="VOICE-MIC",
            status="active",
            created_at="2026-03-14T12:00:00Z",
            updated_at="2026-03-14T12:00:00Z",
        ),
        transcripts=[
            Transcript(
                id=1,
                session_id=1,
                text=transcript_text,
                confidence=0.95,
                created_at="2026-03-14T12:00:00Z",
            )
        ],
        graph_nodes=[
            GraphNode(
                id=1,
                session_id=1,
                transcript_id=1,
                parent_node_id=None,
                branch_type="root",
                branch_slot=None,
                node_text="Root node",
                override_reason=None,
                created_at="2026-03-14T12:00:00Z",
            ),
            GraphNode(
                id=2,
                session_id=1,
                transcript_id=1,
                parent_node_id=1,
                branch_type="side",
                branch_slot=2,
                node_text="Side branch node",
                override_reason="Derived from follow-up cluster",
                created_at="2026-03-14T12:01:00Z",
            ),
        ],
        snapshots=[],
        transcript_analyses={},
    )

    assert app is not None

    panel = SessionDetailPanel()
    panel.set_detail(detail)

    root_item = panel.graph_tree.topLevelItem(0)
    side_item = root_item.child(0)
    expected_truncated = transcript_text[:69] + "..."

    assert root_item.text(1) == "root"
    assert side_item.text(1) == "side-2"
    assert side_item.toolTip(1) == "side-2\nDerived from follow-up cluster"
    assert side_item.text(2) == expected_truncated
    assert side_item.toolTip(2) == transcript_text
    panel.close()


def test_session_detail_panel_shows_placeholder_when_quality_report_is_missing(tmp_path):
    panel, _detail = build_panel_with_detail(tmp_path)

    assert panel._analysis_labels["quality"].text() == "No quality report available."
    panel.close()


def test_session_detail_panel_renders_quality_summary_with_warnings(tmp_path):
    panel, _detail = build_panel_with_detail(
        tmp_path,
        quality_report={
            "segment_count": 3,
            "speaker_count": 2,
            "unresolved_segments": 1,
            "overlap_ratio": 0.25,
            "avg_asr_confidence": 0.93,
            "avg_speaker_confidence": 0.88,
            "word_timing_coverage": 0.75,
            "corrected_change_ratio": 0.12,
            "topic_count": 0,
            "action_item_count": 0,
            "decision_count": 0,
            "question_count": 0,
            "summary_present": False,
            "warnings": ["Low confidence", "Unresolved speaker"],
        },
    )

    assert (
        panel._analysis_labels["quality"].text()
        == "2 speakers  |  overlap 0.25  |  coverage 0.75  |  Low confidence | Unresolved speaker"
    )
    panel.close()


def test_session_detail_panel_shows_snapshot_placeholder_without_snapshots(tmp_path):
    app = QApplication.instance() or QApplication([])
    service = build_service(tmp_path)
    session = service.create_session("Empty Session", "VOICE-MIC")
    detail = service.get_session_detail(session.id)

    assert app is not None
    assert detail is not None

    panel = SessionDetailPanel()
    panel.set_detail(detail)

    assert panel.snapshot_table.rowCount() == 1
    assert panel.snapshot_table.item(0, 0).text() == "No snapshots available."
    assert panel.snapshot_table.item(0, 1).text() == ""
    panel.close()


def test_session_detail_panel_renders_snapshot_hash_text_and_tooltips(tmp_path):
    panel, detail = build_panel_with_detail(tmp_path)

    assert detail.snapshots

    latest_snapshot = detail.snapshots[0]
    short_hash = f"{latest_snapshot.hash_sha256[:12]}..."

    assert panel.snapshot_table.rowCount() == 1
    assert panel.snapshot_table.item(0, 0).text() == latest_snapshot.created_at
    assert panel.snapshot_table.item(0, 1).text() == str(latest_snapshot.node_count)
    assert panel.snapshot_table.item(0, 2).text() == short_hash
    assert panel.snapshot_table.item(0, 2).toolTip() == latest_snapshot.hash_sha256
    assert panel.snapshot_table.item(0, 3).text() == latest_snapshot.hash_sha256
    assert panel.snapshot_table.item(0, 3).toolTip() == latest_snapshot.hash_sha256
    panel.close()


def test_session_detail_panel_shows_speaker_stats_placeholder_without_backend_stats(tmp_path):
    panel, _detail = build_panel_with_detail(tmp_path)

    assert panel.speaker_stats_list.count() == 1
    assert panel.speaker_stats_list.item(0).text() == "No speaker stats available."
    assert not panel.speaker_stats_list.item(0).flags()
    panel.close()


def test_session_detail_panel_renders_speaker_stats_text_and_tooltip(tmp_path):
    panel, _detail = build_panel_with_detail(
        tmp_path,
        speaker_stats=[
            {
                "speaker": "Speaker_1",
                "segment_count": 2,
                "speaking_seconds": 2.0,
                "overlap_segments": 1,
                "first_start": 0.0,
                "last_end": 3.0,
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
    )

    assert panel.speaker_stats_list.count() == 2
    assert panel.speaker_stats_list.item(0).text() == "Speaker_1  |  2 segments  |  2.0s spoken"
    assert panel.speaker_stats_list.item(0).toolTip() == (
        "Speaker_1\nSegments: 2\nSpeaking seconds: 2.000\nOverlap segments: 1"
    )
    assert panel.speaker_stats_list.item(1).text() == "Speaker_2  |  1 segments  |  1.0s spoken"
    panel.close()


def test_session_detail_panel_shows_insight_placeholder_without_topics_or_actions(tmp_path):
    panel, _detail = build_panel_with_detail(tmp_path)

    assert panel.insight_list.count() == 1
    assert panel.insight_list.item(0).text() == "No topics, decisions, or action items available."
    assert not panel.insight_list.item(0).flags()
    panel.close()


def test_session_detail_panel_renders_topics_decisions_and_actions_in_order(tmp_path):
    panel, _detail = build_panel_with_detail(
        tmp_path,
        topics=[{"label": "Planning", "start": 0.0, "end": 1.5}],
        decisions=["Ship Friday"],
        action_items=["Speaker_1: Send recap"],
    )

    assert panel.insight_list.count() == 3
    assert panel.insight_list.item(0).text() == "Topic: Planning (00:00.000 - 00:01.500)"
    assert panel.insight_list.item(1).text() == "Decision: Ship Friday"
    assert panel.insight_list.item(2).text() == "Action: Speaker_1: Send recap"
    panel.close()


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
