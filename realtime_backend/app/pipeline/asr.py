"""Speech-to-text providers."""

from __future__ import annotations

import importlib
import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import Settings
from ..models import ASRSegment, SpeechRegion, WordTimestamp
from ..utils.audio import extract_wav_region
from ..utils.time import overlap_ratio
from ..utils.turkish_cleanup import GLOSSARY_TERMS
from .asr_runtime_config import add_cuda_dll_directories

LOGGER = logging.getLogger(__name__)

ASR_STATUS_OK = "ASR_STATUS=OK"
ASR_STATUS_MOCK_EXPLICIT = "ASR_STATUS=MOCK_EXPLICIT"
ASR_STATUS_MOCK_FALLBACK = "ASR_STATUS=MOCK_FALLBACK"


@dataclass(frozen=True, slots=True)
class ASRQualityProfile:
    name: str
    model_name: str
    compute_type: str
    beam_size: int
    word_timestamps: bool
    vad_filter: bool
    condition_on_previous_text: bool
    no_speech_threshold: float
    temperature: tuple[float, ...]
    preprocessing_strength: str


def resolve_asr_quality_profile(settings: Settings, quality_mode: str | None = None) -> ASRQualityProfile:
    requested = (quality_mode or settings.transcription_quality_mode or "max_quality").strip().lower()
    if requested == "accurate":
        requested = "max_quality"
    if requested not in {"fast", "balanced", "max_quality", "bad_mic_recovery"}:
        LOGGER.warning("Unknown ASR quality profile %r; using max_quality.", requested)
        requested = "max_quality"

    base_model = settings.asr_model_name
    base_compute_type = settings.asr_compute_type
    word_timestamps = bool(settings.asr_word_timestamps)
    vad_filter = bool(settings.asr_internal_vad_enabled)
    condition_on_previous_text = bool(settings.asr_condition_on_previous_text)

    if requested == "fast":
        return ASRQualityProfile(
            name="fast",
            model_name=_profile_value(settings.asr_fast_model_name, base_model),
            compute_type=_profile_value(settings.asr_fast_compute_type, base_compute_type),
            beam_size=1,
            word_timestamps=False if settings.asr_word_timestamps else word_timestamps,
            vad_filter=False,
            condition_on_previous_text=False,
            no_speech_threshold=0.5,
            temperature=(0.0,),
            preprocessing_strength="format_only",
        )
    if requested == "balanced":
        return ASRQualityProfile(
            name="balanced",
            model_name=_profile_value(settings.asr_balanced_model_name, base_model),
            compute_type=_profile_value(settings.asr_balanced_compute_type, base_compute_type),
            beam_size=max(3, settings.asr_beam_size),
            word_timestamps=word_timestamps,
            vad_filter=vad_filter,
            condition_on_previous_text=condition_on_previous_text,
            no_speech_threshold=0.6,
            temperature=(0.0, 0.2),
            preprocessing_strength="safe_loudness",
        )
    if requested == "bad_mic_recovery":
        return ASRQualityProfile(
            name="bad_mic_recovery",
            model_name=_profile_value(settings.asr_bad_mic_model_name, base_model),
            compute_type=_profile_value(settings.asr_bad_mic_compute_type, base_compute_type),
            beam_size=max(5, settings.asr_max_quality_beam_size, settings.asr_beam_size),
            word_timestamps=word_timestamps,
            vad_filter=False,
            condition_on_previous_text=False,
            no_speech_threshold=0.85,
            temperature=(0.0, 0.2, 0.4, 0.6),
            preprocessing_strength="bad_mic_recovery",
        )
    return ASRQualityProfile(
        name="max_quality",
        model_name=_profile_value(settings.asr_max_quality_model_name, base_model),
        compute_type=_profile_value(settings.asr_max_quality_compute_type, base_compute_type),
        beam_size=max(5, settings.asr_max_quality_beam_size, settings.asr_beam_size),
        word_timestamps=word_timestamps,
        vad_filter=vad_filter,
        condition_on_previous_text=condition_on_previous_text,
        no_speech_threshold=0.7,
        temperature=(0.0, 0.2, 0.4),
        preprocessing_strength="safe_loudness",
    )


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
    ) -> list[ASRSegment]:
        raise NotImplementedError


