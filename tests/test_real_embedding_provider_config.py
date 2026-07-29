import sys
from types import ModuleType

import pytest

from collective_mindgraph.infrastructure.ai.local_embeddings import (
    SentenceTransformerEmbeddingModel,
)


def test_local_embedding_model_requires_existing_path():
    provider = SentenceTransformerEmbeddingModel("/non/existent/path")
    assert not provider.is_available()
    with pytest.raises(RuntimeError, match="Failed to load local embedding model"):
        provider.embed_text("test")


def test_local_embedding_model_reports_missing_optional_dependency(monkeypatch):
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    provider = SentenceTransformerEmbeddingModel("approved/model", allow_download=True)

    with pytest.raises(RuntimeError, match="sentence-transformers"):
        provider.embed_text("test")


def test_local_embedding_model_wraps_provider_load_failures(monkeypatch):
    module = ModuleType("sentence_transformers")

    class _BrokenSentenceTransformer:
        def __init__(self, *_args, **_kwargs):
            raise ValueError("bad model")

    module.SentenceTransformer = _BrokenSentenceTransformer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    provider = SentenceTransformerEmbeddingModel("approved/model", allow_download=True)

    with pytest.raises(RuntimeError, match="Failed to load local embedding model"):
        provider.embed_text("test")


def test_loaded_embedding_model_encodes_single_text_and_chunks():
    class _Array:
        def __init__(self, value):
            self._value = value

        def tolist(self):
            return self._value

    class _Model:
        def encode(self, value, *, convert_to_numpy):
            assert convert_to_numpy
            if isinstance(value, list):
                return _Array([[0.1, 0.2] for _item in value])
            return _Array([0.1, 0.2])

    provider = SentenceTransformerEmbeddingModel("unused", dimension=2)
    provider._model = _Model()

    assert provider.is_available()
    assert provider.dimension == 2
    assert provider.embed_text("hello") == [0.1, 0.2]
    assert provider.embed_chunks(["hello", "world"]) == [[0.1, 0.2], [0.1, 0.2]]
