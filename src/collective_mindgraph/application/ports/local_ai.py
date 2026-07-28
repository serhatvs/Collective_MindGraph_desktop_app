"""Local-only AI provider boundaries."""

from __future__ import annotations

from typing import Protocol


class LocalLanguageModel(Protocol):
    @property
    def provider_name(self) -> str: ...

    def is_available(self) -> bool: ...

    def generate_structured_json(
        self,
        prompt: str,
        schema: dict[str, object],
    ) -> dict[str, object]: ...


class TextEmbeddingModel(Protocol):
    @property
    def dimension(self) -> int: ...

    def is_available(self) -> bool: ...

    def embed_text(self, text: str) -> list[float]: ...

    def embed_chunks(self, chunks: list[str]) -> list[list[float]]: ...
