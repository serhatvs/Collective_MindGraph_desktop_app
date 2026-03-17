"""Speech-to-text providers."""

from __future__ import annotations

import importlib
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx

from ..config import Settings
from ..models import ASRSegment, SpeechRegion, WordTimestamp
from ..utils.audio import extract_wav_region
from ..utils.time import overlap_ratio

LOGGER = logging.getLogger(__name__)


class BaseASR(ABC):
    provider_name: str = "base"
    fallback_provider_name: str | None = None

    @abstractmethod
    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
        regions: list[SpeechRegion] | None = None,
    ) -> list[ASRSegment]:
        raise NotImplementedError


class FasterWhisperASR(BaseASR):
    provider_name = "faster_whisper"

    def __init__(self, settings: Settings) -> None:
        try:
            faster_whisper_module = importlib.import_module("faster_whisper")
            whisper_model_cls = getattr(faster_whisper_module, "WhisperModel")
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("faster-whisper is not installed.") from exc

        self._model = whisper_model_cls(
            settings.asr_model_name,
            device=settings.asr_device,
            compute_type=settings.asr_compute_type,
        )
        self._settings = settings

    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
        regions: list[SpeechRegion] | None = None,
    ) -> list[ASRSegment]:
        if not regions:
            return self._transcribe_window(audio_path, language=language, offset_seconds=0.0)

        items: list[ASRSegment] = []
        for region in _regions_for_asr(
            regions,
            padding_seconds=self._settings.asr_region_padding_seconds,
        ):
            region_path = _extract_wav_region(
                source_path=audio_path,
                start_seconds=region.start,
                end_seconds=region.end,
                target_dir=self._settings.temp_dir,
            )
            try:
                items.extend(
                    self._transcribe_window(
                        region_path,
                        language=language,
                        offset_seconds=region.start,
                    )
                )
            finally:
                region_path.unlink(missing_ok=True)
        return _dedupe_segments(items)

    def _transcribe_window(
        self,
        audio_path: Path,
        *,
        language: str | None,
        offset_seconds: float,
    ) -> list[ASRSegment]:
        segments, _info = self._model.transcribe(
            str(audio_path),
            language=language or self._settings.default_language,
            beam_size=self._settings.asr_beam_size,
            word_timestamps=True,
            vad_filter=False,
            condition_on_previous_text=False,
            task="transcribe",
        )
        items: list[ASRSegment] = []
        for segment in segments:
            words = [
                WordTimestamp(
                    start=_offset_value(getattr(word, "start", None), offset_seconds),
                    end=_offset_value(getattr(word, "end", None), offset_seconds),
                    word=word.word,
                    probability=getattr(word, "probability", None),
                )
                for word in (segment.words or [])
            ]
            item = ASRSegment(
                start=float(segment.start) + offset_seconds,
                end=float(segment.end) + offset_seconds,
                text=segment.text.strip(),
                confidence=_average_probability(words),
                words=words,
            )
            if item.text:
                items.append(item)
        return items


class MockASR(BaseASR):
    provider_name = "mock"

    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
        regions: list[SpeechRegion] | None = None,
    ) -> list[ASRSegment]:
        if regions:
            segments: list[ASRSegment] = []
            for index, region in enumerate(regions, start=1):
                segments.append(
                    ASRSegment(
                        start=region.start,
                        end=region.end,
                        text=f"Mock transcription {index} generated from {audio_path.name}.",
                        confidence=0.8,
                    )
                )
            return segments
        return [
            ASRSegment(
                start=0.0,
                end=2.5,
                text=f"Mock transcription generated from {audio_path.name}.",
                confidence=0.8,
            )
        ]


