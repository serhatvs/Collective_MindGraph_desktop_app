import pytest

from collective_mindgraph.infrastructure.ai.local_embeddings import (
    SentenceTransformerEmbeddingModel,
)


def test_local_embedding_model_requires_existing_path():
    provider = SentenceTransformerEmbeddingModel("/non/existent/path")
    assert not provider.is_available()
    with pytest.raises(RuntimeError, match="Failed to load local embedding model"):
        provider.embed_text("test")
