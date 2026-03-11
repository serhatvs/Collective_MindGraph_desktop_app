import asyncio

from app.models import TranscriptSegment
from app.pipeline.llm_postprocess import LLMPostProcessor, MockLLMProvider


def test_mock_llm_provider_preserves_structure_and_adds_punctuation():
    processor = LLMPostProcessor(provider=MockLLMProvider(), batch_size=8)
    segments = [
        TranscriptSegment(
            segment_id="seg_1",
            start=0.0,
            end=1.0,
            speaker="Speaker_1",
            raw_text="hello there",
            corrected_text="hello there",
        )
    ]

    corrected = asyncio.run(processor.apply("conv_1", "en", segments))

    assert corrected[0].speaker == "Speaker_1"
    assert corrected[0].raw_text == "hello there"
    assert corrected[0].corrected_text == "Hello there."