class DeepgramASR(BaseASR):
    provider_name = "deepgram"

    def __init__(self, settings: Settings) -> None:
        if not settings.deepgram_api_key:
            raise RuntimeError("CMG_RT_DEEPGRAM_API_KEY is required for Deepgram ASR.")
        self._settings = settings

    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
        regions: list[SpeechRegion] | None = None,
    ) -> list[ASRSegment]:
        if not regions:
            return self._transcribe_window(audio_path, language=language, offset_seconds=0.0)

        items: list[ASRSegment] = []
        for region in _regions_for_asr(
            regions,
            padding_seconds=self._settings.asr_region_padding_seconds,
        ):
            region_path = _extract_wav_region(
                source_path=audio_path,
                start_seconds=region.start,
                end_seconds=region.end,
                target_dir=self._settings.temp_dir,
            )
            try:
                items.extend(
                    self._transcribe_window(
                        region_path,
                        language=language,
                        offset_seconds=region.start,
                    )
                )
            finally:
                region_path.unlink(missing_ok=True)
        return _dedupe_segments(items)

    def _transcribe_window(
        self,
        audio_path: Path,
        *,
        language: str | None,
        offset_seconds: float,
    ) -> list[ASRSegment]:
        with audio_path.open("rb") as handle:
            response = httpx.post(
                self._settings.deepgram_endpoint,
                params=_deepgram_request_params(self._settings, language),
                headers={
                    "Authorization": f"Token {self._settings.deepgram_api_key}",
                    "Content-Type": "audio/wav",
                },
                content=handle.read(),
                timeout=self._settings.deepgram_timeout_seconds,
            )
        response.raise_for_status()
        payload = response.json()
        return _deepgram_segments_from_payload(payload, offset_seconds=offset_seconds)


class FallbackASR(BaseASR):
    def __init__(self, primary: BaseASR, fallback: BaseASR) -> None:
        self._primary = primary
        self._fallback = fallback
        self.provider_name = getattr(primary, "provider_name", primary.__class__.__name__.lower())
        self.fallback_provider_name = getattr(fallback, "provider_name", fallback.__class__.__name__.lower())

    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
        regions: list[SpeechRegion] | None = None,
    ) -> list[ASRSegment]:
        try:
            return self._primary.transcribe(audio_path, language=language, regions=regions)
        except Exception as exc:
            LOGGER.warning("Primary ASR provider failed, falling back locally: %s", exc)
            return self._fallback.transcribe(audio_path, language=language, regions=regions)


def build_asr(settings: Settings) -> BaseASR:
    if settings.asr_provider == "mock":
        return MockASR()
    if settings.asr_provider == "deepgram":
        return DeepgramASR(settings)
    if settings.asr_provider == "auto":
        local = _build_optional_local_asr(settings)
        if not settings.deepgram_api_key:
            if local is not None:
                return local
            LOGGER.warning("Local ASR is unavailable and no Deepgram key is configured. Falling back to MockASR.")
            return MockASR()
        if local is None:
            LOGGER.warning("Local ASR fallback is unavailable. Using Deepgram without local fallback.")
            return DeepgramASR(settings)
        return FallbackASR(DeepgramASR(settings), local)
    return FasterWhisperASR(settings)


def _build_optional_local_asr(settings: Settings) -> BaseASR | None:
    try:
        return FasterWhisperASR(settings)
    except Exception as exc:
        LOGGER.warning("Local faster-whisper ASR is unavailable: %s", exc)
        return None


def _regions_for_asr(regions: list[SpeechRegion], padding_seconds: float) -> list[SpeechRegion]:
    windows: list[SpeechRegion] = []
    for region in sorted(regions, key=lambda item: item.start):
        padded = SpeechRegion(
            start=max(0.0, region.start - padding_seconds),
            end=region.end + padding_seconds,
            confidence=region.confidence,
        )
        if not windows:
            windows.append(padded)
            continue
        previous = windows[-1]
        if padded.start <= previous.end:
            windows[-1] = SpeechRegion(
                start=previous.start,
                end=max(previous.end, padded.end),
                confidence=previous.confidence or padded.confidence,
            )
            continue
        windows.append(padded)
    return windows


def _extract_wav_region(
    source_path: Path,
    start_seconds: float,
    end_seconds: float,
    target_dir: Path,
) -> Path:
    return extract_wav_region(source_path, start_seconds, end_seconds, target_dir)


