"""Local Embedding Provider implementation."""

import os
import logging
from typing import List, Optional

from .ai_provider import LocalEmbeddingProvider

logger = logging.getLogger(__name__)

class SentenceTransformerEmbeddingProvider(LocalEmbeddingProvider):
    """
    Real local embedding provider using sentence-transformers.
    Requires local model path and 'sentence-transformers' library.
    """

    def __init__(self, model_path: str, dimension: int = 384, allow_download: bool = False, device: str = "cpu"):
        self._model_path = model_path
        self._dimension = dimension
        self._allow_download = allow_download
        self._device = device
        self._model = None
        
        if not allow_download and not os.path.exists(model_path):
            logger.warning(f"Embedding model path does not exist and download is disabled: {model_path}")

    def _load_model(self):
        if self._model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            # If allow_download is False, it will fail if path doesn't exist
            self._model = SentenceTransformer(
                self._model_path, 
                local_files_only=not self._allow_download,
                device=self._device
            )
        except ImportError:
            raise RuntimeError("Library 'sentence-transformers' is not installed. Run 'pip install sentence-transformers'.")
        except Exception as e:
            raise RuntimeError(f"Failed to load local embedding model at {self._model_path}: {str(e)}")

    @property
    def dimension(self) -> int:
        return self._dimension

    def is_available(self) -> bool:
        if self._model is not None:
            return True
        return os.path.exists(self._model_path)

    def embed_text(self, text: str) -> List[float]:
        self._load_model()
        vector = self._model.encode(text, convert_to_numpy=True).tolist()
        return vector

    def embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        self._load_model()
        vectors = self._model.encode(chunks, convert_to_numpy=True).tolist()
        return vectors


class MockLocalEmbeddingProvider(LocalEmbeddingProvider):
    """
    Deterministic mock provider for testing vector storage and hybrid retrieval
    without requiring a real local LLM to be downloaded yet.
    """

    def __init__(self, dim: int = 384):
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    def is_available(self) -> bool:
        return True

    def _mock_vector(self, text: str) -> List[float]:
        """Generate a deterministic pseudo-random vector based on text length and content."""
        v = []
        base = sum(ord(c) for c in text)
        for i in range(self._dim):
            v.append(((base + i) % 100) / 100.0)
        
        # normalize
        mag = sum(x*x for x in v) ** 0.5
        if mag > 0:
            v = [x/mag for x in v]
        return v

    def embed_text(self, text: str) -> List[float]:
        return self._mock_vector(text)

    def embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        return [self._mock_vector(c) for c in chunks]
