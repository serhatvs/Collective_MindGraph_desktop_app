"""Runtime health and settings reads."""

from __future__ import annotations

from fastapi import APIRouter, Request

from collective_mindgraph import __version__

from .errors import ERROR_RESPONSES
from .system_schemas import EngineHealthResponse, EngineSettingsResponse

router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


@router.get("/health", response_model=EngineHealthResponse)
async def engine_health(request: Request) -> EngineHealthResponse:
    context = request.app.state.engine_context
    health = context.runtime_bundle.health(engine_version=__version__)
    return EngineHealthResponse(
        status=health.status.value,
        engine_version=health.engine_version,
        transcription=health.transcription.value,
        embeddings=health.embeddings.value,
        local_llm=health.local_llm.value,
        database_path=str(context.database.path),
        migration_performed=context.migration.migrated,
        detail=health.detail,
    )


@router.get("/settings", response_model=EngineSettingsResponse)
async def engine_settings(request: Request) -> EngineSettingsResponse:
    settings = request.app.state.engine_context.settings
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
