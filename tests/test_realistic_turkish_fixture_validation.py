import json
import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from collective_mindgraph_desktop.database import Database
from collective_mindgraph_desktop.services import CollectiveMindGraphService
from collective_mindgraph_desktop.transcription import QueryResponse, QueryResultItem, TranscriptionResult
from collective_mindgraph_desktop.ui.main_window import MainWindow
from realtime_backend.app.config import Settings
from realtime_backend.app.models import ConversationTranscript, TranscriptSegment
from realtime_backend.app.pipeline.extraction import AIExtractionService
from realtime_backend.app.services.evidence_answer_service import EvidenceAnswerService
from realtime_backend.app.services.graph_reasoning import GraphReasoningService
from realtime_backend.app.services.graph_repository import ProductionGraphRepository as BackendGraphRepository


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "realistic_turkish_memory_session.txt"


def _read_fixture_sections() -> dict[str, str]:
    sections: dict[str, list[str]] = {"RAW_TRANSCRIPT": [], "CLEANED_TRANSCRIPT": []}
    current: str | None = None
    for line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip() == "[RAW_TRANSCRIPT]":
            current = "RAW_TRANSCRIPT"
            continue
        if line.strip() == "[CLEANED_TRANSCRIPT]":
            current = "CLEANED_TRANSCRIPT"
            continue
        if current and line.strip():
            sections[current].append(line)
    return {key: "\n".join(value) for key, value in sections.items()}


def _segments_from_cleaned_text(cleaned_text: str) -> list[TranscriptSegment]:
    segments = []
    for index, line in enumerate(cleaned_text.splitlines(), start=1):
        speaker, text = line.split(":", 1)
        start = float((index - 1) * 6)
        segments.append(
            TranscriptSegment(
                segment_id=f"tr-real-{index}",
                start=start,
                end=start + 5.5,
                speaker=speaker.strip(),
                raw_text=text.strip(),
                corrected_text=text.strip(),
                confidence=0.9,
            )
        )
    return segments


def _expected_extraction() -> dict[str, object]:
    return {
        "summary": "Odeme akisi, PostgreSQL indeksleri ve mobil surum yayin plani konusuldu.",
        "topics": ["Odeme akisi", "PostgreSQL indeksleri", "Mobil surum yayin plani"],
        "tasks": [
            {
                "title": "PostgreSQL indeks planini yarin oglene kadar hazirla",
                "assignee": "Ece",
                "segment_id": "tr-real-3",
            }
        ],
        "decisions": [
            {
                "decision": "Mobil surum yayini cuma gunune alindi",
                "reason": "Odeme akisi duzelmeden yayin yapilmamali.",
                "segment_id": "tr-real-5",
            }
        ],
        "entities": [
            {"title": "PostgreSQL", "segment_id": "tr-real-3"},
            {"title": "Redis", "segment_id": "tr-real-8"},
        ],
        "risks": [
            {
                "title": "Odeme akisi yavas kalirsa kampanya trafiginde sepet terk orani artabilir",
                "segment_id": "tr-real-6",
            },
            {
                "title": "Odeme akisi etkisi belirsiz",
                "segment_id": "tr-real-9",
            },
        ],
        "open_questions": [
            {
                "title": "Kampanya kuponu odeme servisinde mi mobil uygulamada mi dogrulanacak?",
                "segment_id": "tr-real-7",
            }
        ],
        "follow_ups": [
            {
                "title": "DevOps ekibiyle Redis onbellek limitlerini kontrol et",
                "segment_id": "tr-real-8",
            }
        ],
    }


async def _run_extraction(cleaned_text: str) -> ConversationTranscript:
    transcript = ConversationTranscript(
        conversation_id="realistic-turkish-fixture-1",
        source="tests/fixtures/realistic_turkish_memory_session.txt",
        language="tr",
        segments=_segments_from_cleaned_text(cleaned_text),
    )
    settings = Settings(extraction_mode="local_llm", llm_endpoint="http://127.0.0.1:1234/v1")
    with patch(
        "realtime_backend.app.pipeline.local_llm_provider.LocalLLMEndpointProvider.is_available",
        return_value=True,
    ), patch(
        "realtime_backend.app.pipeline.local_llm_provider.LocalLLMEndpointProvider.generate_structured_json",
        return_value=_expected_extraction(),
    ):
        return await AIExtractionService(settings).extract_intelligence(transcript)


