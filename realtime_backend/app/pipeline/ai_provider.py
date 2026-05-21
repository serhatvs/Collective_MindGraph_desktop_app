from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class LocalLLMProvider(ABC):
    """
    Abstracts a local-only LLM endpoint (e.g., LM Studio, Ollama, vLLM).
    Strictly forbids cloud connections.
    """
    
    @abstractmethod
    def generate_structured_json(self, prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Forces the local model to return valid JSON matching the provided JSON schema.
        Should handle retries and JSON repair internally.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Checks if the local endpoint is responsive.
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g., 'LMStudio', 'Ollama')."""
        pass


class LocalEmbeddingProvider(ABC):
    """
    Abstracts local embedding generation. No cloud APIs allowed.
    """

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generates a dense vector embedding for a single string."""
        pass
    
    @abstractmethod
    def embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        """Generates embeddings for a batch of strings efficiently."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Checks if the embedding model is loaded in memory/available."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimensionality of the vector space."""
        pass
