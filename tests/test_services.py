import json

from collective_mindgraph_desktop.database import Database
from collective_mindgraph_desktop.services import CollectiveMindGraphService, SnapshotHasher


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
    assert set(payload) == {"session", "transcripts", "graph_nodes", "snapshots"}
    assert payload == exported_payload
    assert payload["session"]["id"] == session.id
    assert payload["transcripts"]
    assert payload["graph_nodes"]
    assert payload["snapshots"]
