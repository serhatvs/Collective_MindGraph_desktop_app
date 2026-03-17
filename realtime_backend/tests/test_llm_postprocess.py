import asyncio

import httpx

from app.config import Settings
from app.models import CorrectionRequest, CorrectionResult, TranscriptSegment
from app.pipeline import llm_postprocess as llm_module
from app.pipeline.llm_postprocess import (
    AutoLocalLLMProvider,
    BaseLLMProvider,
    BedrockAutoLocalLLMProvider,
    LLMPostProcessor,
    MockLLMProvider,
    _extract_bedrock_text,
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


def test_auto_local_llm_provider_falls_back_to_mock_cleanup():
    provider = AutoLocalLLMProvider(Settings())

    async def failing_remote(_request):
        raise httpx.ConnectError("unreachable")

    provider._remote_provider.correct = failing_remote  # type: ignore[method-assign]
    request_segments = [
        TranscriptSegment(
            segment_id="seg_1",
            start=0.0,
            end=1.0,
            speaker="Speaker_1",
            raw_text="hello world",
            corrected_text="hello world",
        )
    ]

    corrected = asyncio.run(
        provider.correct(
            CorrectionRequest(
                conversation_id="conv_x",
                language="en",
                context_segments=[],
                segments=request_segments,
            )
        )
    )

    assert corrected[0].corrected_text == "Hello world."


def test_extract_bedrock_text_joins_message_fragments():
    payload = {
        "output": {
            "message": {
                "content": [
                    {"text": '{"segments": ['},
                    {"text": '{"segment_id":"seg_1","corrected_text":"Hello."}'},
                    {"text": "]}"}
                ]
            }
        }
    }

    content = _extract_bedrock_text(payload)

    assert content == '{"segments": [{"segment_id":"seg_1","corrected_text":"Hello."}]}'


def test_bedrock_auto_local_llm_provider_falls_back_when_bedrock_fails(monkeypatch):
    class FakeBedrockProvider(BaseLLMProvider):
        async def correct(self, request):
            raise RuntimeError("bedrock unavailable")

    monkeypatch.setattr(llm_module, "BedrockLLMProvider", lambda settings: FakeBedrockProvider())
    provider = BedrockAutoLocalLLMProvider(Settings())
    request_segments = [
        TranscriptSegment(
            segment_id="seg_1",
            start=0.0,
            end=1.0,
            speaker="Speaker_1",
            raw_text="hello world",
            corrected_text="hello world",
        )
    ]

    corrected = asyncio.run(
        provider.correct(
            CorrectionRequest(
                conversation_id="conv_bedrock",
                language="en",
                context_segments=[],
                segments=request_segments,
            )
        )
    )

    assert corrected[0].corrected_text == "Hello world."


def test_build_llm_postprocessor_defaults_to_bedrock_auto_local():
    processor = llm_module.build_llm_postprocessor(Settings())

    assert processor._provider.__class__.__name__ == "BedrockAutoLocalLLMProvider"
