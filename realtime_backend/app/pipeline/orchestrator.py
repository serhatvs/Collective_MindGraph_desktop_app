"""Pipeline orchestration from normalized audio to structured transcript."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from ..config import Settings
from ..models import ConversationTranscript, ProcessingDebug, TranscriptSegment
from ..services.summary import ConversationSummaryService
from ..utils.ids import new_conversation_id
from .alignment import merge_transcript_segments
from .asr import BaseASR, build_asr
from .diarization import BaseDiarizer, build_diarizer
from .llm_postprocess import LLMPostProcessor, build_llm_postprocessor
from .speaker_mapper import StableSpeakerMapper
from .vad import BaseVAD, build_vad


class TranscriptionPipeline:
    def __init__(
        self,
        settings: Settings,
        vad: BaseVAD | None = None,
        asr: BaseASR | None = None,
        diarizer: BaseDiarizer | None = None,
        llm_postprocessor: LLMPostProcessor | None = None,
        summary_service: ConversationSummaryService | None = None,
    ) -> None:
        self._settings = settings
        self._vad = vad or build_vad(settings)
        self._asr = asr or build_asr(settings)
        self._diarizer = diarizer or build_diarizer(settings)
        self._llm_postprocessor = llm_postprocessor or build_llm_postprocessor(settings)
        self._summary_service = summary_service or ConversationSummaryService()

    async def process_audio_path(
        self,
        audio_path: Path,
        *,
        conversation_id: str | None = None,
        source: str,
        language: str | None = None,
        prior_segments: list[TranscriptSegment] | None = None,
        speaker_mapper: StableSpeakerMapper | None = None,
        chunk_offset: float = 0.0,
        include_summary: bool = True,
        debug: bool = True,
    ) -> ConversationTranscript:
        resolved_conversation_id = conversation_id or new_conversation_id()
        prior = list(prior_segments or [])
        mapper = speaker_mapper or StableSpeakerMapper()

        vad_regions = await asyncio.to_thread(self._vad.detect, audio_path)
        asr_segments = await asyncio.to_thread(self._asr.transcribe, audio_path, language, vad_regions)
        diarization_turns = await asyncio.to_thread(self._diarizer.diarize, audio_path, vad_regions)
        merged_segments = merge_transcript_segments(
            asr_segments=asr_segments,
            diarization_turns=diarization_turns,
            speaker_mapper=mapper,
            prior_segments=prior,
            chunk_offset=chunk_offset,
        )
        corrected_segments = await self._llm_postprocessor.apply(
            conversation_id=resolved_conversation_id,
            language=language or self._settings.default_language,
            segments=merged_segments,
        )

        transcript = ConversationTranscript(
            conversation_id=resolved_conversation_id,
            source=source,
            language=language or self._settings.default_language,
            segments=corrected_segments,
            debug=ProcessingDebug(
                vad_regions=vad_regions,
                diarization_turns=diarization_turns,
                asr_segments=asr_segments,
            )
            if debug
            else None,
        )

        if include_summary:
            summary, topics, action_items = self._summary_service.build_summary(transcript)
            transcript.summary = summary
            transcript.topics = topics
            transcript.action_items = action_items
        transcript.updated_at = datetime.now(tz=UTC)
        return transcript
