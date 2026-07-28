"""Seed one Turkish demo meeting into the canonical local database."""

from __future__ import annotations

from collective_mindgraph.application.transcription.contracts import (
    ConversationTranscript,
    TranscriptSegment,
)
from collective_mindgraph.application.transcription.extract_insights import (
    ExtractTranscriptInsights,
)
from collective_mindgraph.engine.context import build_engine_context
from collective_mindgraph.engine.settings import get_engine_settings
from collective_mindgraph.infrastructure.persistence import (
    CanonicalTranscriptionResultArchive,
)


def main() -> int:
    context = build_engine_context(get_engine_settings())
    meeting = context.create_meeting("Collective MindGraph Demo")
    transcript = ConversationTranscript(
        conversation_id="demo_technical_turkish",
        source="demo",
        language="tr",
        segments=[
            TranscriptSegment(
                segment_id="demo-segment-1",
                start=0,
                end=12,
                speaker="Konuşmacı 1",
                raw_text="FastAPI endpointini test edeceğiz.",
                corrected_text="FastAPI endpointini bu hafta test edeceğiz.",
            ),
            TranscriptSegment(
                segment_id="demo-segment-2",
                start=12,
                end=24,
                speaker="Konuşmacı 2",
                raw_text="Ham ve düzeltilmiş metin ayrı tutulacak.",
                corrected_text="Ham ve düzeltilmiş metin ayrı tutulacak.",
            ),
        ],
    )
    (
        transcript.summary,
        transcript.topics,
        transcript.action_items,
        transcript.decisions,
    ) = ExtractTranscriptInsights().build_summary(transcript)
    CanonicalTranscriptionResultArchive(
        context.meetings,
        context.recordings,
        context.transcripts,
        context.insights,
        context.knowledge,
    ).save(transcript, meeting_id=meeting.id)
    print(f"Created meeting {meeting.id}: {meeting.title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
