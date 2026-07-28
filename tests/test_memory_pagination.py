from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from collective_mindgraph.domain import (
    EvidenceId,
    EvidenceReference,
    KnowledgeNode,
    KnowledgeNodeId,
    KnowledgeNodeKind,
    MeetingId,
    SegmentId,
)
from collective_mindgraph.engine.main import create_app
from collective_mindgraph.engine.settings import EngineSettings


def _settings(tmp_path) -> EngineSettings:
    return EngineSettings(
        data_dir=tmp_path / "data",
        temp_dir=tmp_path / "temp",
        database_path=tmp_path / "data" / "collective_mindgraph.sqlite3",
        asr_provider="mock",
        vad_provider="energy",
        diarizer_provider="fallback",
        embedding_provider="disabled",
        llm_provider="disabled",
    )


def test_memory_search_cursor_reaches_results_after_first_page(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        meeting_id = MeetingId(
            client.post("/api/v1/meetings", json={"title": "Pagination"}).json()["id"]
        )
        context = client.app.state.engine_context
        now = datetime.now(tz=UTC)
        for index in range(65):
            evidence_id = EvidenceId(f"evidence-{index:03d}")
            segment_id = SegmentId(f"segment-{index:03d}")
            context.knowledge.save_evidence(
                EvidenceReference(
                    id=evidence_id,
                    meeting_id=meeting_id,
                    segment_id=None,
                    text_preview=f"roadmap item {index:03d}",
                    created_at=now,
                )
            )
            context.knowledge.save_node(
                KnowledgeNode(
                    id=KnowledgeNodeId(f"node-{index:03d}"),
                    meeting_id=meeting_id,
                    kind=KnowledgeNodeKind.NOTE,
                    title=f"roadmap item {index:03d}",
                    body=f"roadmap item {index:03d}",
                    evidence_id=evidence_id,
                    attributes={"review": "accepted", "segment_id": str(segment_id)},
                    created_at=now,
                    updated_at=now,
                )
            )

        first = client.get(
            "/api/v1/memory/search",
            params={"q": "roadmap", "limit": 20},
        ).json()
        second = client.get(
            "/api/v1/memory/search",
            params={"q": "roadmap", "limit": 20, "cursor": first["next_cursor"]},
        ).json()

        assert first["total"] == 65
        assert len(first["items"]) == 20
        assert first["next_cursor"] == "20"
        assert len(second["items"]) == 20
        assert {item["node_id"] for item in first["items"]}.isdisjoint(
            item["node_id"] for item in second["items"]
        )
        assert first["warnings"] == [
            "Semantic provider unavailable; keyword and graph fallback used."
        ]
