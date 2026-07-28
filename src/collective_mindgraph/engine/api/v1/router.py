"""Versioned HTTP surface consumed by the desktop client."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)

from collective_mindgraph.application import PageRequest
from collective_mindgraph.application.transcription.transcription_glossary import parse_term_input
from collective_mindgraph.domain import (
    EvidenceId,
    InsightId,
    KnowledgeNodeKind,
    MeetingId,
    Recording,
    RecordingId,
    RecordingStorageStatus,
    ReviewDecision,
    SegmentId,
)

from .errors import ERROR_RESPONSES
from .knowledge_schemas import (
    EvidencePageResponse,
    EvidenceResponse,
    InsightPageResponse,
    InsightResponse,
    KnowledgeEdgePageResponse,
    KnowledgeEdgeResponse,
    KnowledgeNodePageResponse,
    KnowledgeNodeResponse,
    ReviewInsightRequest,
)
from .meeting_schemas import (
    CreateMeetingRequest,
    DashboardResponse,
    MeetingPageResponse,
    MeetingResponse,
    ProcessingJobResponse,
    TranscriptResponse,
    TranscriptSegmentResponse,
    UpdateMeetingRequest,
    UpdateTranscriptSegmentRequest,
)
from .response_mapping import processing_job_response

router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


def _context(request: Request):
    return request.app.state.engine_context


def _meeting_response(meeting) -> MeetingResponse:
    return MeetingResponse(
        id=int(meeting.id),
        title=meeting.title,
        status=meeting.status.value,
        input_device=meeting.input_device,
        created_at=meeting.created_at,
        updated_at=meeting.updated_at,
    )


def _transcript_response(transcript) -> TranscriptResponse:
    return TranscriptResponse(
        id=int(transcript.id),
        meeting_id=int(transcript.meeting_id),
        conversation_id=transcript.conversation_id,
        provider=transcript.provider,
        language=transcript.language,
        raw_text=transcript.raw_text,
        corrected_text=transcript.corrected_text,
        confidence=transcript.confidence,
        created_at=transcript.created_at,
        updated_at=transcript.updated_at,
        segments=[
            TranscriptSegmentResponse(
                id=str(segment.id),
                position=segment.position,
                start_seconds=segment.start_seconds,
                end_seconds=segment.end_seconds,
                speaker_label=segment.speaker_label,
                raw_text=segment.raw_text,
                corrected_text=segment.corrected_text,
                confidence=segment.confidence,
            )
            for segment in transcript.segments
        ],
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(request: Request) -> DashboardResponse:
    snapshot = _context(request).dashboard()
    return DashboardResponse(
        total_meetings=snapshot.total_meetings,
        total_transcripts=snapshot.total_transcripts,
        total_knowledge_nodes=snapshot.total_knowledge_nodes,
        pending_reviews=snapshot.pending_reviews,
        recent_meetings=[_meeting_response(item) for item in snapshot.recent_meetings],
    )


@router.get("/meetings", response_model=MeetingPageResponse)
async def list_meetings(
    request: Request,
    query: str = "",
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> MeetingPageResponse:
    page = _context(request).list_meetings(
        PageRequest(cursor=cursor, limit=limit),
        query=query,
    )
    return MeetingPageResponse(
        items=[_meeting_response(item) for item in page.items],
        total=page.total,
        next_cursor=page.next_cursor,
    )


@router.post("/meetings", response_model=MeetingResponse, status_code=201)
async def create_meeting(request: Request, payload: CreateMeetingRequest) -> MeetingResponse:
    meeting = _context(request).create_meeting(payload.title, payload.input_device)
    return _meeting_response(meeting)


@router.get("/meetings/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(request: Request, meeting_id: int) -> MeetingResponse:
    meeting = _context(request).get_meeting(MeetingId(meeting_id))
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    return _meeting_response(meeting)


@router.patch("/meetings/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    request: Request,
    meeting_id: int,
    payload: UpdateMeetingRequest,
) -> MeetingResponse:
    context = _context(request)
    meeting = context.get_meeting(MeetingId(meeting_id))
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    if payload.title is not None:
        meeting = context.rename_meeting(MeetingId(meeting_id), payload.title)
    if payload.archived is True:
        meeting = context.archive_meeting(MeetingId(meeting_id))
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    return _meeting_response(meeting)


@router.delete("/meetings/{meeting_id}", status_code=204)
async def delete_meeting(request: Request, meeting_id: int) -> Response:
    context = _context(request)
    selected_meeting = MeetingId(meeting_id)
    async with context.recording_jobs.meeting_lock(selected_meeting):
        if context.get_meeting(selected_meeting) is None:
            raise HTTPException(status_code=404, detail="Meeting not found.")
        if context.recording_jobs.meeting_is_busy(selected_meeting):
            raise HTTPException(
                status_code=409,
                detail="Meeting has active recording work and cannot be deleted.",
            )
        for recording in context.recordings.list_for_meeting(selected_meeting):
            if context.recording_storage.is_managed(recording.source_uri):
                context.recording_storage.delete(recording.source_uri)
        if not context.delete_meeting(selected_meeting):
            raise HTTPException(status_code=404, detail="Meeting not found.")
    return Response(status_code=204)


@router.get("/meetings/{meeting_id}/transcript", response_model=TranscriptResponse)
async def get_meeting_transcript(request: Request, meeting_id: int) -> TranscriptResponse:
    transcript = _context(request).transcripts.latest_for_meeting(MeetingId(meeting_id))
    if transcript is None:
        raise HTTPException(status_code=404, detail="Transcript not found.")
    return _transcript_response(transcript)


@router.get(
    "/meetings/{meeting_id}/evidence",
    response_model=EvidencePageResponse,
)
async def list_meeting_evidence(
    request: Request,
    meeting_id: int,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> EvidencePageResponse:
    selected_meeting = MeetingId(meeting_id)
    if _context(request).get_meeting(selected_meeting) is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    page = _context(request).knowledge.list_evidence(
        PageRequest(cursor=cursor, limit=limit),
        meeting_id=selected_meeting,
    )
    return EvidencePageResponse(
        items=[_evidence_response(item) for item in page.items],
        total=page.total,
        next_cursor=page.next_cursor,
    )


@router.get("/evidence/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence(request: Request, evidence_id: str) -> EvidenceResponse:
    evidence = _context(request).knowledge.get_evidence(EvidenceId(evidence_id))
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found.")
    return _evidence_response(evidence)


@router.post(
    "/meetings/{meeting_id}/recordings",
    response_model=ProcessingJobResponse,
    status_code=202,
)
async def ingest_recording(
    request: Request,
    meeting_id: int,
    upload: UploadFile = File(...),
    language: str | None = Form(default=None),
    quality_mode: str | None = Form(default=None),
    session_glossary: str | None = Form(default=None),
    hotwords: str | None = Form(default=None),
) -> ProcessingJobResponse:
    context = _context(request)
    selected_meeting = MeetingId(meeting_id)
    async with context.recording_jobs.meeting_lock(selected_meeting):
        meeting = context.get_meeting(selected_meeting)
        if meeting is None:
            raise HTTPException(status_code=404, detail="Meeting not found.")
        recording_id = RecordingId(str(uuid4()))
        source_path, source_uri = context.recording_storage.allocate(
            selected_meeting,
            recording_id,
            upload.filename or "audio.bin",
        )
        try:
            await _store_upload(upload, source_path)
            if source_path.stat().st_size == 0:
                raise HTTPException(status_code=422, detail="Recording upload is empty.")
        except BaseException:
            source_path.unlink(missing_ok=True)
            raise
        recording = Recording(
            id=recording_id,
            meeting_id=selected_meeting,
            source_uri=source_uri,
            duration_seconds=None,
            input_device=meeting.input_device,
            storage_status=RecordingStorageStatus.MANAGED,
            keep_audio=context.settings.retain_raw_audio,
            captured_at=datetime.now(tz=UTC),
        )
        context.recordings.save(recording)
        try:
            job = context.recording_jobs.enqueue(
                recording,
                language=language,
                quality_mode=quality_mode,
                session_glossary_terms=parse_term_input(session_glossary) or None,
                user_hotwords=parse_term_input(hotwords) or None,
            )
        except BaseException:
            context.recordings.update_storage(
                recording_id,
                status=RecordingStorageStatus.RETAINED,
            )
            raise
    return processing_job_response(job)


@router.patch(
    "/transcript-segments/{segment_id}",
    response_model=TranscriptSegmentResponse,
)
async def update_transcript_segment(
    request: Request,
    segment_id: str,
    payload: UpdateTranscriptSegmentRequest,
) -> TranscriptSegmentResponse:
    segment = _context(request).update_transcript_segment(
        SegmentId(segment_id),
        payload.corrected_text,
    )
    if segment is None:
        raise HTTPException(status_code=404, detail="Transcript segment not found.")
    return TranscriptSegmentResponse(
        id=str(segment.id),
        position=segment.position,
        start_seconds=segment.start_seconds,
        end_seconds=segment.end_seconds,
        speaker_label=segment.speaker_label,
        raw_text=segment.raw_text,
        corrected_text=segment.corrected_text,
        confidence=segment.confidence,
        needs_review=True,
    )


@router.get("/insights", response_model=InsightPageResponse)
async def list_insights(
    request: Request,
    meeting_id: int | None = None,
    review: str | None = None,
    query: str = "",
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> InsightPageResponse:
    review_decision = ReviewDecision(review) if review else None
    page = _context(request).insights.list(
        PageRequest(cursor=cursor, limit=limit),
        meeting_id=MeetingId(meeting_id) if meeting_id is not None else None,
        review=review_decision,
        query=query,
    )
    return InsightPageResponse(
        items=[InsightResponse(**_insight_payload(item)) for item in page.items],
        total=page.total,
        next_cursor=page.next_cursor,
    )


@router.patch("/insights/{insight_id}/review", response_model=InsightResponse)
async def review_insight(
    request: Request,
    insight_id: str,
    payload: ReviewInsightRequest,
) -> InsightResponse:
    try:
        decision = ReviewDecision(payload.decision)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Unsupported review decision.") from exc
    insight = _context(request).review_insight(
        InsightId(insight_id),
        decision=decision,
        title=payload.title,
        body=payload.body,
    )
    if insight is None:
        raise HTTPException(status_code=404, detail="Insight not found.")
    return InsightResponse(**_insight_payload(insight))


@router.get("/knowledge/nodes", response_model=KnowledgeNodePageResponse)
async def list_knowledge_nodes(
    request: Request,
    query: str = "",
    meeting_id: int | None = None,
    kind: str | None = None,
    review: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> KnowledgeNodePageResponse:
    page = _context(request).knowledge.list_nodes(
        PageRequest(cursor=cursor, limit=limit),
        query=query,
        meeting_id=MeetingId(meeting_id) if meeting_id is not None else None,
        kind=KnowledgeNodeKind(kind) if kind else None,
        review=ReviewDecision(review) if review else None,
    )
    return KnowledgeNodePageResponse(
        items=[
            KnowledgeNodeResponse(
                id=str(item.id),
                meeting_id=int(item.meeting_id) if item.meeting_id is not None else None,
                kind=item.kind.value,
                title=item.title,
                body=item.body,
                evidence_id=str(item.evidence_id) if item.evidence_id else None,
                attributes=item.attributes,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in page.items
        ],
        total=page.total,
        next_cursor=page.next_cursor,
    )


@router.get("/knowledge/edges", response_model=KnowledgeEdgePageResponse)
async def list_knowledge_edges(
    request: Request,
    query: str = "",
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> KnowledgeEdgePageResponse:
    page = _context(request).knowledge.list_edges(
        PageRequest(cursor=cursor, limit=limit),
        query=query,
    )
    return KnowledgeEdgePageResponse(
        items=[
            KnowledgeEdgeResponse(
                id=str(item.id),
                source_id=str(item.source_id),
                target_id=str(item.target_id),
                kind=item.kind.value,
                evidence_id=str(item.evidence_id) if item.evidence_id else None,
                confidence=item.confidence,
                attributes=item.attributes,
                created_at=item.created_at,
            )
            for item in page.items
        ],
        total=page.total,
        next_cursor=page.next_cursor,
    )


def _insight_payload(insight) -> dict[str, object]:
    return {
        "id": str(insight.id),
        "meeting_id": int(insight.meeting_id),
        "kind": insight.kind.value,
        "title": insight.title,
        "body": insight.body,
        "review": insight.review.value,
        "evidence_id": str(insight.evidence_id) if insight.evidence_id else None,
        "confidence": insight.confidence,
        "edited_by_user": insight.edited_by_user,
        "needs_review": insight.needs_review,
        "created_at": insight.created_at,
        "updated_at": insight.updated_at,
    }


def _evidence_response(evidence) -> EvidenceResponse:
    return EvidenceResponse(
        id=str(evidence.id),
        meeting_id=int(evidence.meeting_id),
        segment_id=str(evidence.segment_id) if evidence.segment_id else None,
        start_seconds=evidence.start_seconds,
        end_seconds=evidence.end_seconds,
        text_preview=evidence.text_preview,
        confidence=evidence.confidence,
        extractor=evidence.extractor,
        created_at=evidence.created_at,
    )


async def _store_upload(upload: UploadFile, target: Path) -> None:
    max_bytes = 2 * 1024 * 1024 * 1024
    written = 0
    with target.open("xb") as destination:
        while chunk := await upload.read(1024 * 1024):
            written += len(chunk)
            if written > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail="Recording exceeds the 2 GiB local ingest limit.",
                )
            destination.write(chunk)
