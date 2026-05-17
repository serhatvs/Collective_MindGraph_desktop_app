"""Speech-to-text providers."""

from __future__ import annotations

import importlib
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from ..config import Settings
from ..models import ASRSegment, SpeechRegion, WordTimestamp
from ..utils.audio import extract_wav_region
from ..utils.time import overlap_ratio
from ..utils.turkish_cleanup import GLOSSARY_TERMS

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
        quality_mode: str | None = None,
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
        quality_mode: str | None = None,
    ) -> list[ASRSegment]:
        if not regions:
            return self._transcribe_window(
                audio_path,
                language=language,
                offset_seconds=0.0,
                quality_mode=quality_mode,
            )

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
                        quality_mode=quality_mode,
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
        quality_mode: str | None = None,
    ) -> list[ASRSegment]:
        resolved_language = language or self._settings.default_language
        resolved_quality = quality_mode or self._settings.transcription_quality_mode

        # Quality mode parameter mapping
        beam_size = self._settings.asr_beam_size
        word_timestamps = True
        no_speech_threshold = 0.6

        if resolved_quality == "fast":
            beam_size = 1
            no_speech_threshold = 0.5
        elif resolved_quality == "accurate":
            beam_size = max(beam_size, 5)
            no_speech_threshold = 0.7

        # Turkish specific transcription enhancements
        initial_prompt = None
        if resolved_language == "tr":
            # Use combined glossary for initial prompt
            initial_prompt = ", ".join(GLOSSARY_TERMS[:50])

        segments, _info = self._model.transcribe(
            str(audio_path),
            language=resolved_language,
            beam_size=beam_size,
            word_timestamps=word_timestamps,
            vad_filter=False,
            condition_on_previous_text=False,
            task="transcribe",
            initial_prompt=initial_prompt,
            no_speech_threshold=no_speech_threshold,
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


def build_asr(settings: Settings) -> BaseASR:
    if settings.asr_provider == "mock":
        return MockASR()
    if settings.asr_provider == "auto":
        local = _build_optional_local_asr(settings)
        if local is not None:
            return local
        LOGGER.warning("Local ASR is unavailable. Falling back to MockASR.")
        return MockASR()
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


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
