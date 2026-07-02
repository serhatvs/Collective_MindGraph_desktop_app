import json

from collective_mindgraph_desktop.database import Database
from collective_mindgraph_desktop.services import CollectiveMindGraphService
from collective_mindgraph_desktop.transcription import TranscriptionResult
from realtime_backend.app.services.evidence_answer_service import EvidenceAnswerService
from realtime_backend.app.services.graph_reasoning import GraphReasoningService
from realtime_backend.app.services.graph_repository import ProductionGraphRepository as BackendGraphRepository
from realtime_backend.app.services.hybrid_memory_query_service import HybridMemoryQueryService


def _service(tmp_path, name: str) -> CollectiveMindGraphService:
    return CollectiveMindGraphService(Database(tmp_path / name))


def _backend_graph(service: CollectiveMindGraphService) -> BackendGraphRepository:
    return BackendGraphRepository(service._database)


def _nodes_by_type(service: CollectiveMindGraphService, session_id: int) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for node in service.get_session_graph_data(session_id)["nodes"]:
        grouped.setdefault(str(node["type"]), []).append(node)
    return grouped


def _metadata(node: dict[str, object]) -> dict[str, object]:
    return json.loads(str(node["metadata_json"]))


def _query_node_ids(service: CollectiveMindGraphService, query: str) -> set[str]:
    result = HybridMemoryQueryService(
        _backend_graph(service),
        vector_repo=None,
        embedding_provider=None,
    ).execute_query(query, use_keyword=True, use_vector=False, use_graph=True)
    return {node.id for node in result.nodes}


def _ask_memory(service: CollectiveMindGraphService, query: str, session_id: int):
    return EvidenceAnswerService(GraphReasoningService(_backend_graph(service))).ask(
        query,
        session_id=str(session_id),
        include_pending=False,
        mode="evidence_only",
    )


def _turkish_meeting_result() -> TranscriptionResult:
    return TranscriptionResult(
        conversation_id="memory-e2e-tr-1",
        model_id="fixture-cleaned-transcript",
        audio_path="memory_track_fixture.wav",
        text=(
            "Ekip PostgreSQL gecisini konustu. Ayse indeks planini hazirlayacak. "
            "Kubernetes pilotu onaylandi. Takvim gecikmesi riski var. "
            "DevOps sahipligi acik kaldi."
        ),
        raw_text_output=(
            "Ekip postgres gecisini konustu ayse indeks planini hazirliyacak "
            "kubernets pilotu onaylandi takvim gecikmesi riski var devops sahipligi acik kaldi"
        ),
        corrected_text_output=(
            "Ekip PostgreSQL gecisini konustu. Ayse indeks planini hazirlayacak. "
            "Kubernetes pilotu onaylandi. Takvim gecikmesi riski var. "
            "DevOps sahipligi acik kaldi."
        ),
        summary="PostgreSQL gecisi ve Kubernetes pilotu icin kararlar, riskler ve takip maddeleri konusuldu.",
        topics=[{"label": "PostgreSQL gecisi", "start": 0.0, "end": 14.0}],
        action_items=[
            {
                "title": "PostgreSQL indeks planini hazirla",
                "responsible_person": "Ayse",
                "source_segment_id": "s1",
            }
        ],
        decisions=[
            {
                "decision": "Kubernetes pilotu onaylandi",
                "reason_context": "Pilot ortam hazir.",
                "source_segment_id": "s2",
            }
        ],
        people=["Ayse", "Mehmet"],
        segments=[
            {
                "segment_id": "s1",
                "start": 0.0,
                "end": 8.5,
                "speaker": "Ayse",
                "raw_text": "postgres gecisi ve indeks plani",
                "corrected_text": "PostgreSQL gecisi ve indeks plani",
                "confidence": 0.91,
            },
            {
                "segment_id": "s2",
                "start": 8.5,
                "end": 17.0,
                "speaker": "Mehmet",
                "raw_text": "kubernets pilotu onaylandi takvim gecikmesi riski",
                "corrected_text": "Kubernetes pilotu onaylandi. Takvim gecikmesi riski var.",
                "confidence": 0.89,
            },
            {
                "segment_id": "s3",
                "start": 17.0,
                "end": 24.0,
                "speaker": "Ayse",
                "raw_text": "devops sahipligi acik kaldi takip edilecek",
                "corrected_text": "DevOps sahipligi acik kaldi ve takip edilecek.",
                "confidence": 0.87,
            },
        ],
        metadata={
            "language": "tr",
            "transcription_profile": "memory-track-fixture",
            "entities": [
                {"title": "PostgreSQL", "source_segment_id": "s1"},
                {"title": "Kubernetes", "source_segment_id": "s2"},
            ],
            "risks": [
                {"title": "Takvim gecikmesi riski", "source_segment_id": "s2"},
                {"title": "Kubernetes gecisinde gecikme riski", "source_segment_id": "s2"},
            ],
            "open_questions": [{"title": "DevOps sahipligini kim alacak?", "source_segment_id": "s3"}],
            "follow_ups": [{"title": "DevOps ekibiyle sahiplik toplantisi yap", "source_segment_id": "s3"}],
            "extraction_mode": "explicit_fixture",
        },
    )


