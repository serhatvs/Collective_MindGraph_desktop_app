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
from ..pipeline.transcript_formatter import build_transcript_response

router = APIRouter()


@router.get("/jobs")
async def list_jobs(request: Request, active_only: bool = False):
    return request.app.state.job_manager.list_jobs(active_only=active_only)

@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    asr_provider = request.app.state.transcription_service._pipeline._asr
    llm_provider = request.app.state.transcription_service._pipeline._llm_postprocessor._provider
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        vad_provider=settings.vad_provider,
        asr_provider=settings.asr_provider,
        asr_provider_resolved=getattr(asr_provider, "provider_name", None),
        asr_fallback_provider=getattr(asr_provider, "fallback_provider_name", None),
        asr_status=getattr(asr_provider, "asr_status", None),
        asr_mock_fallback_used=bool(getattr(asr_provider, "mock_fallback_used", False)),
        asr_model_name=getattr(settings, "asr_model_name", None),
        asr_quality_profile=getattr(settings, "transcription_quality_mode", None),
        diarizer_provider=settings.diarizer_provider,
        llm_provider=settings.llm_provider,
        llm_provider_resolved=getattr(llm_provider, "provider_name", None),
        llm_fallback_provider=getattr(llm_provider, "fallback_provider_name", None),
    )


@router.post("/transcribe/file", response_model=FileTranscriptionResponse)
async def transcribe_file(
    request: Request,
    upload: UploadFile = File(...),
    conversation_id: str | None = Form(default=None),
    language: str | None = Form(default=None),
    quality_mode: str | None = Form(default=None),
) -> FileTranscriptionResponse:
    service = request.app.state.transcription_service
    settings = request.app.state.settings
    suffix = Path(upload.filename or "audio.bin").suffix or ".bin"
    source_path = settings.temp_dir / f"upload_{request.app.state.id_factory()}{suffix}"
    source_path.write_bytes(await upload.read())
    try:
        transcript = await service.transcribe_file(
            source_path,
            conversation_id=conversation_id,
            language=language,
            quality_mode=quality_mode,
            source="upload",
        )
    finally:
        source_path.unlink(missing_ok=True)
    response = build_transcript_response(transcript)
    return FileTranscriptionResponse(
        transcript=transcript,
        text_output=response.renderings.corrected_text_output,
        raw_text_output=response.renderings.raw_text_output,
        corrected_text_output=response.renderings.corrected_text_output,
        speaker_stats=response.speaker_stats,
        asr_status=transcript.metadata.get("asr_status"),
        warnings=list(transcript.metadata.get("warnings", [])),
        metadata=dict(transcript.metadata),
    )


@router.get("/transcript/{conversation_id}", response_model=TranscriptResponse)
async def get_transcript(request: Request, conversation_id: str) -> TranscriptResponse:
    transcript = request.app.state.transcription_service.get_transcript(conversation_id)
    if transcript is None:
        raise HTTPException(status_code=404, detail="Transcript not found.")
    return build_transcript_response(transcript)


@router.get("/summary/{conversation_id}", response_model=SummaryResponse)
async def get_summary(request: Request, conversation_id: str) -> SummaryResponse:
    transcript = request.app.state.transcription_service.get_transcript(conversation_id)
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
    transcript = request.app.state.transcription_service.get_transcript(conversation_id)
    if transcript is None:
        raise HTTPException(status_code=404, detail="Transcript not found.")
    return request.app.state.quality_service.build_report(transcript)


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
                    direction=step.direction
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
        # Map GraphNode to QueryResultItem
        results.append(
            QueryResultItem(
                result_type=node.type.value.lower(),
                text=node.properties.get("title") or node.properties.get("text") or "",
                source_session_id=node.source.session_id if node.source else "unknown",
                source_segment_id=node.source.segment_id if node.source else None,
                matched_by=node.properties.get("matched_by"),
                score=node.properties.get("score", 1.0),
                score_breakdown=node.properties.get("score_breakdown", {}),
                edge_path=node.properties.get("edge_path"),
                node_id=node.id,
                preview=node.properties.get("text")[:200] if node.properties.get("text") else None
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
