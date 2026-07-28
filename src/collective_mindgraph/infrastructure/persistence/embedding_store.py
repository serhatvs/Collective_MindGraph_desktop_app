"""SQLite vector storage with deterministic cosine retrieval."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from collective_mindgraph.application.ports import EmbeddingMatch
from collective_mindgraph.domain import EvidenceId, KnowledgeNodeId

from .sqlite_database import SqliteDatabase


class SqliteEmbeddingStore:
    def __init__(self, database: SqliteDatabase, expected_dimension: int) -> None:
        if expected_dimension <= 0:
            raise ValueError("Embedding dimension must be positive.")
        self._database = database
        self._expected_dimension = expected_dimension

    def put(
        self,
        *,
        node_id: KnowledgeNodeId,
        vector: list[float],
        text_chunk: str,
        evidence_id: EvidenceId | None = None,
    ) -> str:
        self._validate(vector)
        embedding_id = str(uuid5(NAMESPACE_URL, f"embedding:{node_id}"))
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO embeddings (
                    id, node_id, evidence_id, vector_json,
                    text_chunk, dimension, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    node_id = excluded.node_id,
                    evidence_id = excluded.evidence_id,
                    vector_json = excluded.vector_json,
                    text_chunk = excluded.text_chunk,
                    dimension = excluded.dimension,
                    created_at = excluded.created_at
                """,
                (
                    embedding_id,
                    str(node_id),
                    str(evidence_id) if evidence_id else None,
                    json.dumps(vector),
                    text_chunk,
                    self._expected_dimension,
                    datetime.now(tz=UTC).isoformat(),
                ),
            )
        return embedding_id

    def search(
        self,
        vector: list[float],
        *,
        limit: int = 10,
        threshold: float = 0.3,
    ) -> tuple[EmbeddingMatch, ...]:
        self._validate(vector)
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT node_id, evidence_id, text_chunk, vector_json, dimension
                FROM embeddings
                """
            ).fetchall()
        matches: list[EmbeddingMatch] = []
        for row in rows:
            if int(row["dimension"]) != self._expected_dimension:
                continue
            candidate = [float(value) for value in json.loads(str(row["vector_json"]))]
            score = _cosine_similarity(vector, candidate)
            if score < threshold:
                continue
            matches.append(
                EmbeddingMatch(
                    node_id=KnowledgeNodeId(str(row["node_id"])),
                    score=score,
                    text_chunk=str(row["text_chunk"]),
                    evidence_id=(
                        EvidenceId(str(row["evidence_id"])) if row["evidence_id"] else None
                    ),
                )
            )
        matches.sort(key=lambda item: (-item.score, str(item.node_id)))
        return tuple(matches[: max(1, limit)])

    def count(self) -> int:
        with self._database.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0])

    def _validate(self, vector: list[float]) -> None:
        if len(vector) != self._expected_dimension:
            raise ValueError(f"Expected {self._expected_dimension} values, received {len(vector)}.")


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
