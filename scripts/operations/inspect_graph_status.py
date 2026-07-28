"""Inspect knowledge and evidence counts in the canonical database."""

from __future__ import annotations

from collective_mindgraph.engine.runtime_paths import canonical_database_path
from collective_mindgraph.infrastructure.persistence import SqliteDatabase


def main() -> int:
    path = canonical_database_path()
    print("--- Collective MindGraph Knowledge Status ---")
    print(f"Database: {path}")
    if not path.exists():
        print("The canonical database has not been created yet.")
        return 0
    database = SqliteDatabase(path)
    with database.connect() as connection:
        for table in (
            "meetings",
            "transcripts",
            "insights",
            "evidence_references",
            "knowledge_nodes",
            "knowledge_edges",
            "embeddings",
            "processing_jobs",
        ):
            count = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            print(f"{table}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
