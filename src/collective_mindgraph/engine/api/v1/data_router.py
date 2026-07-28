"""Settings and versioned data-exchange endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from collective_mindgraph.domain import MeetingId

from .errors import ERROR_RESPONSES
from .system_schemas import (
    EngineSettingsResponse,
    ImportResponse,
    UpdateEngineSettingsRequest,
)

router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


def _settings_response(settings) -> EngineSettingsResponse:
    return EngineSettingsResponse(
        language=settings.default_language,
        transcription_quality=settings.transcription_quality_mode,
        asr_provider=settings.asr_provider,
        asr_model=settings.asr_model_name,
        embeddings_enabled=settings.embedding_provider == "sentence_transformer",
        embedding_provider=settings.embedding_provider,
        local_llm_provider=settings.llm_provider,
        diarization_enabled=settings.diarization_enabled,
        retain_raw_audio=settings.retain_raw_audio,
    )


@router.put("/settings", response_model=EngineSettingsResponse)
async def update_settings(
    request: Request,
    payload: UpdateEngineSettingsRequest,
) -> EngineSettingsResponse:
    context = request.app.state.engine_context
    fields = {
        "default_language": payload.language,
        "transcription_quality_mode": payload.transcription_quality,
        "asr_provider": payload.asr_provider,
        "asr_model_name": payload.asr_model,
        "embedding_provider": payload.embedding_provider,
        "llm_provider": payload.local_llm_provider,
        "diarization_enabled": payload.diarization_enabled,
        "retain_raw_audio": payload.retain_raw_audio,
    }
    changes = {key: value for key, value in fields.items() if value is not None}
    previous_embedding_provider = context.settings.embedding_provider
    context.runtime.apply(changes)
    if (
        previous_embedding_provider != "sentence_transformer"
        and context.settings.embedding_provider == "sentence_transformer"
    ):
        context.recording_jobs.enqueue_reindex()
    return _settings_response(context.settings)


@router.get("/export")
async def export_data(request: Request, meeting_id: int | None = None):
    return request.app.state.engine_context.data_exchange.export(
        MeetingId(meeting_id) if meeting_id is not None else None
    )


@router.post("/import", response_model=ImportResponse)
async def import_data(
    request: Request,
    payload: dict[str, object],
) -> ImportResponse:
    imported = request.app.state.engine_context.data_exchange.import_payload(payload)
    return ImportResponse(imported=imported)
