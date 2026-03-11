"""Incremental WebSocket-oriented streaming transcription service."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ..config import Settings
from ..models import ConversationTranscript, TranscriptSegment
from ..pipeline.orchestrator import TranscriptionPipeline
from ..pipeline.speaker_mapper import StableSpeakerMapper
from ..services.conversation_store import ConversationStore
from ..services.media import FFmpegAudioNormalizer
from ..services.summary import ConversationSummaryService
from ..utils.ids import new_conversation_id


@dataclass
class StreamSession:
    conversation_id: str
    language: str | None
    pcm_buffer: bytearray = field(default_factory=bytearray)
    committed_seconds: float = 0.0
    transcript: ConversationTranscript = field(
        default_factory=lambda: ConversationTranscript(conversation_id=new_conversation_id(), source="stream")
    )
    speaker_mapper: StableSpeakerMapper = field(default_factory=StableSpeakerMapper)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class StreamingTranscriptionService:
    def __init__(
        self,
        settings: Settings,
        pipeline: TranscriptionPipeline,
        normalizer: FFmpegAudioNormalizer,
        store: ConversationStore,
        summary_service: ConversationSummaryService | None = None,
    ) -> None:
        self._settings = settings
        self._pipeline = pipeline
        self._normalizer = normalizer
        self._store = store
        self._summary_service = summary_service or ConversationSummaryService()
        self._sessions: dict[str, StreamSession] = {}

    def create_session(self, language: str | None = None) -> StreamSession:
        conversation_id = new_conversation_id()
        session = StreamSession(
            conversation_id=conversation_id,
            language=language,
            transcript=ConversationTranscript(
                conversation_id=conversation_id,
                source="stream",
                language=language,
                status="streaming",
            ),
        )
        self._sessions[conversation_id] = session
        return session

    def get_session(self, conversation_id: str) -> StreamSession | None:
        return self._sessions.get(conversation_id)

    async def append_audio(self, conversation_id: str, pcm_chunk: bytes) -> ConversationTranscript | None:
        session = self._sessions[conversation_id]
        async with session.lock:
            session.pcm_buffer.extend(pcm_chunk)
            total_duration = self._pcm_duration_seconds(session)
            if total_duration - session.committed_seconds < self._settings.stream_min_emit_seconds:
                return None
            return await self._flush(session, finalize=False)

    async def finalize(self, conversation_id: str) -> ConversationTranscript:
        session = self._sessions[conversation_id]
        async with session.lock:
            transcript = await self._flush(session, finalize=True)
            transcript.status = "completed"
            summary, topics, action_items = self._summary_service.build_summary(transcript)
            transcript.summary = summary
            transcript.topics = topics
            transcript.action_items = action_items
            transcript.updated_at = datetime.now(tz=UTC)
            self._store.save(transcript)
            return transcript

    async def flush_partial(self, conversation_id: str) -> ConversationTranscript:
        session = self._sessions[conversation_id]
        async with session.lock:
            transcript = await self._flush(session, finalize=False)
            self._store.save(transcript)
            return transcript

    async def _flush(self, session: StreamSession, finalize: bool) -> ConversationTranscript:
        total_duration = self._pcm_duration_seconds(session)
        if total_duration <= 0:
            return session.transcript

        overlap = self._settings.stream_overlap_seconds
        window_start = 0.0 if finalize else max(0.0, session.committed_seconds - overlap)
        bytes_per_second = (
            self._settings.sample_rate * self._settings.channels * self._settings.sample_width_bytes
        )
        start_byte = int(window_start * bytes_per_second)
        window_pcm = bytes(session.pcm_buffer[start_byte:])
        wav_path = self._settings.temp_dir / f"{session.conversation_id}_{int(total_duration * 1000)}.wav"
        await asyncio.to_thread(
            self._normalizer.pcm_to_wav,
            window_pcm,
            wav_path,
            self._settings.sample_width_bytes,
        )
        partial = await self._pipeline.process_audio_path(
            wav_path,
            conversation_id=session.conversation_id,
            source="stream",
            language=session.language,
            prior_segments=session.transcript.segments,
            speaker_mapper=session.speaker_mapper,
            chunk_offset=window_start,
            include_summary=False,
            debug=False,
        )
        session.transcript.segments = self._replace_tail(
            session.transcript.segments,
            partial.segments,
            window_start,
        )
        session.transcript.updated_at = datetime.now(tz=UTC)
        self._store.save(session.transcript)
        session.committed_seconds = total_duration
        return session.transcript

    @staticmethod
    def _replace_tail(
        existing: list[TranscriptSegment],
        incoming: list[TranscriptSegment],
        from_second: float,
    ) -> list[TranscriptSegment]:
        preserved = [segment for segment in existing if segment.start < from_second]
        return preserved + incoming

    def _pcm_duration_seconds(self, session: StreamSession) -> float:
        bytes_per_second = (
            self._settings.sample_rate * self._settings.channels * self._settings.sample_width_bytes
        )
        return len(session.pcm_buffer) / bytes_per_second if bytes_per_second else 0.0
