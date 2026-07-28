import asyncio

import pytest

from collective_mindgraph.application.transcription.contracts import (
    ConversationTranscript,
    TranscriptSegment,
)
from collective_mindgraph.application.transcription.extract_structured_insights import (
    ExtractStructuredInsights,
)
from collective_mindgraph.engine.settings import EngineSettings
from collective_mindgraph.infrastructure.ai.local_language_model import (
    LocalEndpointLanguageModel,
)


@pytest.mark.local_model
def test_real_local_llm_extraction():
    settings = EngineSettings()
    if not settings.llm_endpoint:
        pytest.skip("No local language-model endpoint is configured.")
    model = LocalEndpointLanguageModel(settings.llm_endpoint)
    if not model.is_available():
        pytest.skip(f"Local language-model server is unavailable at {model.base_url}.")

    transcript = ConversationTranscript(
        conversation_id="real_llm_test",
        source="verification",
        segments=[
            TranscriptSegment(
                segment_id="s1",
                start=0,
                end=10,
                speaker="Serhat",
                corrected_text="Bu hafta FastAPI endpointini test edeceğiz.",
            )
        ],
    )
    result = asyncio.run(
        ExtractStructuredInsights(model, mode="local_llm").extract_intelligence(transcript)
    )

    assert result.metadata["extraction_source"] == "local_llm"
    assert result.metadata["json_valid"] is True
