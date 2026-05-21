import pytest
import sqlite3
from collective_mindgraph.infrastructure.ai.local_embedding_provider import MockLocalEmbeddingProvider
from collective_mindgraph.infrastructure.database.vector_repository import VectorRepository

@pytest.fixture
def repo():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return VectorRepository(conn)

def test_embed_and_retrieve(repo):
    provider = MockLocalEmbeddingProvider(dim=4)
    text1 = "FastAPI endpoint"
    text2 = "Something else entirely"
    
    v1 = provider.embed_text(text1)
    v2 = provider.embed_text(text2)
    
    repo.store_embedding("node_1", text1, v1)
    repo.store_embedding("node_2", text2, v2)
    
    # Query with exactly text1
    q_vec = provider.embed_text(text1)
    results = repo.search_similar(q_vec, top_k=1)
    
    assert len(results) == 1
    assert results[0][0] == "node_1"
    assert results[0][1] == text1
    assert results[0][2] > 0.99  # Cosine similarity for identical vectors is 1.0
