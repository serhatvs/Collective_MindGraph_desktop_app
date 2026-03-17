"""Voice activity detection providers."""

from __future__ import annotations

import importlib
import logging
import wave
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from ..config import Settings
from ..models import SpeechRegion

LOGGER = logging.getLogger(__name__)


class BaseVAD(ABC):
    @abstractmethod
    def detect(self, audio_path: Path) -> list[SpeechRegion]:
        raise NotImplementedError


class EnergyVAD(BaseVAD):
    """Approximate fallback VAD when silero is unavailable."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._frame_ms = settings.vad_frame_ms
        self._min_speech_ms = settings.vad_min_speech_ms
        self._min_silence_ms = settings.vad_min_silence_ms
        self._padding_ms = settings.vad_padding_ms
        self._base_threshold = settings.vad_energy_threshold

    def detect(self, audio_path: Path) -> list[SpeechRegion]:
        samples, sample_rate = _read_wav(audio_path)
        if samples.size == 0:
            return []

        energies = _frame_energies(samples, sample_rate, self._frame_ms)
        smoothed_energies = _smooth_energies(energies, self._settings.vad_smoothing_frames)
        adaptive_threshold = _adaptive_energy_threshold(
            smoothed_energies,
            self._base_threshold,
            self._settings.vad_adaptive_multiplier,
        )
        speech_mask = smoothed_energies >= adaptive_threshold

        min_speech_frames = max(1, int(self._min_speech_ms / self._frame_ms))
        min_silence_frames = max(1, int(self._min_silence_ms / self._frame_ms))
        padding_seconds = self._padding_ms / 1000
        total_duration_seconds = len(samples) / sample_rate

        regions: list[SpeechRegion] = []
        active_start: int | None = None
        silence_run = 0
        for frame_index, active in enumerate(speech_mask):
            if active and active_start is None:
                active_start = frame_index
                silence_run = 0
                continue
            if active:
                silence_run = 0
                continue
            if active_start is None:
                continue
            silence_run += 1
            if silence_run < min_silence_frames:
                continue
            if frame_index - active_start >= min_speech_frames:
                start = max(0.0, active_start * self._frame_ms / 1000 - padding_seconds)
                end = min(total_duration_seconds, (frame_index - silence_run + 1) * self._frame_ms / 1000 + padding_seconds)
                regions.append(
                    SpeechRegion(
                        start=start,
                        end=end,
                        confidence=_region_confidence(smoothed_energies, active_start, frame_index),
                    )
                )
            active_start = None
            silence_run = 0

        if active_start is not None:
            start = max(0.0, active_start * self._frame_ms / 1000 - padding_seconds)
            end = total_duration_seconds
            regions.append(
                SpeechRegion(
                    start=start,
                    end=end,
                    confidence=_region_confidence(smoothed_energies, active_start, len(smoothed_energies)),
                )
            )

        return _postprocess_regions(
            regions=regions,
            frame_energies=smoothed_energies,
            frame_ms=self._frame_ms,
            total_duration_seconds=total_duration_seconds,
            settings=self._settings,
        )


class SileroVAD(BaseVAD):
    def __init__(self, settings: Settings) -> None:
        try:
            silero_vad = importlib.import_module("silero_vad")
            get_speech_timestamps = getattr(silero_vad, "get_speech_timestamps")
            load_silero_vad = getattr(silero_vad, "load_silero_vad")
            read_audio = getattr(silero_vad, "read_audio")
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("silero-vad is not installed.") from exc

        self._get_speech_timestamps = get_speech_timestamps
        self._load_silero_vad = load_silero_vad
        self._read_audio = read_audio
        self._model = self._load_silero_vad()
        self._settings = settings

    def detect(self, audio_path: Path) -> list[SpeechRegion]:
        audio = self._read_audio(str(audio_path), sampling_rate=self._settings.sample_rate)
        timestamps = self._get_speech_timestamps(
            audio,
            self._model,
            sampling_rate=self._settings.sample_rate,
            min_speech_duration_ms=self._settings.vad_min_speech_ms,
            min_silence_duration_ms=self._settings.vad_min_silence_ms,
            speech_pad_ms=self._settings.vad_padding_ms,
        )
        samples, sample_rate = _read_wav(audio_path)
        regions = [
            SpeechRegion(
                start=item["start"] / self._settings.sample_rate,
                end=item["end"] / self._settings.sample_rate,
                confidence=item.get("confidence"),
            )
            for item in timestamps
        ]
        return _postprocess_regions(
            regions=regions,
            frame_energies=_smooth_energies(
                _frame_energies(samples, sample_rate, self._settings.vad_frame_ms),
                self._settings.vad_smoothing_frames,
            ),
            frame_ms=self._settings.vad_frame_ms,
            total_duration_seconds=len(samples) / sample_rate if sample_rate else 0.0,
            settings=self._settings,
        )


def build_vad(settings: Settings) -> BaseVAD:
    if settings.vad_provider == "silero":
        try:
            return SileroVAD(settings)
        except Exception as exc:  # pragma: no cover - dependency/env dependent
            LOGGER.warning("Falling back to EnergyVAD because silero failed: %s", exc)
    return EnergyVAD(settings)


def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        sample_rate = handle.getframerate()
        sample_width = handle.getsampwidth()
        raw = handle.readframes(handle.getnframes())

    dtype = np.int16 if sample_width == 2 else np.int8
    audio = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    max_value = float(np.iinfo(dtype).max or 1)
    return audio / max_value, sample_rate


def _frame_energies(samples: np.ndarray, sample_rate: int, frame_ms: int) -> np.ndarray:
    frame_size = max(1, int(sample_rate * frame_ms / 1000))
    frames = [
        samples[index : index + frame_size]
        for index in range(0, len(samples), frame_size)
        if len(samples[index : index + frame_size]) > 0
    ]
    return np.array([float(np.sqrt(np.mean(np.square(frame)))) for frame in frames], dtype=np.float32)


def _smooth_energies(energies: np.ndarray, window_frames: int) -> np.ndarray:
    if energies.size == 0 or window_frames <= 1:
        return energies
    kernel = np.ones(window_frames, dtype=np.float32) / window_frames
    return np.convolve(energies, kernel, mode="same")


def _adaptive_energy_threshold(
    energies: np.ndarray,
    base_threshold: float,
    adaptive_multiplier: float,
) -> float:
    if energies.size == 0:
        return base_threshold
    noise_floor = float(np.percentile(energies, 20))
    speech_floor = float(np.percentile(energies, 80))
    spread = max(0.0, speech_floor - noise_floor)
    adaptive_threshold = max(
        base_threshold,
        noise_floor + spread * 0.25,
        noise_floor * adaptive_multiplier,
    )
    return adaptive_threshold


def _region_confidence(energies: np.ndarray, start_frame: int, end_frame: int) -> float | None:
    if energies.size == 0 or end_frame <= start_frame:
        return None
    region = energies[start_frame:end_frame]
    if region.size == 0:
        return None
    peak = float(np.max(region))
    mean = float(np.mean(region))
    if peak <= 0:
        return 0.0
    return round(min(1.0, mean / peak), 3)


def _postprocess_regions(
    regions: list[SpeechRegion],
    frame_energies: np.ndarray,
    frame_ms: int,
    total_duration_seconds: float,
    settings: Settings,
) -> list[SpeechRegion]:
    merged = _merge_regions(regions, merge_gap_seconds=settings.vad_merge_gap_ms / 1000)
    return _split_long_regions(
        regions=merged,
        frame_energies=frame_energies,
        frame_ms=frame_ms,
        total_duration_seconds=total_duration_seconds,
        max_region_seconds=settings.vad_max_region_seconds,
        target_region_seconds=settings.vad_target_region_seconds,
        split_search_seconds=settings.vad_split_search_seconds,
    )


def _merge_regions(regions: list[SpeechRegion], merge_gap_seconds: float = 0.05) -> list[SpeechRegion]:
    if not regions:
        return []
    ordered = sorted(regions, key=lambda item: item.start)
    merged: list[SpeechRegion] = [ordered[0]]
    for region in ordered[1:]:
        current = merged[-1]
        if region.start <= current.end + merge_gap_seconds:
            merged[-1] = SpeechRegion(
                start=current.start,
                end=max(current.end, region.end),
                confidence=_merge_confidence(current.confidence, region.confidence),
            )
            continue
        merged.append(region)
    return merged


def _split_long_regions(
    regions: list[SpeechRegion],
    frame_energies: np.ndarray,
    frame_ms: int,
    total_duration_seconds: float,
    max_region_seconds: float,
    target_region_seconds: float,
    split_search_seconds: float,
) -> list[SpeechRegion]:
    if max_region_seconds <= 0:
        return regions

    split_regions: list[SpeechRegion] = []
    frame_seconds = frame_ms / 1000
    target_seconds = target_region_seconds if 0 < target_region_seconds < max_region_seconds else max_region_seconds / 2
    search_frames = max(1, int(split_search_seconds / frame_seconds))
    max_frames = max(1, int(max_region_seconds / frame_seconds))
    target_frames = max(1, int(target_seconds / frame_seconds))

    for region in regions:
        start_frame = max(0, int(region.start / frame_seconds))
        end_frame = min(len(frame_energies), max(start_frame + 1, int(np.ceil(region.end / frame_seconds))))
        if (end_frame - start_frame) <= max_frames:
            split_regions.append(region)
            continue

        current_start = start_frame
        while (end_frame - current_start) > max_frames:
            desired_split = min(end_frame - 1, current_start + target_frames)
            search_start = max(current_start + 1, desired_split - search_frames)
            search_end = min(end_frame - 1, desired_split + search_frames)
            split_frame = _best_split_frame(frame_energies, search_start, search_end, fallback=desired_split)
            split_regions.append(
                SpeechRegion(
                    start=current_start * frame_seconds,
                    end=min(total_duration_seconds, split_frame * frame_seconds),
                    confidence=region.confidence,
                )
            )
            current_start = split_frame

        split_regions.append(
            SpeechRegion(
                start=current_start * frame_seconds,
                end=min(total_duration_seconds, end_frame * frame_seconds),
                confidence=region.confidence,
            )
        )

    return [region for region in split_regions if region.end - region.start >= frame_seconds]


def _best_split_frame(
    frame_energies: np.ndarray,
    search_start: int,
    search_end: int,
    fallback: int,
) -> int:
    if frame_energies.size == 0 or search_end <= search_start:
        return fallback
    window = frame_energies[search_start : search_end + 1]
    if window.size == 0:
        return fallback
    return int(search_start + int(np.argmin(window)))


def _merge_confidence(left: float | None, right: float | None) -> float | None:
    values = [item for item in (left, right) if item is not None]
    if not values:
        return None
    return round(float(sum(values) / len(values)), 3)
