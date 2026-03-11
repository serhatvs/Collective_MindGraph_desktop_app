import asyncio

from app.models import CorrectionResult, TranscriptSegment
from app.pipeline.llm_postprocess import (
    BaseLLMProvider,
    LLMPostProcessor,
    MockLLMProvider,
    _parse_json_results,
)


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


def test_parse_json_results_accepts_fenced_payload():
    source_segments = [
        TranscriptSegment(
            segment_id="seg_1",
            start=0.0,
            end=1.0,
            speaker="Speaker_1",
            raw_text="hello there",
            corrected_text="hello there",
        )
    ]

    corrections = _parse_json_results(
        """```json
{"segments":[{"segment_id":"seg_1","corrected_text":"Hello there.","notes":["ok"]}]}
```""",
        source_segments,
    )

    assert corrections[0].corrected_text == "Hello there."
    assert corrections[0].notes == ["ok"]


class CaptureProvider(BaseLLMProvider):
    def __init__(self) -> None:
        self.requests = []

    async def correct(self, request):
        self.requests.append(request)
        return [
            CorrectionResult(
                segment_id=item.segment_id,
                corrected_text=item.raw_text.upper(),
                notes=["captured"],
            )
            for item in request.segments
        ]


def test_llm_postprocessor_passes_context_segments_to_provider():
    provider = CaptureProvider()
    processor = LLMPostProcessor(provider=provider, batch_size=2, context_segments=1)
    segments = [
        TranscriptSegment(
            segment_id="seg_1",
            start=0.0,
            end=1.0,
            speaker="Speaker_1",
            raw_text="first turn",
            corrected_text="first turn",
        ),
        TranscriptSegment(
            segment_id="seg_2",
            start=1.0,
            end=2.0,
            speaker="Speaker_2",
            raw_text="second turn",
            corrected_text="second turn",
        ),
        TranscriptSegment(
            segment_id="seg_3",
            start=2.0,
            end=3.0,
            speaker="Speaker_1",
            raw_text="third turn",
            corrected_text="third turn",
        ),
    ]

    corrected = asyncio.run(processor.apply("conv_2", "en", segments))

    assert provider.requests[0].context_segments == []
    assert [item.segment_id for item in provider.requests[1].context_segments] == ["seg_2"]
    assert corrected[2].corrected_text == "THIRD TURN"
