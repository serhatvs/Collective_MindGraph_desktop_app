"""Speech-to-text providers."""

from __future__ import annotations

import importlib
import inspect
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from collective_mindgraph.application.ports import TranscriptionConfiguration
from collective_mindgraph.application.transcription.contracts import (
    ASRSegment,
    SpeechRegion,
    WordTimestamp,
)
from collective_mindgraph.application.transcription.transcription_glossary import (
    ResolvedGlossary,
    resolve_transcription_glossary,
)

from .asr_quality_profiles import ASRQualityProfile, resolve_asr_quality_profile
from .asr_runtime_config import add_cuda_dll_directories
from .asr_segment_processing import average_probability as _average_probability
from .asr_segment_processing import dedupe_segments as _dedupe_segments
from .asr_segment_processing import estimate_segment_confidence as _estimate_segment_confidence
from .asr_segment_processing import extract_region as _extract_wav_region
from .asr_segment_processing import offset_value as _offset_value
from .asr_segment_processing import regions_for_asr as _regions_for_asr
from .asr_segment_processing import safe_float as _safe_float

LOGGER = logging.getLogger(__name__)

ASR_STATUS_OK = "ASR_STATUS=OK"
ASR_STATUS_MOCK_EXPLICIT = "ASR_STATUS=MOCK_EXPLICIT"
ASR_STATUS_MOCK_FALLBACK = "ASR_STATUS=MOCK_FALLBACK"


class BaseASR(ABC):
    provider_name: str = "base"
    fallback_provider_name: str | None = None
    asr_status: str = ASR_STATUS_OK
    mock_fallback_used: bool = False
    fallback_reason: str | None = None

    @abstractmethod
    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
        regions: list[SpeechRegion] | None = None,
        quality_mode: str | None = None,
        glossary: ResolvedGlossary | None = None,
    ) -> list[ASRSegment]:
        raise NotImplementedError


def transcribe_with_glossary_compatibility(
    provider: BaseASR,
    audio_path: Path,
    language: str | None,
    regions: list[SpeechRegion] | None,
    quality_mode: str,
    glossary: ResolvedGlossary,
) -> list[ASRSegment]:
    """Call an ASR provider while retaining support for pre-glossary providers."""

    try:
        return provider.transcribe(
            audio_path,
            language,
            regions,
            quality_mode,
            glossary=glossary,
        )
    except TypeError as exc:
        if "glossary" not in str(exc):
            raise
        return provider.transcribe(audio_path, language, regions, quality_mode)


def offset_asr_segments(
    items: list[ASRSegment],
    offset_seconds: float,
    *,
    deep: bool = False,
) -> list[ASRSegment]:
    """Return ASR segments shifted on the timeline."""

    if not offset_seconds:
        return list(items)
    return [
        item.model_copy(
            update={
                "start": item.start + offset_seconds,
                "end": item.end + offset_seconds,
                "words": [
                    word.model_copy(
                        update={
                            "start": (word.start + offset_seconds)
                            if word.start is not None
                            else None,
                            "end": (word.end + offset_seconds) if word.end is not None else None,
                        }
                    )
                    for word in item.words
                ],
            },
            deep=deep,
        )
        for item in items
    ]


