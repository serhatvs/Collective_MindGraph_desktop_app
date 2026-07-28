"""Typed memory search and grounded-answer endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from collective_mindgraph.domain import MeetingId

from .errors import ERROR_RESPONSES
from .memory_schemas import (
    MemoryAnswerResponse,
    MemoryEvidenceResponse,
    MemoryReasoningStepResponse,
    MemorySearchItemResponse,
    MemorySearchResponse,
    MemorySentenceValidationResponse,
)

router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


@router.get("/memory/search", response_model=MemorySearchResponse)
async def search_memory(
    request: Request,
    q: str,
    mode: str = "hybrid",
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> MemorySearchResponse:
    context = request.app.state.engine_context
    offset = _memory_offset(cursor)
    search = context.search_memory
    results = search(q, mode=mode, limit=200)
    selected = results[offset : offset + limit]
    warnings = (
        ["Semantic provider unavailable; keyword and graph fallback used."]
        if mode == "hybrid" and not search.semantic_available
        else []
    )
    return MemorySearchResponse(
        query=q,
        mode=mode,
        items=[_memory_search_item(context, item) for item in selected],
        warnings=warnings,
        total=len(results),
        next_cursor=(
            str(offset + len(selected)) if offset + len(selected) < len(results) else None
        ),
    )


@router.get("/memory/ask", response_model=MemoryAnswerResponse)
async def ask_memory(
    request: Request,
    q: str,
    mode: str = "evidence_only",
    meeting_id: int | None = None,
    include_pending: bool = False,
) -> MemoryAnswerResponse:
    context = request.app.state.engine_context
    answer = context.answer_memory(
        q,
        mode=mode,
        meeting_id=MeetingId(meeting_id) if meeting_id is not None else None,
        include_pending=include_pending,
    )
    sources: dict[str, MemoryEvidenceResponse] = {}
    reasoning_steps: list[MemoryReasoningStepResponse] = []
    for chain in answer.chains:
        for step in chain.steps:
            if step.evidence is not None:
                sources[str(step.evidence.id)] = _memory_evidence(
                    context,
                    step.evidence,
                )
            reasoning_steps.append(
                MemoryReasoningStepResponse(
                    node_id=str(step.node.id),
                    kind=step.node.kind.value,
                    title=step.node.title,
                    body=step.node.body,
                    relationship=step.edge.kind.value if step.edge else None,
                    direction=step.direction,
                    evidence_id=(str(step.evidence.id) if step.evidence is not None else None),
                )
            )
    return MemoryAnswerResponse(
        answer=answer.short_answer,
        mode_requested=answer.mode_requested,
        mode_used=answer.mode_used,
        validation_status=answer.validation_status,
        confidence=answer.confidence_level,
        evidence_coverage=answer.evidence_coverage_score,
        sources=list(sources.values()),
        reasoning_steps=reasoning_steps,
        warnings=list(answer.warnings),
        sentence_validations=[
            MemorySentenceValidationResponse(
                sentence=item.sentence,
                supported=item.supported,
                citations=list(item.sources),
                unsupported_terms=list(item.unsupported_terms),
            )
            for item in answer.sentence_validations
        ],
    )


def _memory_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        value = int(cursor)
    except ValueError as exc:
        raise ValueError("Memory cursor is invalid.") from exc
    if value < 0:
        raise ValueError("Memory cursor is invalid.")
    return value


def _memory_search_item(context, item) -> MemorySearchItemResponse:
    return MemorySearchItemResponse(
        node_id=str(item.node.id),
        kind=item.node.kind.value,
        title=item.node.title,
        body=item.node.body,
        score=item.score,
        matched_by=sorted(item.matched_by),
        evidence=(_memory_evidence(context, item.evidence) if item.evidence is not None else None),
    )


def _memory_evidence(context, evidence) -> MemoryEvidenceResponse:
    meeting = context.get_meeting(evidence.meeting_id)
    return MemoryEvidenceResponse(
        id=str(evidence.id),
        meeting_id=int(evidence.meeting_id),
        meeting_title=meeting.title if meeting is not None else str(evidence.meeting_id),
        segment_id=str(evidence.segment_id) if evidence.segment_id else None,
        text_preview=evidence.text_preview,
        start_seconds=evidence.start_seconds,
        end_seconds=evidence.end_seconds,
    )
