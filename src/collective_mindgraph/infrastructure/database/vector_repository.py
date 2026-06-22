"""Simple SQLite-based vector store skeleton for Phase 2."""

import json
import sqlite3
import uuid
from contextlib import nullcontext
from typing import List, Dict, Any, Tuple, Optional
from collective_mindgraph.core.source_reference import SourceReference

class VectorRepository:
    """
    A naive SQLite vector store implementation.
    In a real production environment, this would wrap FAISS, Chroma, or LanceDB.
    """

    def __init__(self, database, expected_dim: Optional[int] = None):
        self.database = database
        self.expected_dim = expected_dim
        self._initialize_schema()

    def _connect(self):
        if hasattr(self.database, "connect"):
            return self.database.connect()
        return nullcontext(self.database)

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
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
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_v2_embeddings_node ON v2_embeddings(node_id);")

    def store_embedding(
        self,
        node_id: str,
        node_type: str,
        text_chunk: str | List[float],
        vector: List[float] | None = None,
        source_reference_id: Optional[str] = None,
    ) -> str:
        if vector is None:
            vector = text_chunk if isinstance(text_chunk, list) else []
            text_chunk = node_type
            node_type = "UNKNOWN"
        if self.expected_dim and len(vector) != self.expected_dim:
            raise ValueError(f"Vector dimension mismatch. Expected {self.expected_dim}, got {len(vector)}")
        
        emb_id = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO v2_embeddings (id, node_id, node_type, source_reference_id, vector_json, text_chunk, dimension, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (emb_id, node_id, node_type, source_reference_id, json.dumps(vector), str(text_chunk), len(vector))
            )
        return emb_id

    def search_similar(self, query_vector: List[float], top_k: int = 5, threshold: float = 0.0) -> List[Dict[str, Any]]:
        """
        Naive cosine similarity search in Python.
        Returns List of dicts with node_id, text, score, source_reference_id, node_type
        """
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT node_id, node_type, text_chunk, vector_json, source_reference_id FROM v2_embeddings"
            ).fetchall()
        
        results = []
        for row in rows:
            vec = json.loads(row["vector_json"])
            if len(vec) != len(query_vector):
                continue
                
            # Cosine similarity assuming normalized vectors
            sim = sum(a * b for a, b in zip(query_vector, vec))
            if sim >= threshold:
                score = round(float(sim), 4)
                results.append({
                    0: row["node_id"],
                    1: row["text_chunk"],
                    2: score,
                    "node_id": row["node_id"],
                    "node_type": row["node_type"],
                    "text": row["text_chunk"],
                    "score": score,
                    "source_reference_id": row["source_reference_id"]
                })
            
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM v2_embeddings").fetchone()
        return row[0] if row else 0
