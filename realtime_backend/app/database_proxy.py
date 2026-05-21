"""SQLite database proxy for backend services."""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

class DatabaseProxy:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(str(self.path))
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self):
        schema = """
        CREATE TABLE IF NOT EXISTS v2_source_references (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            segment_id TEXT,
            document_id TEXT,
            chunk_id TEXT,
            timestamp_start REAL,
            timestamp_end REAL,
            text_preview TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS v2_graph_nodes (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            title TEXT,
            text_content TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            source_reference_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (source_reference_id) REFERENCES v2_source_references(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS v2_graph_edges (
            id TEXT PRIMARY KEY,
            source_node_id TEXT NOT NULL,
            target_node_id TEXT NOT NULL,
            edge_type TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            confidence REAL NOT NULL DEFAULT 1.0,
            source_reference_id TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (source_node_id) REFERENCES v2_graph_nodes(id) ON DELETE CASCADE,
            FOREIGN KEY (target_node_id) REFERENCES v2_graph_nodes(id) ON DELETE CASCADE,
            FOREIGN KEY (source_reference_id) REFERENCES v2_source_references(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS v2_embeddings (
            id TEXT PRIMARY KEY,
            node_id TEXT NOT NULL,
            node_type TEXT NOT NULL,
            source_reference_id TEXT,
            vector_json TEXT NOT NULL,
            text_chunk TEXT NOT NULL,
            dimension INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_v2_graph_nodes_type ON v2_graph_nodes(type);
        CREATE INDEX IF NOT EXISTS idx_v2_graph_edges_source ON v2_graph_edges(source_node_id);
        CREATE INDEX IF NOT EXISTS idx_v2_graph_edges_target ON v2_graph_edges(target_node_id);
        CREATE INDEX IF NOT EXISTS idx_v2_embeddings_node ON v2_embeddings(node_id);
        """
        with self.connect() as connection:
            connection.executescript(schema)