def test_memory_track_end_to_end_product_loop(tmp_path):
    service = _service(tmp_path, "memory_e2e.sqlite3")

    session = service.ingest_transcription_result(_turkish_meeting_result())
    detail = service.get_session_detail(session.id)
    assert detail is not None
    assert len(detail.transcripts) == 1
    assert detail.transcripts[0].text == _turkish_meeting_result().corrected_text_output

    analysis = next(iter(detail.transcript_analyses.values()))
    assert analysis.raw_text_output == _turkish_meeting_result().raw_text_output
    assert analysis.corrected_text_output == _turkish_meeting_result().corrected_text_output
    assert len(analysis.segments) == 3
    assert analysis.segments[0].segment_id == "s1"
    assert analysis.segments[0].start == 0.0
    assert analysis.segments[0].end == 8.5

    nodes = _nodes_by_type(service, session.id)
    for node_type in ("TASK", "DECISION", "TOPIC", "ENTITY", "RISK", "OPEN_QUESTION", "FOLLOW_UP"):
        assert node_type in nodes
        assert all(_metadata(node)["review_status"] == "pending" for node in nodes[node_type])
        assert all(node["source_reference_id"] for node in nodes[node_type])

    task = nodes["TASK"][0]
    decision = nodes["DECISION"][0]
    segment = nodes["SEGMENT"][0]
    postgres_entity = next(node for node in nodes["ENTITY"] if node["title"] == "PostgreSQL")
    open_question = nodes["OPEN_QUESTION"][0]
    follow_up = nodes["FOLLOW_UP"][0]
    risks = nodes["RISK"]
    risk_target = next(node for node in risks if node["title"] == "Takvim gecikmesi riski")
    risk_source = next(node for node in risks if node["title"] == "Kubernetes gecisinde gecikme riski")

    assert task["source_segment_id"] == "s1"
    assert task["source_text_preview"] == "PostgreSQL gecisi ve indeks plani"
    assert task["source_timestamp_start"] == 0.0
    assert task["source_timestamp_end"] == 8.5

    assert service.update_node(segment["id"], {"review_status": "approved"})
    assert service.update_node(postgres_entity["id"], {"review_status": "approved"})
    assert service.update_node(task["id"], {"review_status": "approved"})
    assert service.update_node(
        decision["id"],
        {"title": "Kubernetes pilotu onaylandi ve izlenecek", "review_status": "edited"},
    )
    assert service.update_node(open_question["id"], {"review_status": "rejected"})
    assert service.update_node(
        follow_up["id"],
        {"review_status": "rejected", "disabled": True, "disabled_reason": "covered by task"},
    )
    assert service.update_node(risk_target["id"], {"review_status": "approved"})
    assert service.merge_nodes(risk_source["id"], risk_target["id"])

    refreshed_nodes = {node["id"]: node for node in service.get_session_graph_data(session.id)["nodes"]}
    assert _metadata(refreshed_nodes[task["id"]])["review_status"] == "approved"
    assert _metadata(refreshed_nodes[decision["id"]])["review_status"] == "edited"
    assert refreshed_nodes[decision["id"]]["title"] == "Kubernetes pilotu onaylandi ve izlenecek"
    assert _metadata(refreshed_nodes[open_question["id"]])["review_status"] == "rejected"
    assert _metadata(refreshed_nodes[follow_up["id"]])["disabled"] is True
    assert _metadata(refreshed_nodes[risk_source["id"]])["review_status"] == "merged"
    assert _metadata(refreshed_nodes[risk_source["id"]])["merged_into_node_id"] == risk_target["id"]
    assert risk_source["id"] in _metadata(refreshed_nodes[risk_target["id"]])["merged_source_node_ids"]

    query_ids = _query_node_ids(service, "gecikme")
    assert risk_target["id"] in query_ids
    assert risk_source["id"] not in query_ids
    assert follow_up["id"] not in query_ids
    assert open_question["id"] not in query_ids
    assert decision["id"] in _query_node_ids(service, "Kubernetes pilotu")

    ask_response = _ask_memory(service, "PostgreSQL task", session.id)
    assert ask_response.answer_type == "evidence_only"
    assert ask_response.evidence_coverage_score == 1.0
    assert ask_response.evidence_chains
    evidence_steps = [step for chain in ask_response.evidence_chains for step in chain.steps]
    task_step = next(step for step in evidence_steps if step.node_id == task["id"])
    assert task_step.source_reference_id
    assert task_step.source_session_id == str(session.id)
    assert task_step.source_segment_id == "s1"
    assert task_step.text_preview == "PostgreSQL gecisi ve indeks plani"
    assert task_step.start_time == 0.0
    assert task_step.end_time == 8.5

    export_path = tmp_path / "memory_e2e_export.json"
    payload = service.export_session(session.id, export_path)
    assert payload["v2_production_graph"]["nodes"]
    assert payload["v2_production_graph"]["edges"]
    assert payload["v2_production_graph"]["source_references"]

    imported_service = _service(tmp_path, "memory_e2e_imported.sqlite3")
    imported = imported_service.import_session(export_path)
    imported_nodes = _nodes_by_type(imported_service, imported.id)
    assert {"TASK", "DECISION", "TOPIC", "ENTITY", "RISK", "OPEN_QUESTION", "FOLLOW_UP"} <= set(imported_nodes)

    imported_task = imported_nodes["TASK"][0]
    imported_risks = {node["id"]: node for node in imported_nodes["RISK"]}
    imported_source = imported_risks[risk_source["id"]]
    imported_target = imported_risks[risk_target["id"]]
    assert _metadata(imported_task)["review_status"] == "approved"
    assert imported_task["source_session_id"] == str(imported.id)
    assert imported_task["source_segment_id"] == "s1"
    assert imported_task["source_text_preview"] == "PostgreSQL gecisi ve indeks plani"
    assert _metadata(imported_source)["review_status"] == "merged"
    assert _metadata(imported_source)["merged_into_node_id"] == risk_target["id"]
    assert risk_source["id"] in _metadata(imported_target)["merged_source_node_ids"]

    imported_query_ids = _query_node_ids(imported_service, "gecikme")
    assert risk_target["id"] in imported_query_ids
    assert risk_source["id"] not in imported_query_ids

    imported_ask_response = _ask_memory(imported_service, "PostgreSQL task", imported.id)
    assert imported_ask_response.evidence_chains
    imported_steps = [step for chain in imported_ask_response.evidence_chains for step in chain.steps]
    imported_task_step = next(step for step in imported_steps if step.node_id == task["id"])
    assert imported_task_step.source_session_id == str(imported.id)
    assert imported_task_step.source_segment_id == "s1"
    assert imported_task_step.text_preview == "PostgreSQL gecisi ve indeks plani"
