"""High-level file transcription service."""

from __future__ import annotations

import asyncio
from pathlib import Path

from ..config import Settings
from ..models import ConversationTranscript
from ..pipeline.orchestrator import TranscriptionPipeline
from ..services.conversation_store import ConversationStore
from ..services.media import FFmpegAudioNormalizer
from ..utils.ids import new_conversation_id


class TranscriptionService:
    def __init__(
        self,
        settings: Settings,
        pipeline: TranscriptionPipeline,
        store: ConversationStore,
        normalizer: FFmpegAudioNormalizer,
    ) -> None:
        self._settings = settings
        self._pipeline = pipeline
        self._store = store
        self._normalizer = normalizer

    async def transcribe_file(
        self,
        source_path: Path,
        *,
        conversation_id: str | None = None,
        language: str | None = None,
        quality_mode: str | None = None,
        source: str = "file",
    ) -> ConversationTranscript:
        transcript_id = conversation_id or new_conversation_id()
        # Note: TranscriptionPipeline.process_audio_path handles normalization internally
        transcript = await self._pipeline.process_audio_path(
            source_path,
            conversation_id=transcript_id,
            source=source,
            language=language,
            quality_mode=quality_mode,
        )
        self._store.save(transcript)
        return transcript

    def get_transcript(self, conversation_id: str) -> ConversationTranscript | None:
        return self._store.get(conversation_id)
