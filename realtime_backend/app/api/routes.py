"""HTTP endpoints for file-based transcription and transcript retrieval."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ..models import (
    FileTranscriptionResponse, 
    HealthResponse, 
    QualityReport, 
    QueryResponse, 
    QueryResultItem,
    ReasoningResponse,
    EvidenceChain,
    EvidenceStep,
    SummaryResponse, 
    TranscriptResponse
)
from ..pipeline.transcript_formatter import build_file_transcription_response, build_transcript_response
from ..pipeline.transcription_glossary import parse_term_input
from ..utils.ids import validate_conversation_id

router = APIRouter()


@router.get("/jobs")
async def list_jobs(request: Request, active_only: bool = False):
    return request.app.state.job_manager.list_jobs(active_only=active_only)

@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    runtime = request.app.state.transcription_service.runtime_status()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        vad_provider=settings.vad_provider,
        asr_provider=settings.asr_provider,
        asr_provider_resolved=runtime.asr_provider_resolved,
        asr_fallback_provider=runtime.asr_fallback_provider,
        asr_status=runtime.asr_status,
        asr_mock_fallback_used=runtime.asr_mock_fallback_used,
        asr_model_name=getattr(settings, "asr_model_name", None),
        asr_quality_profile=getattr(settings, "transcription_quality_mode", None),
        asr_runtime_profile=getattr(settings, "asr_runtime_profile", None),
        asr_device=getattr(settings, "asr_device", None),
        asr_compute_type=getattr(settings, "asr_compute_type", None),
        asr_language=getattr(settings, "default_language", None),
        gpu_enabled=getattr(settings, "gpu_enabled", None),
        gpu_required=getattr(settings, "gpu_required", None),
        cuda_available_through_torch=runtime.cuda_available_through_torch,
        gpu_requested=runtime.gpu_requested,
        gpu_actually_used_by_asr=runtime.gpu_loaded,
        faster_whisper_cuda_load_status=runtime.faster_whisper_cuda_load_status,
        gpu_fallback_happened=runtime.gpu_fallback_happened,
        gpu_fallback_reason=runtime.gpu_fallback_reason,
        embedding_device=getattr(settings, "embedding_device", "cpu"),
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
    service = request.app.state.transcription_service
    settings = request.app.state.settings
    validated_conversation_id = _validate_optional_conversation_id(conversation_id)
    suffix = Path(upload.filename or "audio.bin").suffix or ".bin"
    source_path = settings.temp_dir / f"upload_{request.app.state.id_factory()}{suffix}"
    source_path.write_bytes(await upload.read())
    try:
        service_kwargs = {
            "conversation_id": validated_conversation_id,
            "language": language,
            "quality_mode": quality_mode,
            "source": "upload",
        }
        parsed_session_glossary = parse_term_input(session_glossary)
        parsed_hotwords = parse_term_input(hotwords)
        if parsed_session_glossary:
            service_kwargs["session_glossary_terms"] = parsed_session_glossary
        if parsed_hotwords:
            service_kwargs["user_hotwords"] = parsed_hotwords
        transcript = await service.transcribe_file(source_path, **service_kwargs)
    finally:
        source_path.unlink(missing_ok=True)
    return build_file_transcription_response(transcript)


@router.get("/transcript/{conversation_id}", response_model=TranscriptResponse)
async def get_transcript(request: Request, conversation_id: str) -> TranscriptResponse:
    transcript = request.app.state.transcription_service.get_transcript(
        _validate_required_conversation_id(conversation_id)
    )
    if transcript is None:
        raise HTTPException(status_code=404, detail="Transcript not found.")
    return build_transcript_response(transcript)


@router.get("/summary/{conversation_id}", response_model=SummaryResponse)
async def get_summary(request: Request, conversation_id: str) -> SummaryResponse:
    transcript = request.app.state.transcription_service.get_transcript(
        _validate_required_conversation_id(conversation_id)
    )
    if transcript is None:
        raise HTTPException(status_code=404, detail="Transcript not found.")
    return SummaryResponse(
        conversation_id=transcript.conversation_id,
        summary=transcript.summary,
        topics=transcript.topics,
        action_items=transcript.action_items,
        decisions=transcript.decisions,
    )


@router.get("/quality/{conversation_id}", response_model=QualityReport)
async def get_quality(request: Request, conversation_id: str) -> QualityReport:
    transcript = request.app.state.transcription_service.get_transcript(
        _validate_required_conversation_id(conversation_id)
    )
    if transcript is None:
        raise HTTPException(status_code=404, detail="Transcript not found.")
    return request.app.state.quality_service.build_report(transcript)


def _validate_optional_conversation_id(conversation_id: str | None) -> str | None:
    if not conversation_id:
        return None
    return _validate_required_conversation_id(conversation_id)


def _validate_required_conversation_id(conversation_id: str) -> str:
    try:
        return validate_conversation_id(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/reason", response_model=ReasoningResponse)
async def reason_memory(request: Request, q: str, max_depth: int = 3) -> ReasoningResponse:
    reasoning_service = request.app.state.reasoning_service
    
    # 1. Parse intent or use heuristic reasoning
    result = reasoning_service.get_intent_based_reasoning(q)
    
    # 2. Map ReasoningResult to ReasoningResponse
    chains = []
    for chain in result.chains:
        steps = []
        for step in chain.steps:
            steps.append(
                EvidenceStep(
                    node_id=step.node.id,
                    node_type=step.node.type.value,
                    text=step.node.properties.get("title") or step.node.properties.get("text") or "",
                    edge_type=step.edge.type.value if step.edge else None,
                    direction=step.direction,
                    source_reference_id=getattr(step.node.source, "id", None) if step.node.source else None,
                    source_session_id=step.node.source.session_id if step.node.source else None,
                    source_segment_id=step.node.source.segment_id if step.node.source else None,
                    text_preview=getattr(step.node.source, "text_preview", None) if step.node.source else None,
                    start_time=step.node.source.timestamp_start if step.node.source else None,
                    end_time=step.node.source.timestamp_end if step.node.source else None,
                    edge_path=[
                        item.edge.type.value
                        for item in chain.steps
                        if item.edge
                    ],
                )
            )
        chains.append(EvidenceChain(steps=steps, explanation=chain.explanation))
        
    return ReasoningResponse(query=q, chains=chains, warnings=result.warnings)

from ..api.memory_models import MemoryAskResponse

# ... (rest of imports)

@router.get("/memory/ask", response_model=MemoryAskResponse)
async def ask_memory(
    request: Request, 
    q: str, 
    mode: str = "evidence_only", 
    session_id: str | None = None,
    include_pending: bool = False
) -> MemoryAskResponse:
    evidence_service = request.app.state.evidence_service
    llm_assisted_service = request.app.state.llm_assisted_service
    
    # 1. Always get evidence-only response first
    response = evidence_service.ask(
        query=q, 
        session_id=session_id, 
        include_pending=include_pending,
        mode=mode
    )
    
    # 2. If llm_assisted and evidence exists, enhance it
    if mode == "llm_assisted" and response.evidence_chains:
        return await llm_assisted_service.generate_answer(q, response)
        
    return response

@router.get("/query", response_model=QueryResponse)
async def query_memory(request: Request, q: str, mode: str = "hybrid") -> QueryResponse:
    query_service = request.app.state.query_service
    
    use_keyword = mode in {"keyword", "hybrid"}
    use_vector = mode in {"semantic", "hybrid"}
    use_graph = mode in {"hybrid"}

    hybrid_result = query_service.execute_query(
        q, 
        use_keyword=use_keyword, 
        use_vector=use_vector, 
        use_graph=use_graph
    )
    
    results = []
    for node in hybrid_result.nodes:
        source = node.source
        source_preview = getattr(source, "text_preview", None) if source else None
        node_text = node.properties.get("title") or node.properties.get("text") or ""
        # Map GraphNode to QueryResultItem
        results.append(
            QueryResultItem(
                result_type=node.type.value.lower(),
                text=node_text,
                source_session_id=source.session_id if source else "unknown",
                source_segment_id=source.segment_id if source else None,
                source_reference_id=getattr(source, "id", None) if source else None,
                matched_by=node.properties.get("matched_by"),
                score=node.properties.get("score", 1.0),
                score_breakdown=node.properties.get("score_breakdown", {}),
                edge_path=node.properties.get("edge_path"),
                node_id=node.id,
                preview=(source_preview or node.properties.get("text") or node_text or None),
                text_preview=source_preview,
                start_time=source.timestamp_start if source else None,
                end_time=source.timestamp_end if source else None,
                graph_distance=node.properties.get("graph_distance"),
                related_node_id=node.properties.get("related_node_id"),
                edge_type=node.properties.get("edge_type"),
            )
        )

    # ---------------------------------------------------------
    # Phase 4 Skeleton: Future AI Answer Generation
    # ---------------------------------------------------------
    # if mode == "hybrid" and results:
    #     # check if real LLM is available via readiness check logic
    #     # if active: results.append(generated_answer_item)
    # ---------------------------------------------------------

    return QueryResponse(query=q, results=results, warnings=hybrid_result.warnings)
