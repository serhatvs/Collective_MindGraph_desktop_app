from fastapi.testclient import TestClient

from realtime_backend.app.api.routes import router
from realtime_backend.app.database_proxy import DatabaseProxy
from realtime_backend.app.models import QueryResponse
from realtime_backend.app.services.graph_repository import ProductionGraphRepository
from realtime_backend.app.services.hybrid_memory_query_service import HybridMemoryQueryService
from realtime_backend.app.services.hybrid_query import HybridQueryResult
from realtime_backend.app.services.memory_graph import EdgeType, GraphEdge, GraphNode, NodeType
from realtime_backend.app.services.source_reference import SourceReference


def _backend_graph_repo(tmp_path) -> ProductionGraphRepository:
    db = DatabaseProxy(tmp_path / "backend_hybrid.sqlite3")
    db.initialize()
    return ProductionGraphRepository(db)


def _seed_segment_and_task(repo: ProductionGraphRepository) -> tuple[str, str]:
    segment = GraphNode(
        id="seg_1",
        type=NodeType.SEGMENT,
        properties={"text": "FastAPI planning discussion"},
        source=SourceReference(
            session_id="session_1",
            segment_id="s1",
            timestamp_start=10.0,
            timestamp_end=14.5,
            text_preview="FastAPI planning discussion",
        ),
    )
    task = GraphNode(
        id="task_1",
        type=NodeType.TASK,
        properties={"title": "Write the launch checklist"},
        source=SourceReference(
            session_id="session_1",
            segment_id="s1",
            timestamp_start=10.0,
            timestamp_end=14.5,
            text_preview="FastAPI planning discussion",
        ),
    )
    repo.create_node(segment)
    repo.create_node(task)
    repo.create_edge(
        GraphEdge(
            id="edge_1",
            source_node_id="seg_1",
            target_node_id="task_1",
            type=EdgeType.SEGMENT_CREATES_TASK,
        )
    )
    return segment.id, task.id


def test_backend_hybrid_query_keyword_expands_to_graph_neighbor(tmp_path):
    repo = _backend_graph_repo(tmp_path)
    _seed_segment_and_task(repo)
    service = HybridMemoryQueryService(repo, vector_repo=None, embedding_provider=None)

    result = service.execute_query("FastAPI", use_keyword=True, use_vector=False, use_graph=True)

    by_id = {node.id: node for node in result.nodes}
    assert "seg_1" in by_id
    assert "task_1" in by_id
    assert "keyword" in by_id["seg_1"].properties["matched_by"]
    assert "graph" in by_id["task_1"].properties["matched_by"]
    assert by_id["task_1"].properties["graph_distance"] == 1
    assert by_id["task_1"].properties["related_node_id"] == "seg_1"
    assert by_id["task_1"].properties["edge_type"] == "SEGMENT_CREATES_TASK"


def test_backend_hybrid_query_preserves_source_metadata_on_expanded_result(tmp_path):
    repo = _backend_graph_repo(tmp_path)
    _seed_segment_and_task(repo)
    service = HybridMemoryQueryService(repo, vector_repo=None, embedding_provider=None)

    result = service.execute_query("FastAPI", use_keyword=True, use_vector=False, use_graph=True)
    expanded = next(node for node in result.nodes if node.id == "task_1")

    assert expanded.source is not None
    assert expanded.source.id
    assert expanded.source.session_id == "session_1"
    assert expanded.source.segment_id == "s1"
    assert expanded.source.text_preview == "FastAPI planning discussion"
    assert expanded.source.timestamp_start == 10.0
    assert expanded.source.timestamp_end == 14.5


def test_query_response_model_keeps_graph_expansion_metadata():
    response = QueryResponse(
        query="FastAPI",
        results=[
            {
                "result_type": "task",
                "text": "Write the launch checklist",
                "source_session_id": "session_1",
                "source_segment_id": "s1",
                "source_reference_id": "source_ref_1",
                "score": 0.4,
                "matched_by": "graph",
                "edge_path": "SEGMENT --(SEGMENT_CREATES_TASK)--> TASK",
                "node_id": "task_1",
                "text_preview": "FastAPI planning discussion",
                "start_time": 10.0,
                "end_time": 14.5,
                "graph_distance": 1,
                "related_node_id": "seg_1",
                "edge_type": "SEGMENT_CREATES_TASK",
            }
        ],
    )

    payload = response.model_dump()
    item = payload["results"][0]
    assert item["matched_by"] == "graph"
    assert item["source_reference_id"] == "source_ref_1"
    assert item["graph_distance"] == 1
    assert item["edge_type"] == "SEGMENT_CREATES_TASK"


def test_query_endpoint_includes_graph_expansion_metadata():
    from fastapi import FastAPI

    source = SourceReference(
        session_id="session_1",
        segment_id="s1",
        timestamp_start=10.0,
        timestamp_end=14.5,
        text_preview="FastAPI planning discussion",
        id="source_ref_1",
    )
    node = GraphNode(
        id="task_1",
        type=NodeType.TASK,
        properties={
            "title": "Write the launch checklist",
            "matched_by": "graph",
            "score": 0.4,
            "score_breakdown": {"keyword": 0.0, "vector": 0.0, "graph": 0.4},
            "edge_path": "SEGMENT --(SEGMENT_CREATES_TASK)--> TASK",
            "graph_distance": 1,
            "related_node_id": "seg_1",
            "edge_type": "SEGMENT_CREATES_TASK",
        },
        source=source,
    )

    class FakeQueryService:
        def execute_query(self, *args, **kwargs):
            return HybridQueryResult(nodes=[node])

    app = FastAPI()
    app.include_router(router)
    app.state.query_service = FakeQueryService()
    client = TestClient(app)

    payload = client.get("/query?q=FastAPI&mode=hybrid").json()
    item = payload["results"][0]
    assert item["matched_by"] == "graph"
    assert item["source_reference_id"] == "source_ref_1"
    assert item["text_preview"] == "FastAPI planning discussion"
    assert item["start_time"] == 10.0
    assert item["end_time"] == 14.5
    assert item["graph_distance"] == 1
    assert item["related_node_id"] == "seg_1"
    assert item["edge_type"] == "SEGMENT_CREATES_TASK"