class FasterWhisperASR(BaseASR):
    provider_name = "faster_whisper"

    def __init__(
        self,
        settings: TranscriptionConfiguration,
        *,
        requested_device: str | None = None,
        gpu_fallback_reason: str | None = None,
    ) -> None:
        cuda_dll_directories = add_cuda_dll_directories()
        try:
            faster_whisper_module = importlib.import_module("faster_whisper")
            whisper_model_cls = getattr(faster_whisper_module, "WhisperModel")
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("faster-whisper is not installed.") from exc

        self._whisper_model_cls = whisper_model_cls
        self._settings = settings
        self._model_cache: dict[tuple[str, str, str], Any] = {}
        self._model = self._load_model(
            settings.asr_model_name, settings.asr_device, settings.asr_compute_type
        )
        self.requested_device = requested_device or settings.asr_device
        self.gpu_requested = _is_cuda_device(self.requested_device)
        self.gpu_loaded = _is_cuda_device(settings.asr_device)
        self.gpu_fallback_happened = bool(gpu_fallback_reason)
        self.gpu_fallback_reason = gpu_fallback_reason
        self.cuda_load_status = _cuda_load_status(
            requested_device=self.requested_device,
            loaded_device=settings.asr_device,
            fallback_reason=gpu_fallback_reason,
        )
        self.cuda_dll_directories = cuda_dll_directories

    def _load_model(self, model_name: str, device: str, compute_type: str):
        key = (model_name, device, compute_type)
        cached = self._model_cache.get(key)
        if cached is not None:
            return cached
        model = self._whisper_model_cls(
            model_name,
            device=device,
            compute_type=compute_type,
            local_files_only=not self._settings.allow_remote_download,
        )
        self._model_cache[key] = model
        return model

    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
        regions: list[SpeechRegion] | None = None,
        quality_mode: str | None = None,
        glossary: ResolvedGlossary | None = None,
    ) -> list[ASRSegment]:
        if not regions:
            return self._transcribe_window(
                audio_path,
                language=language,
                offset_seconds=0.0,
                quality_mode=quality_mode,
                glossary=glossary,
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
                        glossary=glossary,
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
        glossary: ResolvedGlossary | None = None,
    ) -> list[ASRSegment]:
        resolved_language = language or self._settings.default_language
        profile = resolve_asr_quality_profile(self._settings, quality_mode)

        resolved_glossary = glossary or resolve_transcription_glossary(self._settings)
        initial_prompt = resolved_glossary.initial_prompt if resolved_language == "tr" else None
        model = self._load_model(
            profile.model_name, self._settings.asr_device, profile.compute_type
        )
        hotwords_supported = bool(
            resolved_language == "tr"
            and resolved_glossary.hotwords
            and _supports_transcribe_argument(model, "hotwords")
        )

        segments, _info, call_metadata = _call_faster_whisper_transcribe(
            model,
            audio_path=audio_path,
            language=resolved_language,
            profile=profile,
            initial_prompt=initial_prompt,
            hotwords=resolved_glossary.hotwords if hotwords_supported else None,
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
            text = segment.text.strip()
            avg_logprob = _safe_float(getattr(segment, "avg_logprob", None))
            no_speech_prob = _safe_float(getattr(segment, "no_speech_prob", None))
            compression_ratio = _safe_float(getattr(segment, "compression_ratio", None))
            word_confidence = _average_probability(words)
            confidence = _estimate_segment_confidence(
                word_confidence=word_confidence,
                avg_logprob=avg_logprob,
                no_speech_prob=no_speech_prob,
                compression_ratio=compression_ratio,
            )
            segment_temperature = _safe_float(getattr(segment, "temperature", None))
            item = ASRSegment(
                start=float(segment.start) + offset_seconds,
                end=float(segment.end) + offset_seconds,
                text=text,
                confidence=confidence,
                words=words,
                avg_logprob=avg_logprob,
                no_speech_prob=no_speech_prob,
                compression_ratio=compression_ratio,
                text_length=len(text),
                metadata={
                    "avg_logprob": avg_logprob,
                    "no_speech_prob": no_speech_prob,
                    "compression_ratio": compression_ratio,
                    "text_length": len(text),
                    "word_confidence": word_confidence,
                    "segment_confidence_estimate": confidence,
                    "temperature": segment_temperature,
                    "temperature_fallback": list(profile.temperature),
                    "quality_profile": profile.name,
                    "model_name": profile.model_name,
                    "compute_type": profile.compute_type,
                    "glossary_prompt_term_count": len(resolved_glossary.terms),
                    "hotwords_supported": hotwords_supported,
                    "hotwords_applied": bool(call_metadata.get("hotwords_applied")),
                },
            )
            if item.text:
                items.append(item)
        return items


class MockASR(BaseASR):
    provider_name = "mock"

    def __init__(
        self,
        *,
        asr_status: str = ASR_STATUS_MOCK_EXPLICIT,
        fallback_reason: str | None = None,
    ) -> None:
        self.asr_status = asr_status
        self.mock_fallback_used = asr_status == ASR_STATUS_MOCK_FALLBACK
        self.fallback_provider_name = "mock" if self.mock_fallback_used else None
        self.fallback_reason = fallback_reason

    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
        regions: list[SpeechRegion] | None = None,
        quality_mode: str | None = None,
        glossary: ResolvedGlossary | None = None,
    ) -> list[ASRSegment]:
        warning_text = (
            f"[{self.asr_status}] Mock ASR placeholder; no real transcription was produced."
        )
        if regions:
            segments: list[ASRSegment] = []
            for index, region in enumerate(regions, start=1):
                segments.append(
                    ASRSegment(
                        start=region.start,
                        end=region.end,
                        text=f"{warning_text} Region {index} from {audio_path.name}.",
                        confidence=0.0,
                    )
                )
            return segments
        return [
            ASRSegment(
                start=0.0,
                end=2.5,
                text=f"{warning_text} Source file: {audio_path.name}.",
                confidence=0.0,
            )
        ]


