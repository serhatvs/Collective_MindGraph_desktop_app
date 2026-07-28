"""Transport schemas for engine status and typed errors."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)
    retryable: bool = False


class EngineHealthResponse(BaseModel):
    status: str
    engine_version: str
    transcription: str
    embeddings: str
    local_llm: str
    database_path: str
    migration_performed: bool
    detail: str = ""


class EngineSettingsResponse(BaseModel):
    language: str | None
    transcription_quality: str
    asr_provider: str
    asr_model: str
    embeddings_enabled: bool
    embedding_provider: str
    local_llm_provider: str
    diarization_enabled: bool
    retain_raw_audio: bool = False
    labs_enabled: bool = True


class UpdateEngineSettingsRequest(BaseModel):
    language: str | None = Field(default=None, min_length=2, max_length=16)
    transcription_quality: str | None = None
    asr_provider: str | None = None
    asr_model: str | None = None
    embedding_provider: str | None = None
    local_llm_provider: str | None = None
    diarization_enabled: bool | None = None
    retain_raw_audio: bool | None = None


class ImportResponse(BaseModel):
    imported: dict[str, int] = Field(default_factory=dict)
