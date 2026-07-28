"""Compatibility HTTP routes backed by canonical engine use cases."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from collective_mindgraph.application import PageRequest
from collective_mindgraph.application.memory import MemoryAnswer
from collective_mindgraph.application.transcription.contracts import (
    EvidenceChain,
    EvidenceStep,
    FileTranscriptionResponse,
    HealthResponse,
    QualityReport,
    QueryResponse,
    QueryResultItem,
    ReasoningResponse,
    SummaryResponse,
    TranscriptResponse,
)
from collective_mindgraph.application.transcription.conversation_ids import (
    new_segment_id,
    validate_conversation_id,
)
from collective_mindgraph.application.transcription.transcript_formatter import (
    build_file_transcription_response,
    build_transcript_response,
)
from collective_mindgraph.application.transcription.transcription_glossary import (
    parse_term_input,
)

from .legacy_memory_contracts import MemoryAskResponse, SentenceValidation

router = APIRouter()


def _context(request: Request):
    return request.app.state.engine_context


@router.get("/jobs")
async def list_jobs(request: Request, active_only: bool = False):
    page = _context(request).jobs.list(PageRequest(limit=200), active_only=active_only)
    return [
        {
            "id": str(job.id),
            "type": job.kind,
            "status": job.status.value,
            "progress": job.progress,
            "message": job.message,
            "error": job.error,
            "metadata_json": job.attributes,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }
        for job in page.items
    ]


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = _context(request).settings
    runtime = _context(request).transcribe_recording.runtime_status()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        vad_provider=settings.vad_provider,
        asr_provider=settings.asr_provider,
        asr_provider_resolved=runtime.asr_provider_resolved,
        asr_fallback_provider=runtime.asr_fallback_provider,
        asr_status=runtime.asr_status,
        asr_mock_fallback_used=runtime.asr_mock_fallback_used,
        asr_model_name=settings.asr_model_name,
        asr_quality_profile=settings.transcription_quality_mode,
        asr_runtime_profile=settings.asr_runtime_profile,
        asr_device=settings.asr_device,
        asr_compute_type=settings.asr_compute_type,
        asr_language=settings.default_language,
        gpu_enabled=settings.gpu_enabled,
        gpu_required=settings.gpu_required,
        cuda_available_through_torch=runtime.cuda_available_through_torch,
        gpu_requested=runtime.gpu_requested,
        gpu_actually_used_by_asr=runtime.gpu_loaded,
        faster_whisper_cuda_load_status=runtime.faster_whisper_cuda_load_status,
        gpu_fallback_happened=runtime.gpu_fallback_happened,
        gpu_fallback_reason=runtime.gpu_fallback_reason,
        embedding_device=settings.embedding_device,
        local_llm_enabled=runtime.local_llm_enabled,
        diarizer_provider=settings.diarizer_provider,
        llm_provider=settings.llm_provider,
        llm_provider_resolved=runtime.llm_provider_resolved,
        llm_fallback_provider=runtime.llm_fallback_provider,
    )


@router.post("/transcribe/file", response_model=FileTranscriptionResponse)
async def transcribe_file(
    request: Request,
    upload: UploadFile = File(...),
    conversation_id: str | None = Form(default=None),
    language: str | None = Form(default=None),
    quality_mode: str | None = Form(default=None),
    session_glossary: str | None = Form(default=None),
    hotwords: str | None = Form(default=None),
) -> FileTranscriptionResponse:
    context = _context(request)
    validated_id = _validate_optional_conversation_id(conversation_id)
    suffix = Path(upload.filename or "audio.bin").suffix or ".bin"
    source_path = context.settings.temp_dir / f"upload_{new_segment_id()}{suffix}"
    source_path.write_bytes(await upload.read())
    source_uri = f"upload://{Path(upload.filename or 'audio.bin').name}"
    try:
        result = await context.transcribe_recording.transcribe_file(
            source_path,
            conversation_id=validated_id,
            language=language,
            quality_mode=quality_mode,
            source="upload",
            session_glossary_terms=parse_term_input(session_glossary) or None,
            user_hotwords=parse_term_input(hotwords) or None,
            recording_source_uri=source_uri,
        )
    finally:
        source_path.unlink(missing_ok=True)
    return build_file_transcription_response(result)


@router.get("/transcript/{conversation_id}", response_model=TranscriptResponse)
async def get_transcript(request: Request, conversation_id: str) -> TranscriptResponse:
    result = _find_transcript(request, conversation_id)
    return build_transcript_response(result)


@router.get("/summary/{conversation_id}", response_model=SummaryResponse)
async def get_summary(request: Request, conversation_id: str) -> SummaryResponse:
    result = _find_transcript(request, conversation_id)
    return SummaryResponse(
        conversation_id=result.conversation_id,
        summary=result.summary,
        topics=result.topics,
        action_items=result.action_items,
        decisions=result.decisions,
    )


@router.get("/quality/{conversation_id}", response_model=QualityReport)
async def get_quality(request: Request, conversation_id: str) -> QualityReport:
    return _context(request).build_quality_report.build_report(
        _find_transcript(request, conversation_id)
    )


@router.get("/query", response_model=QueryResponse)
async def query_memory(request: Request, q: str, mode: str = "hybrid") -> QueryResponse:
    results = _context(request).search_memory(q, mode=mode)
    return QueryResponse(
        query=q,
        results=[
            QueryResultItem(
                result_type=item.node.kind.value,
                text=item.node.title or item.node.body,
                source_session_id=(
                    str(item.evidence.meeting_id)
                    if item.evidence
                    else str(item.node.meeting_id or "unknown")
                ),
                source_segment_id=(
                    str(item.evidence.segment_id)
                    if item.evidence and item.evidence.segment_id
                    else None
                ),
                source_reference_id=(str(item.evidence.id) if item.evidence else None),
                matched_by=",".join(sorted(item.matched_by)),
                score=item.score,
                score_breakdown={key: item.score for key in item.matched_by},
                edge_path=(item.related_from.kind.value if item.related_from else None),
                node_id=str(item.node.id),
                preview=item.evidence.text_preview if item.evidence else item.node.body,
                text_preview=item.evidence.text_preview if item.evidence else None,
                start_time=item.evidence.start_seconds if item.evidence else None,
                end_time=item.evidence.end_seconds if item.evidence else None,
                graph_distance=1 if item.related_from else 0,
                related_node_id=(str(item.related_from.source_id) if item.related_from else None),
                edge_type=item.related_from.kind.value if item.related_from else None,
            )
            for item in results
        ],
    )


@router.get("/reason", response_model=ReasoningResponse)
async def reason_memory(request: Request, q: str, max_depth: int = 3) -> ReasoningResponse:
    del max_depth
    answer = _context(request).answer_memory(q, mode="evidence_only", include_pending=True)
    return ReasoningResponse(
        query=q,
        chains=[_compatibility_chain(chain) for chain in answer.chains],
        warnings=list(answer.warnings),
    )


@router.get("/memory/ask", response_model=MemoryAskResponse)
async def ask_memory(
    request: Request,
    q: str,
    mode: str = "evidence_only",
    session_id: str | None = None,
    include_pending: bool = False,
) -> MemoryAskResponse:
    meeting_id = None
    if session_id:
        try:
            from collective_mindgraph.domain import MeetingId

            meeting_id = MeetingId(int(session_id))
        except ValueError:
            meeting_id = None
    answer = _context(request).answer_memory(
        q,
        mode=mode,
        meeting_id=meeting_id,
        include_pending=include_pending,
    )
    return _compatibility_answer(answer)


def _find_transcript(request: Request, conversation_id: str):
    result = _context(request).transcribe_recording.get_transcript(
        _validate_required_conversation_id(conversation_id)
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Transcript not found.")
    return result


def _validate_optional_conversation_id(conversation_id: str | None) -> str | None:
    return _validate_required_conversation_id(conversation_id) if conversation_id else None


def _validate_required_conversation_id(conversation_id: str) -> str:
    try:
        return validate_conversation_id(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _compatibility_chain(chain) -> EvidenceChain:
    edge_path = [step.edge.kind.value for step in chain.steps if step.edge]
    return EvidenceChain(
        explanation=chain.explanation,
        steps=[
            EvidenceStep(
                node_id=str(step.node.id),
                node_type=step.node.kind.value,
                text=step.node.title or step.node.body,
                edge_type=step.edge.kind.value if step.edge else None,
                direction=step.direction,
                source_reference_id=str(step.evidence.id) if step.evidence else None,
                source_session_id=(str(step.evidence.meeting_id) if step.evidence else None),
                source_segment_id=(
                    str(step.evidence.segment_id)
                    if step.evidence and step.evidence.segment_id
                    else None
                ),
                text_preview=step.evidence.text_preview if step.evidence else None,
                start_time=step.evidence.start_seconds if step.evidence else None,
                end_time=step.evidence.end_seconds if step.evidence else None,
                edge_path=edge_path,
            )
            for step in chain.steps
        ],
    )


def _compatibility_answer(answer: MemoryAnswer) -> MemoryAskResponse:
    return MemoryAskResponse(
        query=answer.query,
        mode=answer.mode_requested,
        mode_requested=answer.mode_requested,
        mode_used=answer.mode_used,
        answer_type=answer.mode_used,
        answer_validation_status=answer.validation_status,
        short_answer=answer.short_answer,
        evidence_chains=[_compatibility_chain(chain) for chain in answer.chains],
        warnings=list(answer.warnings),
        confidence_level=answer.confidence_level,
        evidence_coverage_score=answer.evidence_coverage_score,
        source_session_ids=list(answer.source_meeting_ids),
        source_segment_ids=list(answer.source_segment_ids),
        used_sources=list(answer.used_sources),
        rejected_sources=list(answer.rejected_sources),
        sentence_validations=[
            SentenceValidation(
                sentence=item.sentence,
                supported=item.supported,
                sources=list(item.sources),
                unsupported_terms=list(item.unsupported_terms),
            )
            for item in answer.sentence_validations
        ],
        missing_evidence_note=answer.missing_evidence_note,
        rejected_terms=list(answer.rejected_terms),
    )
