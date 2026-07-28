"""Verify local-first structured extraction and its safe fallback."""

from __future__ import annotations

import asyncio

from collective_mindgraph.application.transcription.contracts import (
    ConversationTranscript,
    TranscriptSegment,
)
from collective_mindgraph.application.transcription.extract_structured_insights import (
    ExtractStructuredInsights,
)
from collective_mindgraph.engine.settings import EngineSettings
from collective_mindgraph.infrastructure.ai import LocalEndpointLanguageModel


async def run() -> int:
    settings = EngineSettings()
    model = (
        LocalEndpointLanguageModel(
            settings.llm_endpoint,
            timeout=int(settings.llm_timeout_seconds),
        )
        if settings.llm_endpoint
        else None
    )
    transcript = ConversationTranscript(
        conversation_id="extraction_verification",
        source="verification",
        segments=[
            TranscriptSegment(
                segment_id="segment-1",
                start=0,
                end=5,
                speaker="Speaker 1",
                corrected_text="FastAPI endpointini bu hafta test edeceğiz.",
            )
        ],
    )
    result = await ExtractStructuredInsights(model).extract_intelligence(transcript)
    print(f"Extraction source: {result.metadata['extraction_source']}")
    print(f"Summary: {result.summary}")
    return 0


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
