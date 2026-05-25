import os
import pytest
from pathlib import Path

from collective_mindgraph_desktop.database import Database
from collective_mindgraph.infrastructure.database.graph_repository import ProductionGraphRepository
from collective_mindgraph.infrastructure.database.vector_repository import VectorRepository
from collective_mindgraph.infrastructure.ai.local_embedding_provider import SentenceTransformerEmbeddingProvider
from collective_mindgraph.core.memory_graph import GraphNode, NodeType
from collective_mindgraph.core.source_reference import SourceReference
from collective_mindgraph.services.hybrid_memory_query_service import HybridMemoryQueryService

def test_real_local_semantic_retrieval(tmp_path):
    model_path = os.getenv("CMG_EMBEDDING_MODEL_PATH")
    if not model_path or not os.path.exists(model_path):
        pytest.skip("Real local embedding model not configured or path does not exist.")

    db_path = tmp_path / "real_semantic.sqlite3"
    db = Database(db_path)
    db.initialize()
    
    # 1. Setup provider and repos
    # We detect dimension automatically from model
    try:
        from sentence_transformers import SentenceTransformer
        tmp_model = SentenceTransformer(model_path, local_files_only=True, device="cpu")
        dimension = tmp_model.get_sentence_embedding_dimension()
        del tmp_model
    except Exception as e:
        pytest.fail(f"Failed to load model to detect dimension: {e}")

    provider = SentenceTransformerEmbeddingProvider(model_path=model_path, device="cpu")

    graph_repo = ProductionGraphRepository(db)
    vector_repo = VectorRepository(db, expected_dim=dimension)
    
    # 2. Create test nodes
    phrases = [
        "FastAPI endpointini test edeceğiz",
        "SQLite kayıtlarında raw transcript ayrı tutulacak",
        "VAD ayarlarını kontrol edeceğiz"
    ]
    
    nodes = []
    for i, p in enumerate(phrases):
        node = GraphNode(
            id=f"node_{i}",
            type=NodeType.TASK,
            properties={"text": p},
            source=SourceReference(session_id="test_session")
        )
        graph_repo.create_node(node)
        vector = provider.embed_text(p)
        vector_repo.store_embedding(node.id, "TASK", p, vector)
        nodes.append(node)

    # 3. Query semantically similar phrases
    query_service = HybridMemoryQueryService(graph_repo, vector_repo, provider)
    
    test_cases = [
        ("API test görevi", "node_0"),
        ("veritabanı kayıt ayrımı", "node_1"),
        ("ses algılama ayarları", "node_2")
    ]
    
    for query_text, expected_node_id in test_cases:
        result = query_service.execute_query(query_text, use_keyword=False, use_vector=True, use_graph=False)
        assert len(result.nodes) > 0
        top_node = result.nodes[0]
        assert top_node.id == expected_node_id, f"Query '{query_text}' should match {expected_node_id}, got {top_node.id}"
        assert "vector" in top_node.properties["matched_by"]

    print("\n✅ Real local semantic retrieval verified end-to-end.")
