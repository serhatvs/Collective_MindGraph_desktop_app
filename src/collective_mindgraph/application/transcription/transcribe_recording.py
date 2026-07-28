"""File-ingest use case for the complete transcription workflow."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from collective_mindgraph.domain import MeetingId, RecordingId

from .contracts import ConversationTranscript
from .conversation_ids import new_conversation_id, validate_conversation_id
from .processing_port import ProcessingRuntimeSnapshot, RecordingProcessorPort
from .result_archive import TranscriptionResultArchive


class TranscribeRecording:
    def __init__(
        self,
        processor: RecordingProcessorPort,
        archive: TranscriptionResultArchive,
    ) -> None:
        self._processor = processor
        self._archive = archive

    async def transcribe_file(
        self,
        source_path: Path,
        *,
        meeting_id: MeetingId | None = None,
        conversation_id: str | None = None,
        language: str | None = None,
        quality_mode: str | None = None,
        session_glossary_terms: list[str] | None = None,
        user_hotwords: list[str] | None = None,
        source: str = "file",
        recording_source_uri: str | None = None,
        recording_id: RecordingId | None = None,
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> ConversationTranscript:
        transcript_id = (
            validate_conversation_id(conversation_id) if conversation_id else new_conversation_id()
        )
        result = await self._processor.process_audio_path(
            source_path,
            conversation_id=transcript_id,
            source=source,
            language=language,
            quality_mode=quality_mode,
            session_glossary_terms=session_glossary_terms,
            user_hotwords=user_hotwords,
            progress_callback=progress_callback,
        )
        if progress_callback is not None:
            progress_callback("persistence", 90)
        self._archive.save(
            result,
            meeting_id=meeting_id,
            source_path=source_path,
            source_uri=recording_source_uri,
            recording_id=recording_id,
        )
        return result

    def get_transcript(self, conversation_id: str) -> ConversationTranscript | None:
        return self._archive.get(validate_conversation_id(conversation_id))

    def runtime_status(self) -> ProcessingRuntimeSnapshot:
        return self._processor.runtime_status()
