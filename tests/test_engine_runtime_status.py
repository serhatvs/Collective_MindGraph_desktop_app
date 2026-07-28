import asyncio

from collective_mindgraph.application.transcription.contracts import (
    ConversationTranscript,
    TranscriptSegment,
)
from collective_mindgraph.application.transcription.extract_structured_insights import (
    ExtractStructuredInsights,
)


class _UnavailableModel:
    provider_name = "test"

    def is_available(self) -> bool:
        return False

    def generate_structured_json(self, prompt, schema):
        raise AssertionError("unavailable model must not be called")


class _AvailableModel:
    provider_name = "test"

    def is_available(self) -> bool:
        return True

    def generate_structured_json(self, prompt, schema):
        return {"summary": "LLM Sum", "tasks": [], "decisions": [], "topics": []}


def _transcript() -> ConversationTranscript:
    return ConversationTranscript(
        conversation_id="test",
        source="test",
        segments=[
            TranscriptSegment(
                segment_id="s1",
                start=0,
                end=1,
                speaker="S",
                corrected_text="test",
            )
        ],
    )


def test_extraction_reports_fallback_when_local_model_is_unavailable():
    result = asyncio.run(
        ExtractStructuredInsights(_UnavailableModel()).extract_intelligence(_transcript())
    )
    assert result.metadata["extraction_source"] == "heuristic_fallback"
    assert "not reachable" in result.metadata["extraction_fallback_reason"]


def test_extraction_reports_local_model_success():
    result = asyncio.run(
        ExtractStructuredInsights(_AvailableModel()).extract_intelligence(_transcript())
    )
    assert result.metadata["extraction_source"] == "local_llm"
    assert result.summary == "LLM Sum"
