"""High-level file transcription service."""

from __future__ import annotations

from pathlib import Path

from ..models import ConversationTranscript
from ..pipeline.orchestrator import TranscriptionPipeline, TranscriptionRuntimeStatus
from ..services.conversation_store import ConversationStore
from ..utils.ids import new_conversation_id, validate_conversation_id


class TranscriptionService:
    def __init__(
        self,
        pipeline: TranscriptionPipeline,
        store: ConversationStore,
    ) -> None:
        self._pipeline = pipeline
        self._store = store

    async def transcribe_file(
        self,
        source_path: Path,
        *,
        conversation_id: str | None = None,
        language: str | None = None,
        quality_mode: str | None = None,
        session_glossary_terms: list[str] | None = None,
        user_hotwords: list[str] | None = None,
        source: str = "file",
    ) -> ConversationTranscript:
        transcript_id = validate_conversation_id(conversation_id) if conversation_id else new_conversation_id()
        transcript = await self._pipeline.process_audio_path(
            source_path,
            conversation_id=transcript_id,
            source=source,
            language=language,
            quality_mode=quality_mode,
            session_glossary_terms=session_glossary_terms,
            user_hotwords=user_hotwords,
        )
        self._store.save(transcript)
        return transcript

    def get_transcript(self, conversation_id: str) -> ConversationTranscript | None:
        return self._store.get(conversation_id)

    def runtime_status(self) -> TranscriptionRuntimeStatus:
        return self._pipeline.runtime_status()
