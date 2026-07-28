"""Local embedding index construction over canonical knowledge nodes."""

from __future__ import annotations

from collective_mindgraph.application.pagination import PageRequest
from collective_mindgraph.application.ports import (
    EmbeddingStore,
    KnowledgeGraphStore,
    TextEmbeddingModel,
)
from collective_mindgraph.domain import MeetingId, ReviewDecision


class IndexKnowledge:
    def __init__(
        self,
        knowledge: KnowledgeGraphStore,
        embeddings: EmbeddingStore,
        model: TextEmbeddingModel | None,
    ) -> None:
        self._knowledge = knowledge
        self._embeddings = embeddings
        self._model = model

    @property
    def available(self) -> bool:
        return self._model is not None and self._model.is_available()

    def __call__(self, meeting_id: MeetingId | None = None) -> int:
        if not self.available or self._model is None:
            return 0
        indexed = 0
        cursor: str | None = None
        while True:
            page = self._knowledge.list_nodes(
                PageRequest(cursor=cursor, limit=200),
                meeting_id=meeting_id,
            )
            for node in page.items:
                review = str(node.attributes.get("review", ReviewDecision.ACCEPTED.value))
                if review == ReviewDecision.REJECTED.value:
                    continue
                text = f"{node.title}\n{node.body}".strip()
                if not text:
                    continue
                self._embeddings.put(
                    node_id=node.id,
                    vector=self._model.embed_text(text),
                    text_chunk=text,
                    evidence_id=node.evidence_id,
                )
                indexed += 1
            cursor = page.next_cursor
            if cursor is None:
                break
        return indexed
