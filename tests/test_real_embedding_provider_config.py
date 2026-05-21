import os
import pytest
from collective_mindgraph.infrastructure.ai.local_embedding_provider import SentenceTransformerEmbeddingProvider

def test_real_embedding_provider_requires_local_path():
    # Should warn or fail if path doesn't exist and download is disabled
    provider = SentenceTransformerEmbeddingProvider(model_path="/non/existent/path", allow_download=False)
    assert provider.is_available() is False

def test_remote_downloads_disabled_by_default():
    provider = SentenceTransformerEmbeddingProvider(model_path="all-MiniLM-L6-v2")
    assert provider._allow_download is False

def test_missing_model_handled_gracefully():
    provider = SentenceTransformerEmbeddingProvider(model_path="/tmp/missing_model")
    with pytest.raises(RuntimeError, match="Failed to load local embedding model"):
        provider.embed_text("test")
