"""HTTP endpoints for file-based transcription and transcript retrieval."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ..models import FileTranscriptionResponse, HealthResponse, SummaryResponse
from ..pipeline.transcript_formatter import format_transcript

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        vad_provider=settings.vad_provider,
        asr_provider=settings.asr_provider,
        diarizer_provider=settings.diarizer_provider,
        llm_provider=settings.llm_provider,
    )


@router.post("/transcribe/file", response_model=FileTranscriptionResponse)
async def transcribe_file(
    request: Request,
    upload: UploadFile = File(...),
    language: str | None = Form(default=None),
) -> FileTranscriptionResponse:
    service = request.app.state.transcription_service
    settings = request.app.state.settings
    suffix = Path(upload.filename or "audio.bin").suffix or ".bin"
    source_path = settings.temp_dir / f"upload_{request.app.state.id_factory()}{suffix}"
    source_path.write_bytes(await upload.read())
    try:
        transcript = await service.transcribe_file(
            source_path,
            language=language,
            source="upload",
        )
    finally:
        source_path.unlink(missing_ok=True)
    return FileTranscriptionResponse(
        transcript=transcript,
        text_output=format_transcript(transcript),
    )


@router.get("/transcript/{conversation_id}")
async def get_transcript(request: Request, conversation_id: str):
    transcript = request.app.state.transcription_service.get_transcript(conversation_id)
    if transcript is None:
        raise HTTPException(status_code=404, detail="Transcript not found.")
    return transcript


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
    )