def _desktop_result(raw_text: str, extracted: ConversationTranscript) -> TranscriptionResult:
    cleaned_text = "\n".join(f"{segment.speaker}: {segment.corrected_text}" for segment in extracted.segments)
    return TranscriptionResult(
        conversation_id=extracted.conversation_id,
        model_id="realistic-turkish-text-fixture",
        audio_path=str(FIXTURE_PATH),
        text=cleaned_text,
        raw_text_output=raw_text,
        corrected_text_output=cleaned_text,
        summary=extracted.summary,
        topics=[topic.model_dump() for topic in extracted.topics],
        action_items=[task.model_dump() for task in extracted.action_items],
        decisions=[decision.model_dump() for decision in extracted.decisions],
        people=["Ayşe", "Mehmet", "Ece"],
        segments=[segment.model_dump() for segment in extracted.segments],
        metadata={
            **extracted.metadata,
            "fixture_path": str(FIXTURE_PATH),
            "audio_fixture_status": "not_run_no_real_turkish_meeting_audio_fixture_available",
            "wer_accuracy_status": "not_measured_no_human_reference_audio_alignment",
        },
    )


def _nodes_by_type(service: CollectiveMindGraphService, session_id: int) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for node in service.get_session_graph_data(session_id)["nodes"]:
        grouped.setdefault(str(node["type"]), []).append(node)
    return grouped


def _metadata(node: dict[str, object]) -> dict[str, object]:
    return json.loads(str(node["metadata_json"]))


def _ask_memory(service: CollectiveMindGraphService, query: str, session_id: int, include_pending: bool = False):
    return EvidenceAnswerService(GraphReasoningService(BackendGraphRepository(service._database))).ask(
        query,
        session_id=str(session_id),
        include_pending=include_pending,
        mode="evidence_only",
    )


def _approve(service: CollectiveMindGraphService, *nodes: dict[str, object]) -> None:
    for node in nodes:
        assert service.update_node(str(node["id"]), {"review_status": "approved"})


