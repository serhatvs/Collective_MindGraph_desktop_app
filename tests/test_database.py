from collective_mindgraph_desktop.database import Database
from collective_mindgraph_desktop.repositories import SessionRepository


def test_initialize_creates_schema(tmp_path):
    database = Database(tmp_path / "collective_mindgraph.sqlite3")
    database.initialize()

    with database.connect() as connection:
        table_names = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }

    assert {"sessions", "transcripts", "graph_nodes", "snapshots"}.issubset(table_names)


def test_session_create_list_and_search(tmp_path):
    database = Database(tmp_path / "collective_mindgraph.sqlite3")
    database.initialize()
    repository = SessionRepository(database)

    alpha = repository.create(
        title="Alpha Investigation",
        device_id="WS-01",
        status="active",
        timestamp="2026-03-06 09:00:00",
    )
    beta = repository.create(
        title="Beta Review",
        device_id="DEVICE-77",
        status="paused",
        timestamp="2026-03-06 09:05:00",
    )

    listed_sessions = repository.list()
    title_matches = repository.list("Alpha")
    device_matches = repository.list("DEVICE-77")

    assert [session.id for session in listed_sessions] == [beta.id, alpha.id]
    assert [session.id for session in title_matches] == [alpha.id]
    assert [session.id for session in device_matches] == [beta.id]
