import json

from collective_mindgraph_user_app.database import Database
from collective_mindgraph_user_app.services import CollectiveMindGraphCompanionService


def build_service(tmp_path) -> CollectiveMindGraphCompanionService:
    return CollectiveMindGraphCompanionService(Database(tmp_path / "companion.sqlite3"))


def test_session_create_list_and_search(tmp_path):
    service = build_service(tmp_path)

    alpha = service.create_session("Weekly Review", "Personal", "Routines", "Weekly Review", "Focused")
    beta = service.create_session("Python Notes", "Learning", "Python", "Study Sprint", "Curious")

    listed = service.list_sessions()
    title_matches = service.list_sessions("Weekly")
    category_matches = service.list_sessions("Python")
    template_matches = service.list_sessions("Study Sprint")

    assert {session.id for session in listed} == {alpha.id, beta.id}
    assert [session.id for session in title_matches] == [alpha.id]
    assert [session.id for session in category_matches] == [beta.id]
    assert [session.id for session in template_matches] == [beta.id]


def test_note_save_and_load(tmp_path):
    service = build_service(tmp_path)
    session = service.create_session("Journal", "Personal", "Reset", "Journal Reflection", "Reflective")
    html = "<h2>Today</h2><p><b>One good thing</b> happened.</p>"

    saved_note = service.save_note(session.id, html)
    detail = service.get_session_detail(session.id)

    assert detail is not None
    assert detail.note is not None
    assert saved_note.content == html
    assert detail.note.content == html
    assert any(item.kind == "idea" for item in detail.session_flow)
    assert any(node.kind == "session_root" for node in detail.session_graph)


def test_demo_seed_creates_category_map_data(tmp_path):
    service = build_service(tmp_path)

    sessions = service.seed_demo_data()

    assert len(sessions) == 3
    for session in sessions:
        detail = service.get_session_detail(session.id)
        assert detail is not None
        assert detail.note is not None
        assert detail.main_category.name
        assert detail.session_flow
        assert detail.session_graph
        assert any(item.kind == "session" and item.entity_id == session.id for item in detail.workspace_map)


def test_export_payload(tmp_path):
    service = build_service(tmp_path)
    session = service.seed_demo_data()[0]
    export_path = tmp_path / "session_export.json"

    payload = service.export_session(session.id, export_path)
    exported_payload = json.loads(export_path.read_text(encoding="utf-8"))

    assert export_path.exists()
    assert set(payload) == {
        "session",
        "note",
        "main_category",
        "sub_category",
        "session_flow",
        "session_graph",
        "workspace_map",
    }
    assert payload == exported_payload
    assert payload["session"]["id"] == session.id
    assert payload["note"] is not None
    assert payload["main_category"]["name"]
    assert payload["session_flow"]
    assert payload["session_graph"]
    assert payload["workspace_map"]


def test_workspace_map_groups_sessions_under_subcategories(tmp_path):
    service = build_service(tmp_path)
    alpha = service.create_session("Feature Ideas", "Product", "Discovery", "Idea Canvas", "Curious")
    beta = service.create_session("Research Notes", "Product", "Discovery", "Project Outline", "Focused")
    service.create_session("Inbox Session", "Inbox", "", "Freeform Session", "Calm")

    workspace_map = service.get_workspace_map(alpha.id)

    assert any(item.kind == "main_category" and item.title == "Product" for item in workspace_map)
    assert any(item.kind == "sub_category" and item.title == "Discovery" for item in workspace_map)
    assert any(item.kind == "session" and item.entity_id == alpha.id and item.is_selected for item in workspace_map)
    assert any(item.kind == "session" and item.entity_id == beta.id for item in workspace_map)


def test_create_related_session_keeps_category_path(tmp_path):
    service = build_service(tmp_path)
    source = service.create_session("Source Session", "Work", "Planning", "Idea Canvas", "Focused")

    related = service.create_related_session(source.id, "Spin Off Idea")

    assert related.main_category_name == source.main_category_name
    assert related.sub_category_name == source.sub_category_name
    assert related.title == "Spin Off Idea"


def test_session_graph_links_related_sessions(tmp_path):
    service = build_service(tmp_path)
    source = service.create_session("Source Session", "Work", "Planning", "Idea Canvas", "Focused")
    related = service.create_related_session(source.id, "Follow Up Branch")
    service.append_quick_idea(source.id, "Trace the dependency chain")

    detail = service.get_session_detail(source.id)

    assert detail is not None
    assert any(item.kind == "idea" and "dependency chain" in item.detail.lower() for item in detail.session_flow)
    assert any(node.kind == "related_session" and node.session_id == related.id for node in detail.session_graph)
