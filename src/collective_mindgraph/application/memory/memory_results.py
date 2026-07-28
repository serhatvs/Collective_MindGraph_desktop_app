"""Transport-neutral results returned by memory use cases."""

from __future__ import annotations

from dataclasses import dataclass

from collective_mindgraph.domain import (
    EvidenceReference,
    KnowledgeEdge,
    KnowledgeNode,
)


@dataclass(frozen=True, slots=True)
class MemorySearchResult:
    node: KnowledgeNode
    score: float
    matched_by: frozenset[str]
    evidence: EvidenceReference | None = None
    related_from: KnowledgeEdge | None = None


@dataclass(frozen=True, slots=True)
class MemoryEvidenceStep:
    node: KnowledgeNode
    evidence: EvidenceReference | None
    edge: KnowledgeEdge | None = None
    direction: str = "self"


@dataclass(frozen=True, slots=True)
class MemoryEvidenceChain:
    steps: tuple[MemoryEvidenceStep, ...]
    explanation: str


@dataclass(frozen=True, slots=True)
class AnswerSentenceValidation:
    sentence: str
    supported: bool
    sources: tuple[str, ...] = ()
    unsupported_terms: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MemoryAnswer:
    query: str
    mode_requested: str
    mode_used: str
    validation_status: str
    short_answer: str
    chains: tuple[MemoryEvidenceChain, ...]
    warnings: tuple[str, ...]
    confidence_level: str
    evidence_coverage_score: float
    source_meeting_ids: tuple[str, ...]
    source_segment_ids: tuple[str, ...]
    used_sources: tuple[str, ...]
    rejected_sources: tuple[str, ...] = ()
    sentence_validations: tuple[AnswerSentenceValidation, ...] = ()
    missing_evidence_note: str | None = None
    rejected_terms: tuple[str, ...] = ()