@pytest.mark.asyncio
async def test_realistic_turkish_fixture_to_source_linked_memory_and_ui(qtbot, tmp_path):
    fixture = _read_fixture_sections()
    assert "ödeme akışı" in fixture["CLEANED_TRANSCRIPT"]
    assert "kahve içebiliriz" in fixture["CLEANED_TRANSCRIPT"]

    extracted = await _run_extraction(fixture["CLEANED_TRANSCRIPT"])
    assert extracted.metadata["extraction_source"] == "local_llm"
    assert extracted.action_items
    assert extracted.decisions
    assert extracted.metadata["risks"]
    assert extracted.metadata["open_questions"]
    assert extracted.metadata["follow_ups"]

    service = CollectiveMindGraphService(Database(tmp_path / "realistic_turkish_fixture.sqlite3"))
    session = service.ingest_transcription_result(_desktop_result(fixture["RAW_TRANSCRIPT"], extracted))
    detail = service.get_session_detail(session.id)
    assert detail is not None
    assert len(detail.transcripts) == 1

    transcript = detail.transcripts[0]
    analysis = detail.transcript_analyses[transcript.id]
    assert analysis.raw_text_output == fixture["RAW_TRANSCRIPT"]
    assert analysis.corrected_text_output == "\n".join(
        f"{segment.speaker}: {segment.corrected_text}" for segment in extracted.segments
    )
    assert len(analysis.segments) == 10
    assert analysis.segments[0].segment_id == "tr-real-1"
    assert analysis.segments[0].speaker == "Ayşe"
    assert analysis.segments[0].corrected_text.startswith("Merhaba ekip")

    graph_data = service.get_session_graph_data(session.id)
    assert graph_data["nodes"]
    assert graph_data["edges"]

    nodes = _nodes_by_type(service, session.id)
    for node_type in ("SEGMENT", "TASK", "DECISION", "TOPIC", "ENTITY", "RISK", "OPEN_QUESTION", "FOLLOW_UP"):
        assert node_type in nodes
        assert all(node["source_reference_id"] for node in nodes[node_type])

    task = next(node for node in nodes["TASK"] if "PostgreSQL" in node["title"])
    decision = nodes["DECISION"][0]
    postgres = next(node for node in nodes["ENTITY"] if node["title"] == "PostgreSQL")
    redis = next(node for node in nodes["ENTITY"] if node["title"] == "Redis")
    risk = next(node for node in nodes["RISK"] if "sepet terk" in node["title"])
    open_question = nodes["OPEN_QUESTION"][0]
    follow_up = nodes["FOLLOW_UP"][0]
    task_segment = next(node for node in nodes["SEGMENT"] if node["source_segment_id"] == "tr-real-3")

    assert task["source_segment_id"] == "tr-real-3"
    assert "PostgreSQL indeks plan" in task["source_text_preview"]
    assert task["source_timestamp_start"] == 12.0
    assert _metadata(task)["review_status"] == "pending"
    assert _metadata(decision)["review_status"] == "pending"

    all_task_decision_titles = " ".join(node["title"] for node in nodes["TASK"] + nodes["DECISION"])
    assert "kahve" not in all_task_decision_titles.lower()

    _approve(service, task_segment, task, postgres, redis, risk, open_question, follow_up, decision)
    assert service.update_node(open_question["id"], {"review_status": "edited", "title": open_question["title"]})

    approved_nodes = {node["id"]: node for node in service.get_session_graph_data(session.id)["nodes"]}
    assert _metadata(approved_nodes[task["id"]])["review_status"] == "approved"
    assert _metadata(approved_nodes[open_question["id"]])["review_status"] == "edited"

    ask_task = _ask_memory(service, "PostgreSQL görev", session.id)
    assert ask_task.answer_type == "evidence_only"
    assert ask_task.evidence_coverage_score == 1.0
    task_steps = [step for chain in ask_task.evidence_chains for step in chain.steps]
    task_step = next(step for step in task_steps if step.node_id == task["id"])
    assert task_step.source_reference_id
    assert task_step.source_session_id == str(session.id)
    assert task_step.source_segment_id == "tr-real-3"
    assert "PostgreSQL indeks plan" in task_step.text_preview

    unsupported = _ask_memory(service, "Docker görev", session.id)
    assert unsupported.evidence_coverage_score == 0.0
    assert not unsupported.evidence_chains
    assert not unsupported.source_session_ids
    assert "Docker" not in unsupported.short_answer

    with service._database.connect() as connection:
        source_count = connection.execute(
            "SELECT COUNT(*) AS count FROM v2_source_references WHERE session_id = ?",
            (str(session.id),),
        ).fetchone()["count"]
    assert source_count >= len(nodes["SEGMENT"])

    window = MainWindow(service)
    qtbot.addWidget(window)
    window._select_session(session.id)
    window.tabs.setCurrentWidget(window.diagnostics_page)
    assert window.diagnostics_page.labels["diarization_status"].text() == "NOT IMPLEMENTED / ROADMAP"
    assert window.diagnostics_page.labels["embedding_status"].text().startswith("DISABLED")

    window.tabs.setCurrentWidget(window.memory_search_page)
    window.memory_search_page._handle_query_finished(
        QueryResponse(
            query="PostgreSQL",
            results=[
                QueryResultItem(
                    result_type="TASK",
                    text=str(task["title"]),
                    source_session_id=str(session.id),
                    source_segment_id="tr-real-3",
                    matched_by="keyword",
                    score=1.0,
                    preview=str(task["source_text_preview"]),
                )
            ],
        )
    )
    assert window.memory_search_page.results_list.count() == 1

    window.memory_search_page.ask_panel._handle_finished(ask_task)
    assert "PostgreSQL" in window.memory_search_page.ask_panel.answer_box.toPlainText()
