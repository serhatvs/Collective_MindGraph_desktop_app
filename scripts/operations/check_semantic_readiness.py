"""Report canonical local-embedding configuration and index size."""

from __future__ import annotations

from collective_mindgraph.engine.runtime_paths import canonical_database_path
from collective_mindgraph.engine.settings import EngineSettings
from collective_mindgraph.infrastructure.persistence import SqliteDatabase


def main() -> int:
    settings = EngineSettings()
    database_path = canonical_database_path()
    print("--- Collective MindGraph Semantic Readiness ---")
    print(f"Provider: {settings.embedding_provider}")
    print(f"Model path: {settings.embedding_model_path or '(not configured)'}")
    print(f"Database: {database_path}")
    if not database_path.exists():
        print("EMPTY: The canonical database has not been created yet.")
        return 0
    with SqliteDatabase(database_path).connect() as connection:
        count = int(connection.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0])
    print(f"Indexed embeddings: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
