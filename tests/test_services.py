import json

from collective_mindgraph_desktop.database import Database
from collective_mindgraph_desktop.models import TranscriptAnalysisSegment
from collective_mindgraph_desktop.services import CollectiveMindGraphService, SnapshotHasher
from collective_mindgraph_desktop.transcription import TranscriptionResult


def build_service(tmp_path) -> CollectiveMindGraphService:
    return CollectiveMindGraphService(Database(tmp_path / "collective_mindgraph.sqlite3"))


def test_seed_demo_data_creates_sessions_and_related_records(tmp_path):
    service = build_service(tmp_path)

    sessions = service.seed_demo_data()
    summary = service.get_app_summary()

    assert len(sessions) == 3
    assert summary.total_sessions == 3
    assert summary.total_transcripts > 0
    assert summary.total_nodes > 0
    assert summary.total_snapshots >= 6

    for session in sessions:
        detail = service.get_session_detail(session.id)
        assert detail is not None
        assert detail.transcripts
        assert detail.graph_nodes
        assert detail.snapshots


def test_snapshot_hash_is_deterministic(tmp_path):
    service = build_service(tmp_path)
    session = service.seed_demo_data()[0]
    detail = service.get_session_detail(session.id)
    assert detail is not None

    hash_one = SnapshotHasher.compute(detail.graph_nodes)
    hash_two = SnapshotHasher.compute(list(reversed(detail.graph_nodes)))

    assert hash_one == hash_two


def test_rebuild_snapshots_keeps_current_graph_hash_stable(tmp_path):
    service = build_service(tmp_path)
    session = service.seed_demo_data()[0]
    detail_before = service.get_session_detail(session.id)
    assert detail_before is not None

    expected_hash = SnapshotHasher.compute(detail_before.graph_nodes)
    assert detail_before.snapshots[0].hash_sha256 == expected_hash

    rebuilt = service.rebuild_snapshots(session.id)
    detail_after = service.get_session_detail(session.id)

    assert rebuilt
    assert detail_after is not None
    assert len(detail_after.snapshots) == 1
    assert detail_after.snapshots[0].hash_sha256 == expected_hash


def test_export_session_payload(tmp_path):
    service = build_service(tmp_path)
    session = service.seed_demo_data()[0]
    export_path = tmp_path / "session_export.json"

    payload = service.export_session(session.id, export_path)
    exported_payload = json.loads(export_path.read_text(encoding="utf-8"))

    assert export_path.exists()
    assert set(payload) == {"session", "transcripts", "graph_nodes", "snapshots", "transcript_analyses"}
    assert payload == exported_payload
    assert payload["session"]["id"] == session.id
    assert payload["transcripts"]
    assert payload["graph_nodes"]
    assert payload["snapshots"]


def test_ingest_transcript_creates_a_new_session_when_none_is_selected(tmp_path):
    service = build_service(tmp_path)

    session = service.ingest_transcript("Map out the incident and isolate the first failure signal.")
    detail = service.get_session_detail(session.id)
    summary = service.get_app_summary()

    assert detail is not None
    assert session.title == "Map out the incident and isolate the first failure signal."
    assert summary.total_sessions == 1
    assert summary.total_transcripts == 1
    assert summary.total_nodes == 1
    assert summary.total_snapshots == 1
    assert detail.transcripts[0].text == "Map out the incident and isolate the first failure signal."
    assert detail.graph_nodes[0].branch_type == "root"
    assert detail.graph_nodes[0].parent_node_id is None


def test_ingest_transcript_appends_to_the_selected_session(tmp_path):
    service = build_service(tmp_path)

    session = service.ingest_transcript("Track the incoming signal and keep the main hypothesis visible.")
    continued = service.ingest_transcript(
        "Add a follow-up note about the backup route staying available.",
        session.id,
    )
    detail = service.get_session_detail(session.id)

    assert continued.id == session.id
    assert detail is not None
    assert len(detail.transcripts) == 2
    assert len(detail.graph_nodes) == 2
    assert len(detail.snapshots) == 1
    assert detail.graph_nodes[0].branch_type == "root"
    assert detail.graph_nodes[1].branch_type == "main"
    assert detail.graph_nodes[1].parent_node_id == detail.graph_nodes[0].id


