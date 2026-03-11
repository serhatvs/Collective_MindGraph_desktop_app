"""LLM post-processing for readability and context consistency."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import httpx

from ..config import Settings
from ..models import CorrectionRequest, CorrectionResult, TranscriptSegment


class BaseLLMProvider(ABC):
    @abstractmethod
    async def correct(self, request: CorrectionRequest) -> list[CorrectionResult]:
        raise NotImplementedError


class NoOpLLMProvider(BaseLLMProvider):
    async def correct(self, request: CorrectionRequest) -> list[CorrectionResult]:
        return [
            CorrectionResult(segment_id=item.segment_id, corrected_text=item.raw_text)
            for item in request.segments
        ]


class MockLLMProvider(BaseLLMProvider):
    async def correct(self, request: CorrectionRequest) -> list[CorrectionResult]:
        corrected: list[CorrectionResult] = []
        for item in request.segments:
            text = item.raw_text.strip()
            if text and text[-1] not in ".!?":
                text = f"{text}."
            if text:
                text = text[0].upper() + text[1:]
            corrected.append(
                CorrectionResult(
                    segment_id=item.segment_id,
                    corrected_text=text,
                    notes=["mock provider applied punctuation/capitalization"],
                )
            )
        return corrected


class OllamaLLMProvider(BaseLLMProvider):
    def __init__(self, settings: Settings) -> None:
        self._model = settings.llm_model_name
        self._endpoint = settings.llm_endpoint or "http://127.0.0.1:11434/api/generate"
        self._timeout = settings.llm_timeout_seconds

    async def correct(self, request: CorrectionRequest) -> list[CorrectionResult]:
        prompt = _build_prompt(request)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                self._endpoint,
                json={"model": self._model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
        payload = response.json()
        return _parse_json_results(payload.get("response", "[]"), request.segments)


class OpenAICompatibleLLMProvider(BaseLLMProvider):
    def __init__(self, settings: Settings) -> None:
        if not settings.llm_endpoint:
            raise ValueError("CMG_RT_LLM_ENDPOINT must be set for API-based LLM providers.")
        self._endpoint = settings.llm_endpoint.rstrip("/")
        self._api_key = settings.llm_api_key
        self._model = settings.llm_model_name
        self._timeout = settings.llm_timeout_seconds

    async def correct(self, request: CorrectionRequest) -> list[CorrectionResult]:
        prompt = _build_prompt(request)
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._endpoint}/chat/completions",
                headers=headers,
                json={
                    "model": self._model,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You repair transcripts. Preserve meaning, timestamps, and speaker structure. "
                                "Never invent content. Return strict JSON."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return _parse_json_results(content, request.segments)


class LLMPostProcessor:
    def __init__(self, provider: BaseLLMProvider, batch_size: int) -> None:
        self._provider = provider
        self._batch_size = batch_size

    async def apply(self, conversation_id: str, language: str | None, segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
        updated_segments = list(segments)
        for batch_start in range(0, len(updated_segments), self._batch_size):
            batch = updated_segments[batch_start : batch_start + self._batch_size]
            request = CorrectionRequest(
                conversation_id=conversation_id,
                language=language,
                segments=batch,
            )
            corrections = await self._provider.correct(request)
            correction_map = {item.segment_id: item for item in corrections}
            for index, segment in enumerate(batch, start=batch_start):
                correction = correction_map.get(segment.segment_id)
                if correction is None:
                    continue
                updated_segments[index] = segment.model_copy(
                    update={
                        "corrected_text": correction.corrected_text or segment.raw_text,
                        "speaker": correction.speaker_override or segment.speaker,
                        "notes": segment.notes + correction.notes,
                    }
                )
        return updated_segments


def build_llm_postprocessor(settings: Settings) -> LLMPostProcessor:
    if settings.llm_provider == "none":
        provider: BaseLLMProvider = NoOpLLMProvider()
    elif settings.llm_provider == "mock":
        provider = MockLLMProvider()
    elif settings.llm_provider == "ollama":
        provider = OllamaLLMProvider(settings)
    else:
        provider = OpenAICompatibleLLMProvider(settings)
    return LLMPostProcessor(provider=provider, batch_size=settings.llm_batch_size)


def _build_prompt(request: CorrectionRequest) -> str:
    payload = [
        {
            "segment_id": segment.segment_id,
            "speaker": segment.speaker,
            "start": segment.start,
            "end": segment.end,
            "raw_text": segment.raw_text,
        }
        for segment in request.segments
    ]
    return (
        "Correct the following diarized transcript segments for punctuation, capitalization, "
        "sentence continuity, local context consistency, and obvious ASR mistakes. Preserve meaning. "
        "Do not invent content. Keep timestamps and speaker structure unless correction is strongly justified.\n"
        "Return JSON with the shape {\"segments\": [{\"segment_id\": ..., \"corrected_text\": ..., "
        "\"speaker_override\": null, \"notes\": []}]}\n"
        f"{json.dumps({'language': request.language, 'segments': payload}, ensure_ascii=False)}"
    )


def _parse_json_results(content: str, source_segments: list[TranscriptSegment]) -> list[CorrectionResult]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        payload = {"segments": []}
    raw_segments: list[dict[str, Any]] = payload.get("segments", [])
    if not raw_segments:
        return [
            CorrectionResult(segment_id=item.segment_id, corrected_text=item.raw_text)
            for item in source_segments
        ]
    return [CorrectionResult.model_validate(item) for item in raw_segments]
