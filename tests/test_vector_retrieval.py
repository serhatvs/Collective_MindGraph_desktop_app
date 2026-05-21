import pytest
import sqlite3
from collective_mindgraph.infrastructure.ai.local_embedding_provider import MockLocalEmbeddingProvider
from collective_mindgraph.infrastructure.database.vector_repository import VectorRepository

@pytest.fixture
def repo(tmp_path):
    from collective_mindgraph_desktop.database import Database
    db = Database(tmp_path / "vec.sqlite3")
    return VectorRepository(db, expected_dim=4)

def test_vector_storage_and_cosine_search(repo):
    provider = MockLocalEmbeddingProvider(dim=4)
    
    # Store items
    repo.store_embedding("node_1", "SEGMENT", "technical meeting", provider.embed_text("technical meeting"))
    repo.store_embedding("node_2", "TASK", "fix bug", provider.embed_text("fix bug"))
    
    # Search
    q_vec = provider.embed_text("bug fixing")
    results = repo.search_similar(q_vec, top_k=5, threshold=0.1)
    
    assert len(results) >= 1
    # "fix bug" should have higher score than "technical meeting" for "bug fixing" query
    # in our deterministic mock vector world.
    assert results[0]["node_id"] == "node_2"
    assert "score" in results[0]
    assert results[0]["node_type"] == "TASK"

def test_dimension_validation(repo):
    with pytest.raises(ValueError, match="dimension mismatch"):
        repo.store_embedding("err", "TYPE", "txt", [1.0, 0.0]) # Only 2 dims, expected 4
