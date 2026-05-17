"""LLM post-processing for readability and context consistency."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from ..config import Settings
from ..models import CorrectionRequest, CorrectionResult, TranscriptSegment
from ..utils.offline_safety import validate_local_endpoint

LOGGER = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    provider_name: str = "base"
    fallback_provider_name: str | None = None

    @abstractmethod
    async def correct(self, request: CorrectionRequest) -> list[CorrectionResult]:
        raise NotImplementedError


class NoOpLLMProvider(BaseLLMProvider):
    provider_name = "none"

    async def correct(self, request: CorrectionRequest) -> list[CorrectionResult]:
        return [
            CorrectionResult(segment_id=item.segment_id, corrected_text=item.raw_text)
            for item in request.segments
        ]


class MockLLMProvider(BaseLLMProvider):
    provider_name = "mock"

    async def correct(self, request: CorrectionRequest) -> list[CorrectionResult]:
        corrected: list[CorrectionResult] = []
        for item in request.segments:
            text = _local_cleanup(item.raw_text)
            corrected.append(
                CorrectionResult(
                    segment_id=item.segment_id,
                    corrected_text=text,
                    notes=["mock provider applied punctuation/capitalization"],
                )
            )
        return corrected


class OllamaLLMProvider(BaseLLMProvider):
    provider_name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self._model = settings.llm_model_name
        self._endpoint = settings.llm_endpoint or "http://127.0.0.1:11434/api/generate"
        self._timeout = settings.llm_timeout_seconds
        validate_local_endpoint(self._endpoint, "Ollama", settings.allow_remote_access)

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
    provider_name = "openai_compatible"

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_endpoint:
            raise ValueError("CMG_RT_LLM_ENDPOINT must be set for API-based LLM providers.")
        self._endpoint = settings.llm_endpoint.rstrip("/")
        self._api_key = settings.llm_api_key
        self._model = settings.llm_model_name
        self._timeout = settings.llm_timeout_seconds
        validate_local_endpoint(self._endpoint, "OpenAI-compatible", settings.allow_remote_access)

    async def _resolve_model(self) -> str:
        if self._model and self._model != "auto":
            return self._model

        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._endpoint}/models", headers=headers)
            response.raise_for_status()
        payload = response.json()
        data = payload.get("data", [])
        if not isinstance(data, list) or not data:
            raise ValueError("No LLM models are available at the configured endpoint.")
        first = data[0]
        if not isinstance(first, dict) or not first.get("id"):
            raise ValueError("Configured LLM endpoint returned models without ids.")
        self._model = str(first["id"])
        return self._model

    async def correct(self, request: CorrectionRequest) -> list[CorrectionResult]:
        prompt = _build_prompt(request)
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        model_name = await self._resolve_model()

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._endpoint}/chat/completions",
                headers=headers,
                json={
                    "model": model_name,
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
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


class LMStudioLLMProvider(OpenAICompatibleLLMProvider):
    provider_name = "lmstudio"

    def __init__(self, settings: Settings) -> None:
        self._model = settings.llm_model_name
        self._endpoint = (settings.llm_endpoint or "http://127.0.0.1:1234/v1").rstrip("/")
        self._api_key = settings.llm_api_key
        self._timeout = settings.llm_timeout_seconds
        validate_local_endpoint(self._endpoint, "LM Studio", settings.allow_remote_access)


class AutoLocalLLMProvider(BaseLLMProvider):
    provider_name = "lmstudio"
    fallback_provider_name = "mock"

    def __init__(self, settings: Settings) -> None:
        self._remote_provider = LMStudioLLMProvider(settings)
        self._fallback_provider = MockLLMProvider()
        self._remote_available: bool | None = None

    async def correct(self, request: CorrectionRequest) -> list[CorrectionResult]:
        if self._remote_available is False:
            return await self._fallback_provider.correct(request)
        try:
            corrected = await self._remote_provider.correct(request)
        except (httpx.HTTPError, ValueError):
            self._remote_available = False
            return await self._fallback_provider.correct(request)
        self._remote_available = True
        return corrected


class LLMPostProcessor:
    def __init__(self, provider: BaseLLMProvider, batch_size: int, context_segments: int = 0) -> None:
        self._provider = provider
        self._batch_size = batch_size
        self._context_segments = max(0, context_segments)

    async def apply(self, conversation_id: str, language: str | None, segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
        updated_segments = list(segments)
        for batch_start in range(0, len(updated_segments), self._batch_size):
            batch = updated_segments[batch_start : batch_start + self._batch_size]
            context = updated_segments[max(0, batch_start - self._context_segments) : batch_start]
            request = CorrectionRequest(
                conversation_id=conversation_id,
                language=language,
                context_segments=context,
                segments=batch,
            )
            try:
                corrections = await self._provider.correct(request)
            except Exception as exc:
                corrections = [
                    CorrectionResult(
                        segment_id=item.segment_id,
                        corrected_text=item.raw_text,
                        notes=[f"llm provider failed: {type(exc).__name__}"],
                    )
                    for item in batch
                ]
            correction_map = {item.segment_id: item for item in corrections}
            for index, segment in enumerate(batch, start=batch_start):
                correction = correction_map.get(segment.segment_id)
                if correction is None:
                    continue
                notes = list(segment.notes)
                notes.extend(correction.notes)
                if correction.confidence_note:
                    notes.append(f"llm confidence note: {correction.confidence_note}")
                updated_segments[index] = segment.model_copy(
                    update={
                        "corrected_text": _normalize_correction(
                            original=segment.raw_text,
                            corrected=correction.corrected_text,
                        ),
                        "speaker": correction.speaker_override or segment.speaker,
                        "notes": _dedupe_notes(notes),
                    }
                )
        return updated_segments


def build_llm_postprocessor(settings: Settings) -> LLMPostProcessor:
    if settings.llm_provider == "none":
        provider: BaseLLMProvider = NoOpLLMProvider()
    elif settings.llm_provider == "auto_local":
        provider = AutoLocalLLMProvider(settings)
    elif settings.llm_provider == "mock":
        provider = MockLLMProvider()
    elif settings.llm_provider == "ollama":
        provider = OllamaLLMProvider(settings)
    elif settings.llm_provider == "lmstudio":
        provider = LMStudioLLMProvider(settings)
    elif settings.llm_provider == "openai_compatible":
        provider = OpenAICompatibleLLMProvider(settings)
    else:
        # Default to local/offline-safe lmstudio
        provider = LMStudioLLMProvider(settings)
    return LLMPostProcessor(
        provider=provider,
        batch_size=settings.llm_batch_size,
        context_segments=settings.llm_context_segments,
    )


def _build_prompt(request: CorrectionRequest) -> str:
    context_payload = [
        {
            "speaker": segment.speaker,
            "start": segment.start,
            "end": segment.end,
            "text": segment.corrected_text or segment.raw_text,
        }
        for segment in request.context_segments
    ]
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

    language_note = ""
    if request.language == "tr":
        language_note = (
            "The transcript is in Turkish (tr). Use Turkish grammar and preserve Turkish characters (ç, ğ, ı, İ, ö, ş, ü). "
            "Do not translate to English. "
        )
    elif request.language:
        language_note = f"The transcript is in {request.language}. "

    return (
        "Correct the following diarized transcript segments for punctuation, capitalization, "
        "sentence continuity, local context consistency, and obvious ASR mistakes. "
        "Remove repeated filler words, false starts, or noise where safe. Preserve meaning. "
        "Do not invent content. Keep timestamps and speaker structure unless correction is strongly justified.\n"
        f"{language_note}"
        "Use the context block only to preserve continuity; do not rewrite context.\n"
        "Return JSON with the shape {\"segments\": [{\"segment_id\": ..., \"corrected_text\": ..., "
        "\"speaker_override\": null, \"notes\": [], \"confidence_note\": null}]}\n"
        f"{json.dumps({'language': request.language, 'context': context_payload, 'segments': payload}, ensure_ascii=False)}"
    )


def _parse_json_results(content: str, source_segments: list[TranscriptSegment]) -> list[CorrectionResult]:
    content = _strip_code_fence(content)
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        try:
            payload = {"segments": json.loads(content)}
        except json.JSONDecodeError:
            payload = {"segments": []}
    if isinstance(payload, list):
        payload = {"segments": payload}
    raw_segments: list[dict[str, Any]] = payload.get("segments", [])
    if not raw_segments:
        return [
            CorrectionResult(segment_id=item.segment_id, corrected_text=item.raw_text)
            for item in source_segments
        ]
    valid_ids = {item.segment_id for item in source_segments}
    return [
        CorrectionResult.model_validate(item)
        for item in raw_segments
        if item.get("segment_id") in valid_ids
    ]


def _strip_code_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:]
    return stripped.strip()


def _local_cleanup(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    cleaned = cleaned.replace(" i ", " I ")
    if cleaned.startswith("i "):
        cleaned = "I " + cleaned[2:]
    if cleaned and cleaned[-1] not in ".!?":
        cleaned = f"{cleaned}."
    if cleaned:
        cleaned = cleaned[:1].upper() + cleaned[1:]
    return cleaned


def _normalize_correction(original: str, corrected: str | None) -> str:
    candidate = (corrected or original or "").strip()
    if not candidate:
        return original
    return candidate


def _dedupe_notes(notes: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for note in notes:
        if note in seen:
            continue
        seen.add(note)
        ordered.append(note)
    return ordered
