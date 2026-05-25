from collective_mindgraph_user_app.database import Database


def test_initialize_creates_schema(tmp_path):
    database = Database(tmp_path / "companion.sqlite3")
    database.initialize()

    with database.connect() as connection:
        table_names = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }

    assert {
        "main_categories",
        "sub_categories",
        "user_sessions",
        "note_entries",
    }.issubset(table_names)
