"""Evidence-first answers with sentence-level local-LLM grounding checks."""

from __future__ import annotations

import re
from dataclasses import dataclass

from collective_mindgraph.application.ports import LocalLanguageModel
from collective_mindgraph.domain import MeetingId

from .memory_results import (
    AnswerSentenceValidation,
    MemoryAnswer,
    MemoryEvidenceChain,
    MemoryEvidenceStep,
    MemorySearchResult,
)
from .search_memory import SearchMemory


@dataclass(frozen=True, slots=True)
class _GroundedGeneration:
    answer: str
    validations: tuple[AnswerSentenceValidation, ...]


class AnswerMemory:
    def __init__(
        self,
        search: SearchMemory,
        language_model: LocalLanguageModel | None = None,
    ) -> None:
        self._search = search
        self._language_model = language_model

    def __call__(
        self,
        query: str,
        *,
        mode: str = "evidence_only",
        meeting_id: MeetingId | None = None,
        include_pending: bool = False,
    ) -> MemoryAnswer:
        if mode not in {"evidence_only", "llm_assisted"}:
            raise ValueError("Answer mode must be evidence_only or llm_assisted.")
        results = self._search(
            query,
            mode="hybrid",
            meeting_id=meeting_id,
            include_pending=include_pending,
            limit=12,
        )
        supported_results = tuple(
            result
            for result in results
            if result.evidence is not None
            and (result.evidence.text_preview or result.node.body or result.node.title)
        )
        if not supported_results:
            return _insufficient_answer(query, mode)

        chains = _evidence_chains(supported_results)
        evidence_answer = "; ".join(
            (result.evidence.text_preview or result.node.body or result.node.title)
            for result in supported_results[:5]
            if result.evidence is not None
        )
        used_mode = "evidence_only"
        validation_status = "accepted"
        warnings: list[str] = []
        answer = evidence_answer
        validations: tuple[AnswerSentenceValidation, ...] = (
            AnswerSentenceValidation(
                sentence=evidence_answer,
                supported=True,
                sources=_source_ids(supported_results),
            ),
        )
        if mode == "llm_assisted":
            generated, rejection = self._try_local_answer(query, supported_results)
            if generated is not None:
                answer = generated.answer
                validations = generated.validations
                used_mode = "llm_assisted"
            else:
                used_mode = "evidence_only_fallback"
                validation_status = "rejected_fallback"
                warnings.append(
                    rejection or "Local language model was unavailable; evidence-only answer used."
                )

        source_meetings = tuple(
            dict.fromkeys(
                str(result.evidence.meeting_id) for result in results if result.evidence is not None
            )
        )
        source_segments = tuple(
            dict.fromkeys(
                str(result.evidence.segment_id)
                for result in results
                if result.evidence is not None and result.evidence.segment_id is not None
            )
        )
        used_sources = _source_ids(supported_results)
        coverage = min(1.0, len(chains) / 3)
        return MemoryAnswer(
            query=query,
            mode_requested=mode,
            mode_used=used_mode,
            validation_status=validation_status,
            short_answer=answer,
            chains=chains,
            warnings=tuple(warnings),
            confidence_level="high" if coverage >= 1 else "medium",
            evidence_coverage_score=coverage,
            source_meeting_ids=source_meetings,
            source_segment_ids=source_segments,
            used_sources=used_sources,
            sentence_validations=validations,
        )

    def _try_local_answer(
        self,
        query: str,
        results: tuple[MemorySearchResult, ...],
    ) -> tuple[_GroundedGeneration | None, str | None]:
        if self._language_model is None or not self._language_model.is_available():
            return None, None
        sources = {
            str(result.evidence.id): (
                result.evidence.text_preview or result.node.body or result.node.title
            )
            for result in results[:5]
            if result.evidence is not None
        }
        if not sources:
            return None, "No evidence identifiers were available for a grounded answer."
        try:
            payload = self._language_model.generate_structured_json(
                (
                    "Answer only from the supplied evidence. Every sentence must cite "
                    "one or more evidence IDs. "
                    f"Question: {query}\nEvidence: {sources}"
                ),
                {
                    "type": "object",
                    "properties": {
                        "sentences": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string"},
                                    "citations": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": ["text", "citations"],
                            },
                        }
                    },
                    "required": ["sentences"],
                },
            )
        except (RuntimeError, ValueError):
            return None, "Local language-model output was malformed."
        sentences = payload.get("sentences")
        if not isinstance(sentences, list) or not sentences:
            return None, "Local language-model output had no cited sentences."

        validations: list[AnswerSentenceValidation] = []
        for item in sentences:
            if not isinstance(item, dict):
                return None, "Local language-model sentence data was malformed."
            text = str(item.get("text") or "").strip()
            citations = item.get("citations")
            if not text or not isinstance(citations, list) or not citations:
                return None, "Every generated sentence must have evidence citations."
            citation_ids = tuple(dict.fromkeys(str(value) for value in citations))
            unknown = tuple(value for value in citation_ids if value not in sources)
            if unknown:
                return None, f"Generated answer cited unknown evidence: {', '.join(unknown)}."
            unsupported = _unsupported_terms(
                text,
                " ".join(sources[value] for value in citation_ids),
            )
            if unsupported:
                return None, "Generated answer contained a claim unsupported by its citations."
            validations.append(
                AnswerSentenceValidation(
                    sentence=text,
                    supported=True,
                    sources=citation_ids,
                )
            )
        return (
            _GroundedGeneration(
                answer=" ".join(item.sentence for item in validations),
                validations=tuple(validations),
            ),
            None,
        )


def _evidence_chains(
    results: tuple[MemorySearchResult, ...],
) -> tuple[MemoryEvidenceChain, ...]:
    return tuple(
        MemoryEvidenceChain(
            steps=(
                MemoryEvidenceStep(
                    node=result.node,
                    evidence=result.evidence,
                    edge=result.related_from,
                    direction="related" if result.related_from else "self",
                ),
            ),
            explanation=f"{result.node.kind.value}: {result.node.title}",
        )
        for result in results[:5]
    )


def _source_ids(results: tuple[MemorySearchResult, ...]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(str(result.evidence.id) for result in results if result.evidence is not None)
    )


def _unsupported_terms(sentence: str, evidence: str) -> tuple[str, ...]:
    sentence_terms = _claim_terms(sentence)
    if not sentence_terms:
        return ()
    evidence_terms = _claim_terms(evidence)
    unsupported = sentence_terms - evidence_terms
    return tuple(sorted(unsupported))


def _claim_terms(value: str) -> set[str]:
    ignored = {
        "and",
        "are",
        "as",
        "bir",
        "bu",
        "da",
        "de",
        "did",
        "edildi",
        "olarak",
        "for",
        "için",
        "ile",
        "is",
        "oldu",
        "the",
        "was",
        "were",
        "ve",
    }
    return {
        token
        for token in re.findall(r"[^\W_]+", value.casefold(), flags=re.UNICODE)
        if len(token) >= 3 and token not in ignored
    }


def _insufficient_answer(query: str, mode: str) -> MemoryAnswer:
    note = "No supported evidence matched the query."
    return MemoryAnswer(
        query=query,
        mode_requested=mode,
        mode_used="evidence_only",
        validation_status="accepted",
        short_answer="Bu soruyu yanıtlamak için yeterli kanıt bulunamadı.",
        chains=(),
        warnings=(note,),
        confidence_level="insufficient",
        evidence_coverage_score=0.0,
        source_meeting_ids=(),
        source_segment_ids=(),
        used_sources=(),
        missing_evidence_note=note,
    )