def _call_faster_whisper_transcribe(
    model: Any,
    *,
    audio_path: Path,
    language: str | None,
    profile: ASRQualityProfile,
    initial_prompt: str | None,
    hotwords: str | None = None,
):
    kwargs = {
        "language": language,
        "beam_size": profile.beam_size,
        "word_timestamps": profile.word_timestamps,
        "vad_filter": profile.vad_filter,
        "condition_on_previous_text": profile.condition_on_previous_text,
        "task": "transcribe",
        "initial_prompt": initial_prompt,
        "no_speech_threshold": profile.no_speech_threshold,
        "temperature": profile.temperature,
    }
    if hotwords:
        kwargs["hotwords"] = hotwords
    removed_options: list[str] = []
    for _attempt in range(3):
        try:
            segments, info = model.transcribe(str(audio_path), **kwargs)
            return (
                segments,
                info,
                {
                    "hotwords_applied": bool(kwargs.get("hotwords")),
                    "removed_unsupported_options": removed_options,
                },
            )
        except TypeError as exc:
            message = str(exc)
            if "hotwords" in kwargs and ("hotwords" in message or "unexpected keyword" in message):
                LOGGER.warning("Faster-Whisper runtime rejected hotwords; retrying without them.")
                kwargs.pop("hotwords", None)
                removed_options.append("hotwords")
                continue
            if "temperature" in kwargs and (
                "temperature" in message or "unexpected keyword" in message
            ):
                LOGGER.warning(
                    "Faster-Whisper runtime rejected temperature fallback settings; retrying without them."
                )
                kwargs.pop("temperature", None)
                removed_options.append("temperature")
                continue
            raise
    raise RuntimeError("Faster-Whisper transcription retry limit reached.")


def _supports_transcribe_argument(model: Any, argument: str) -> bool:
    try:
        signature = inspect.signature(model.transcribe)
    except (TypeError, ValueError):
        return False
    if argument in signature.parameters:
        return True
    return any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )


def build_asr(settings: TranscriptionConfiguration) -> BaseASR:
    provider = settings.asr_provider.strip().lower()
    if provider == "mock":
        return MockASR(asr_status=ASR_STATUS_MOCK_EXPLICIT)
    if provider == "auto":
        local, error = _build_optional_local_asr(settings)
        if local is not None:
            return local
        if _gpu_required(settings):
            reason = str(error) if error is not None else "unknown local ASR error"
            raise RuntimeError(
                f"CMG_REQUIRE_GPU=1 but CUDA ASR could not load: {reason}"
            ) from error
        reason = str(error) if error is not None else "unknown local ASR error"
        LOGGER.warning(
            "%s: Local ASR is unavailable. Falling back to MockASR. reason=%s",
            ASR_STATUS_MOCK_FALLBACK,
            reason,
        )
        return MockASR(asr_status=ASR_STATUS_MOCK_FALLBACK, fallback_reason=reason)
    local, error = _build_optional_local_asr(settings)
    if local is not None:
        return local
    reason = str(error) if error is not None else "unknown local ASR error"
    if _gpu_required(settings):
        raise RuntimeError(f"CMG_REQUIRE_GPU=1 but CUDA ASR could not load: {reason}") from error
    raise RuntimeError(f"faster-whisper ASR could not load: {reason}") from error


def _build_optional_local_asr(
    settings: TranscriptionConfiguration,
) -> tuple[BaseASR | None, Exception | None]:
    try:
        return FasterWhisperASR(settings), None
    except Exception as exc:
        if _should_retry_cpu(settings):
            requested_device = settings.asr_device
            requested_compute_type = settings.asr_compute_type
            fallback_reason = (
                f"CUDA ASR load failed for {requested_device}/{requested_compute_type}: "
                f"{type(exc).__name__}: {exc}"
            )
            LOGGER.warning(
                "%s Falling back to CPU/int8 because CMG_REQUIRE_GPU is not set.", fallback_reason
            )
            settings.asr_device = "cpu"
            settings.asr_compute_type = "int8"
            try:
                return (
                    FasterWhisperASR(
                        settings,
                        requested_device=requested_device,
                        gpu_fallback_reason=fallback_reason,
                    ),
                    None,
                )
            except Exception as fallback_exc:
                settings.asr_device = requested_device
                settings.asr_compute_type = requested_compute_type
                LOGGER.warning("CPU fallback for faster-whisper ASR also failed: %s", fallback_exc)
                return None, fallback_exc
        LOGGER.warning("Local faster-whisper ASR is unavailable: %s", exc)
        return None, exc


def _gpu_required(settings: TranscriptionConfiguration) -> bool:
    return bool(getattr(settings, "gpu_required", False))


def _should_retry_cpu(settings: TranscriptionConfiguration) -> bool:
    return _is_cuda_device(settings.asr_device) and not _gpu_required(settings)


def _is_cuda_device(device: str | None) -> bool:
    return (device or "").strip().lower().startswith("cuda")


def _cuda_load_status(
    *, requested_device: str | None, loaded_device: str | None, fallback_reason: str | None
) -> str:
    if not _is_cuda_device(requested_device):
        return "not_requested"
    if fallback_reason:
        return "fallback_to_cpu"
    if _is_cuda_device(loaded_device):
        return "loaded_on_cuda"
    return "requested_but_not_loaded"
