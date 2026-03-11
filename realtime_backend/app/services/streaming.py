"""Incremental WebSocket-oriented streaming transcription service."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ..config import Settings
from ..models import ConversationTranscript, TranscriptSegment
from ..pipeline.speaker_mapper import StableSpeakerMapper
from ..services.conversation_store import ConversationStore
from ..services.media import FFmpegAudioNormalizer
from ..services.summary import ConversationSummaryService
from ..utils.ids import new_conversation_id

if TYPE_CHECKING:
    from ..pipeline.orchestrator import TranscriptionPipeline


@dataclass
class StreamSession:
    conversation_id: str
    language: str | None
    pcm_buffer: bytearray = field(default_factory=bytearray)
    buffer_start_seconds: float = 0.0
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
            total_duration = self._buffer_end_seconds(session)
            if total_duration - session.committed_seconds < self._settings.stream_min_emit_seconds:
                return None
            return await self._flush(session, finalize=False)

    async def finalize(self, conversation_id: str) -> ConversationTranscript:
        session = self._sessions[conversation_id]
        async with session.lock:
            transcript = await self._flush(session, finalize=True)
            transcript.status = "completed"
            summary, topics, action_items, decisions = self._summary_service.build_summary(transcript)
            transcript.summary = summary
            transcript.topics = topics
            transcript.action_items = action_items
            transcript.decisions = decisions
            transcript.updated_at = datetime.now(tz=UTC)
            self._store.save(transcript)
            self._sessions.pop(conversation_id, None)
            return transcript

    async def flush_partial(self, conversation_id: str) -> ConversationTranscript:
        session = self._sessions[conversation_id]
        async with session.lock:
            transcript = await self._flush(session, finalize=False)
            self._store.save(transcript)
            return transcript

    async def _flush(self, session: StreamSession, finalize: bool) -> ConversationTranscript:
        buffer_end = self._buffer_end_seconds(session)
        if buffer_end <= session.buffer_start_seconds:
            return session.transcript

        window_start = self._window_start_seconds(session, buffer_end, finalize)
        start_byte = self._offset_to_byte_index(session, window_start)
        window_pcm = bytes(session.pcm_buffer[start_byte:])
        wav_path = self._settings.temp_dir / f"{session.conversation_id}_{int(buffer_end * 1000)}.wav"
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
        session.committed_seconds = buffer_end
        if not finalize:
            self._compact_buffer(session, buffer_end)
        return session.transcript

    @staticmethod
    def _replace_tail(
        existing: list[TranscriptSegment],
        incoming: list[TranscriptSegment],
        from_second: float,
    ) -> list[TranscriptSegment]:
        preserved = [segment for segment in existing if segment.end <= from_second]
        return preserved + incoming

    def _buffer_end_seconds(self, session: StreamSession) -> float:
        bytes_per_second = (
            self._settings.sample_rate * self._settings.channels * self._settings.sample_width_bytes
        )
        buffered_seconds = len(session.pcm_buffer) / bytes_per_second if bytes_per_second else 0.0
        return session.buffer_start_seconds + buffered_seconds

    def _window_start_seconds(self, session: StreamSession, buffer_end: float, finalize: bool) -> float:
        if finalize or session.committed_seconds <= session.buffer_start_seconds:
            return session.buffer_start_seconds

        overlap_start = max(session.buffer_start_seconds, session.committed_seconds - self._settings.stream_overlap_seconds)
        bounded_start = max(
            session.buffer_start_seconds,
            buffer_end - self._settings.stream_partial_window_seconds,
        )
        return min(overlap_start, bounded_start)

    def _offset_to_byte_index(self, session: StreamSession, offset_seconds: float) -> int:
        bytes_per_second = (
            self._settings.sample_rate * self._settings.channels * self._settings.sample_width_bytes
        )
        frame_size = self._settings.channels * self._settings.sample_width_bytes
        relative_seconds = max(0.0, offset_seconds - session.buffer_start_seconds)
        byte_index = int(relative_seconds * bytes_per_second)
        if frame_size > 0:
            byte_index -= byte_index % frame_size
        return max(0, min(len(session.pcm_buffer), byte_index))

    def _compact_buffer(self, session: StreamSession, buffer_end: float) -> None:
        retention_seconds = max(
            self._settings.stream_buffer_retention_seconds,
            self._settings.stream_partial_window_seconds + self._settings.stream_overlap_seconds,
        )
        keep_from = max(0.0, buffer_end - retention_seconds)
        if keep_from <= session.buffer_start_seconds:
            return

        drop_byte_index = self._offset_to_byte_index(session, keep_from)
        if drop_byte_index <= 0:
            return

        bytes_per_second = (
            self._settings.sample_rate * self._settings.channels * self._settings.sample_width_bytes
        )
        dropped_seconds = drop_byte_index / bytes_per_second if bytes_per_second else 0.0
        session.pcm_buffer = bytearray(session.pcm_buffer[drop_byte_index:])
        session.buffer_start_seconds += dropped_seconds