def test_ingest_transcription_result_persists_backend_analysis(tmp_path):
    service = build_service(tmp_path)

    session = service.ingest_transcription_result(
        TranscriptionResult(
            text="Speaker_1: merhaba\nSpeaker_2: selam",
            model_id="realtime_backend",
            audio_path=str(tmp_path / "sample.wav"),
            conversation_id="conv_123",
            raw_text_output="[00:00.000 - 00:01.000] Speaker_1: merhaba",
            corrected_text_output="[00:00.000 - 00:01.000] Speaker_1: Merhaba.",
            speaker_count=2,
            summary="Iki kisilik kisa selamlama.",
            topics=[{"label": "Selamlama", "start": 0.0, "end": 1.0}],
            action_items=["Takibe devam et"],
            decisions=["Gorusmeyi surdur"],
            speaker_stats=[
                {
                    "speaker": "Speaker_1",
                    "segment_count": 1,
                    "speaking_seconds": 1.0,
                    "overlap_segments": 0,
                    "first_start": 0.0,
                    "last_end": 1.0,
                }
            ],
            segments=[
                {
                    "segment_id": "seg_1",
                    "start": 0.0,
                    "end": 1.0,
                    "speaker": "Speaker_1",
                    "raw_text": "merhaba",
                    "corrected_text": "Merhaba.",
                    "confidence": 0.9,
                    "speaker_confidence": 1.0,
                    "overlap": False,
                    "notes": ["cleaned"],
                }
            ],
            quality_report={
                "segment_count": 1,
                "speaker_count": 1,
                "unresolved_segments": 0,
                "overlap_ratio": 0.0,
                "avg_asr_confidence": 0.9,
                "avg_speaker_confidence": 1.0,
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
    )

    detail = service.get_session_detail(session.id)

    assert detail is not None
    transcript = detail.transcripts[-1]
    analysis = detail.transcript_analyses[transcript.id]
    assert analysis.backend_conversation_id == "conv_123"
    assert analysis.summary == "Iki kisilik kisa selamlama."
    assert analysis.segments[0].corrected_text == "Merhaba."
    assert analysis.action_items == ["Takibe devam et"]
    assert len(detail.graph_nodes) == 3
    assert detail.graph_nodes[1].branch_type == "side"
    assert detail.graph_nodes[2].branch_type == "side"
    assert "Summary:" in detail.graph_nodes[1].node_text
    assert "Decision:" in detail.graph_nodes[2].node_text


def test_save_transcript_analysis_corrections_updates_transcript_and_graph_node(tmp_path):
    service = build_service(tmp_path)
    session = service.ingest_transcription_result(
        TranscriptionResult(
            text="Speaker_1: merhaba",
            model_id="realtime_backend",
            audio_path=str(tmp_path / "sample.wav"),
            conversation_id="conv_abc",
            corrected_text_output="[00:00.000 - 00:01.000] Speaker_1: Merhaba.",
            segments=[
                {
                    "segment_id": "seg_1",
                    "start": 0.0,
                    "end": 1.0,
                    "speaker": "Speaker_1",
                    "raw_text": "merhaba",
                    "corrected_text": "Merhaba.",
                    "confidence": 0.9,
                    "speaker_confidence": 1.0,
                    "overlap": False,
                    "notes": [],
                }
            ],
        )
    )
    detail = service.get_session_detail(session.id)
    assert detail is not None
    transcript = detail.transcripts[-1]
    analysis = detail.transcript_analyses[transcript.id]

    service.save_transcript_analysis_corrections(
        transcript.id,
        [
            TranscriptAnalysisSegment(
                segment_id=analysis.segments[0].segment_id,
                start=analysis.segments[0].start,
                end=analysis.segments[0].end,
                speaker="Hasan",
                raw_text=analysis.segments[0].raw_text,
                corrected_text="Merhaba dunya.",
                confidence=analysis.segments[0].confidence,
                speaker_confidence=analysis.segments[0].speaker_confidence,
                overlap=analysis.segments[0].overlap,
                notes=analysis.segments[0].notes,
            )
        ],
    )

    refreshed_detail = service.get_session_detail(session.id)

    assert refreshed_detail is not None
    assert refreshed_detail.transcripts[-1].text == "Hasan: Merhaba dunya."
    assert refreshed_detail.graph_nodes[-1].node_text == "Hasan: Merhaba dunya."
    refreshed_analysis = refreshed_detail.transcript_analyses[transcript.id]
    assert refreshed_analysis.segments[0].speaker == "Hasan"
    assert refreshed_analysis.corrected_text_output.endswith("Hasan: Merhaba dunya.")