class FasterWhisperASR(BaseASR):
    provider_name = "faster_whisper"

    def __init__(
        self,
        settings: Settings,
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
        self._model = self._load_model(settings.asr_model_name, settings.asr_device, settings.asr_compute_type)
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
        )
        self._model_cache[key] = model
        return model

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
        profile = resolve_asr_quality_profile(self._settings, quality_mode)

        # Turkish specific transcription enhancements
        initial_prompt = None
        if resolved_language == "tr":
            # Use combined glossary for initial prompt
            initial_prompt = ", ".join(GLOSSARY_TERMS[:50])

        model = self._load_model(profile.model_name, self._settings.asr_device, profile.compute_type)
        segments, _info = _call_faster_whisper_transcribe(
            model,
            audio_path=audio_path,
            language=resolved_language,
            profile=profile,
            initial_prompt=initial_prompt,
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
    ) -> list[ASRSegment]:
        warning_text = f"[{self.asr_status}] Mock ASR placeholder; no real transcription was produced."
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
    try:
        return model.transcribe(str(audio_path), **kwargs)
    except TypeError as exc:
        message = str(exc)
        if "temperature" not in message:
            raise
        LOGGER.warning("Faster-Whisper runtime rejected temperature fallback settings; retrying without them.")
        kwargs.pop("temperature", None)
        return model.transcribe(str(audio_path), **kwargs)


def build_asr(settings: Settings) -> BaseASR:
    provider = settings.asr_provider.strip().lower()
    if provider == "mock":
        return MockASR(asr_status=ASR_STATUS_MOCK_EXPLICIT)
    if provider == "auto":
        local, error = _build_optional_local_asr(settings)
        if local is not None:
            return local
        if _gpu_required(settings):
            reason = str(error) if error is not None else "unknown local ASR error"
            raise RuntimeError(f"CMG_REQUIRE_GPU=1 but CUDA ASR could not load: {reason}") from error
        reason = str(error) if error is not None else "unknown local ASR error"
        LOGGER.warning("%s: Local ASR is unavailable. Falling back to MockASR. reason=%s", ASR_STATUS_MOCK_FALLBACK, reason)
        return MockASR(asr_status=ASR_STATUS_MOCK_FALLBACK, fallback_reason=reason)
    local, error = _build_optional_local_asr(settings)
    if local is not None:
        return local
    reason = str(error) if error is not None else "unknown local ASR error"
    if _gpu_required(settings):
        raise RuntimeError(f"CMG_REQUIRE_GPU=1 but CUDA ASR could not load: {reason}") from error
    raise RuntimeError(f"faster-whisper ASR could not load: {reason}") from error


def _build_optional_local_asr(settings: Settings) -> tuple[BaseASR | None, Exception | None]:
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
            LOGGER.warning("%s Falling back to CPU/int8 because CMG_REQUIRE_GPU is not set.", fallback_reason)
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


def _gpu_required(settings: Settings) -> bool:
    return bool(getattr(settings, "gpu_required", False))


def _should_retry_cpu(settings: Settings) -> bool:
    return _is_cuda_device(settings.asr_device) and not _gpu_required(settings)


def _is_cuda_device(device: str | None) -> bool:
    return (device or "").strip().lower().startswith("cuda")


def _profile_value(value: str | None, fallback: str) -> str:
    cleaned = (value or "").strip()
    return cleaned or fallback


def _cuda_load_status(*, requested_device: str | None, loaded_device: str | None, fallback_reason: str | None) -> str:
    if not _is_cuda_device(requested_device):
        return "not_requested"
    if fallback_reason:
        return "fallback_to_cpu"
    if _is_cuda_device(loaded_device):
        return "loaded_on_cuda"
    return "requested_but_not_loaded"


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


def _estimate_segment_confidence(
    *,
    word_confidence: float | None,
    avg_logprob: float | None,
    no_speech_prob: float | None,
    compression_ratio: float | None,
) -> float | None:
    candidates: list[float] = []
    if word_confidence is not None:
        candidates.append(_clamp(float(word_confidence), 0.0, 1.0))
    if avg_logprob is not None:
        candidates.append(_clamp(math.exp(float(avg_logprob)), 0.0, 1.0))
    if not candidates:
        return None

    score = sum(candidates) / len(candidates)
    if no_speech_prob is not None:
        score *= 1.0 - (0.45 * _clamp(no_speech_prob, 0.0, 1.0))
    if compression_ratio is not None and compression_ratio > 2.4:
        score *= 0.85
    if compression_ratio is not None and compression_ratio > 3.0:
        score *= 0.75
    return round(_clamp(score, 0.0, 1.0), 3)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
