from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from collective_mindgraph.domain import (
    EvidenceId,
    EvidenceReference,
    Insight,
    InsightId,
    InsightKind,
    JobId,
    KnowledgeNode,
    KnowledgeNodeId,
    KnowledgeNodeKind,
    ProcessingJob,
    ProcessingStatus,
    ReviewDecision,
    SegmentId,
    Transcript,
    TranscriptId,
    TranscriptSegment,
)
from collective_mindgraph.engine.main import create_app
from collective_mindgraph.engine.settings import EngineSettings


def _settings(tmp_path, name: str = "engine") -> EngineSettings:
    root = tmp_path / name
    return EngineSettings(
        data_dir=root / "data",
        temp_dir=root / "temp",
        database_path=root / "collective_mindgraph.sqlite3",
        asr_provider="mock",
        vad_provider="energy",
        diarizer_provider="fallback",
        embedding_provider="mock",
        llm_provider="disabled",
    )


def _seed_reviewable_memory(client: TestClient) -> tuple[int, object]:
    created = client.post("/api/v1/meetings", json={"title": "Memory review"})
    meeting_id = int(created.json()["id"])
    context = client.app.state.engine_context
    now = datetime.now(tz=UTC)
    context.transcripts.save(
        Transcript(
            id=TranscriptId(0),
            meeting_id=meeting_id,
            conversation_id="review-flow",
            provider="test",
            language="tr",
            raw_text="Ham karar metni",
            corrected_text="Düzeltilmiş karar metni",
            created_at=now,
            updated_at=now,
            segments=(
                TranscriptSegment(
                    id=SegmentId("segment-1"),
                    transcript_id=TranscriptId(0),
                    position=0,
                    start_seconds=0,
                    end_seconds=2,
                    raw_text="Ham karar metni",
                    corrected_text="Düzeltilmiş karar metni",
                ),
            ),
        )
    )
    evidence = EvidenceReference(
        id=EvidenceId("evidence-1"),
        meeting_id=meeting_id,
        segment_id=SegmentId("segment-1"),
        start_seconds=0,
        end_seconds=2,
        text_preview="Düzeltilmiş karar metni",
        extractor="test",
        created_at=now,
    )
    context.knowledge.save_evidence(evidence)
    attributes = {"review": "pending", "needs_review": False}
    context.insights.save(
        Insight(
            id=InsightId("insight-1"),
            meeting_id=meeting_id,
            kind=InsightKind.DECISION,
            title="SQLite kullanılacak",
            body="Kalıcı veri SQLite içinde tutulacak.",
            review=ReviewDecision.PENDING,
            evidence_id=evidence.id,
            created_at=now,
            updated_at=now,
            attributes=attributes,
        )
    )
    context.knowledge.save_node(
        KnowledgeNode(
            id=KnowledgeNodeId("insight-1"),
            meeting_id=meeting_id,
            kind=KnowledgeNodeKind.DECISION,
            title="SQLite kullanılacak",
            body="Kalıcı veri SQLite içinde tutulacak.",
            evidence_id=evidence.id,
            attributes=attributes,
            created_at=now,
            updated_at=now,
        )
    )
    return meeting_id, context


def test_review_correction_search_and_evidence_flow(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        meeting_id, context = _seed_reviewable_memory(client)

        hidden = client.get("/api/v1/memory/search", params={"q": "SQLite"}).json()
        assert hidden["items"] == []

        accepted = client.patch(
            "/api/v1/insights/insight-1/review",
            json={
                "decision": "accepted",
                "title": "SQLite kararı",
                "body": "Kalıcı veri yerel SQLite içinde tutulacak.",
            },
        )
        assert accepted.status_code == 200
        assert accepted.json()["review"] == "accepted"
        node = context.knowledge.get_node(KnowledgeNodeId("insight-1"))
        assert node is not None
        assert node.attributes["review"] == "accepted"
        assert node.title == "SQLite kararı"

        search = client.get(
            "/api/v1/memory/search",
            params={"q": "SQLite", "mode": "hybrid"},
        )
        assert search.status_code == 200
        assert search.json()["items"][0]["evidence"]["id"] == "evidence-1"

        answer = client.get(
            "/api/v1/memory/ask",
            params={"q": "SQLite", "mode": "evidence_only"},
        ).json()
        assert answer["sources"][0]["meeting_id"] == int(meeting_id)
        assert answer["sources"][0]["segment_id"] == "segment-1"

        corrected = client.patch(
            "/api/v1/transcript-segments/segment-1",
            json={"corrected_text": "Kullanıcı tarafından düzeltilmiş metin"},
        )
        assert corrected.status_code == 200
        transcript = context.transcripts.latest_for_meeting(meeting_id)
        assert transcript is not None
        assert transcript.raw_text == "Ham karar metni"
        assert transcript.segments[0].raw_text == "Ham karar metni"
        assert transcript.segments[0].corrected_text == ("Kullanıcı tarafından düzeltilmiş metin")
        assert context.insights.get(InsightId("insight-1")).needs_review
        assert context.knowledge.get_node(KnowledgeNodeId("insight-1")).attributes["needs_review"]

        rejected = client.patch(
            "/api/v1/insights/insight-1/review",
            json={"decision": "rejected"},
        )
        assert rejected.status_code == 200
        assert (
            client.get(
                "/api/v1/memory/search",
                params={"q": "SQLite"},
            ).json()["items"]
            == []
        )


def test_job_settings_and_versioned_export_import(tmp_path):
    with TestClient(create_app(_settings(tmp_path, "source"))) as client:
        meeting_id, context = _seed_reviewable_memory(client)
        now = datetime.now(tz=UTC)
        context.jobs.create(
            ProcessingJob(
                id=JobId("job-1"),
                meeting_id=meeting_id,
                kind="transcription",
                status=ProcessingStatus.RUNNING,
                progress=25,
                message="Processing",
                created_at=now,
                updated_at=now,
            )
        )
        cancelled = client.post("/api/v1/jobs/job-1/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"

        settings = client.put(
            "/api/v1/settings",
            json={"language": "en", "transcription_quality": "balanced"},
        )
        assert settings.status_code == 200
        assert settings.json()["language"] == "en"

        exported = client.get("/api/v1/export").json()
        assert exported["format_version"] == 4
        assert exported["format"] == "collective_mindgraph"

    with TestClient(create_app(_settings(tmp_path, "target"))) as target:
        imported = target.post("/api/v1/import", json=exported)
        assert imported.status_code == 200
        assert imported.json()["imported"]["meetings"] == 1
        dashboard = target.get("/api/v1/dashboard").json()
        assert dashboard["total_meetings"] == 1
        assert dashboard["total_transcripts"] == 1


def test_legacy_graph_export_is_still_importable(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "golden" / "legacy_graph_export.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    with TestClient(create_app(_settings(tmp_path))) as client:
        response = client.post("/api/v1/import", json=payload)
        assert response.status_code == 200
        assert response.json()["imported"]["knowledge_nodes"] == 1