def _dedupe_segments(segments: list[ASRSegment]) -> list[ASRSegment]:
    ordered = sorted(segments, key=lambda item: (item.start, item.end, item.text))
    unique: list[ASRSegment] = []
    for segment in ordered:
        if unique and _segments_look_duplicate(unique[-1], segment):
            continue
        unique.append(segment)
    return unique


def _segments_look_duplicate(left: ASRSegment, right: ASRSegment) -> bool:
    return (
        overlap_ratio(left.start, left.end, right.start, right.end) >= 0.85
        and left.text.strip().lower() == right.text.strip().lower()
    )


def _offset_value(value: float | None, offset_seconds: float) -> float | None:
    if value is None:
        return None
    return float(value) + offset_seconds


def _average_probability(words: list[WordTimestamp]) -> float | None:
    probabilities = [item.probability for item in words if item.probability is not None]
    if not probabilities:
        return None
    return float(sum(probabilities) / len(probabilities))


def _deepgram_request_params(settings: Settings, language: str | None) -> dict[str, str]:
    params = {
        "model": settings.deepgram_model_name,
        "smart_format": str(settings.deepgram_smart_format).lower(),
        "punctuate": str(settings.deepgram_punctuate).lower(),
        "utterances": str(settings.deepgram_utterances).lower(),
    }
    resolved_language = language or settings.default_language
    if resolved_language:
        params["language"] = resolved_language
    elif settings.deepgram_detect_language:
        params["detect_language"] = "true"
    return params


def _deepgram_segments_from_payload(payload: dict[str, Any], *, offset_seconds: float) -> list[ASRSegment]:
    results = payload.get("results") or {}
    utterances = results.get("utterances") or []
    if utterances:
        return _deepgram_segments_from_utterances(utterances, offset_seconds=offset_seconds)
    return _deepgram_segments_from_channels(results.get("channels") or [], offset_seconds=offset_seconds)


def _deepgram_segments_from_utterances(
    utterances: list[dict[str, Any]],
    *,
    offset_seconds: float,
) -> list[ASRSegment]:
    segments: list[ASRSegment] = []
    for utterance in utterances:
        text = str(utterance.get("transcript") or "").strip()
        if not text:
            continue
        words = _deepgram_words_to_timestamps(utterance.get("words") or [], offset_seconds=offset_seconds)
        segments.append(
            ASRSegment(
                start=float(utterance.get("start", 0.0)) + offset_seconds,
                end=float(utterance.get("end", 0.0)) + offset_seconds,
                text=text,
                confidence=_safe_float(utterance.get("confidence")) or _average_probability(words),
                words=words,
            )
        )
    return segments


def _deepgram_segments_from_channels(
    channels: list[dict[str, Any]],
    *,
    offset_seconds: float,
) -> list[ASRSegment]:
    segments: list[ASRSegment] = []
    for channel in channels:
        alternatives = channel.get("alternatives") or []
        if not alternatives:
            continue
        alternative = alternatives[0]
        text = str(alternative.get("transcript") or "").strip()
        if not text:
            continue
        words = _deepgram_words_to_timestamps(alternative.get("words") or [], offset_seconds=offset_seconds)
        start = words[0].start if words and words[0].start is not None else offset_seconds
        end = words[-1].end if words and words[-1].end is not None else offset_seconds
        segments.append(
            ASRSegment(
                start=float(start),
                end=float(end),
                text=text,
                confidence=_safe_float(alternative.get("confidence")) or _average_probability(words),
                words=words,
            )
        )
    return segments


def _deepgram_words_to_timestamps(
    items: list[dict[str, Any]],
    *,
    offset_seconds: float,
) -> list[WordTimestamp]:
    timestamps: list[WordTimestamp] = []
    for item in items:
        word = str(item.get("punctuated_word") or item.get("word") or "").strip()
        if not word:
            continue
        timestamps.append(
            WordTimestamp(
                start=_offset_value(_safe_float(item.get("start")), offset_seconds),
                end=_offset_value(_safe_float(item.get("end")), offset_seconds),
                word=word,
                probability=_safe_float(item.get("confidence")),
            )
        )
    return timestamps


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
