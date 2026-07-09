"""Audio preprocessing and normalization helpers."""

from __future__ import annotations

import logging
import math
import os
import subprocess
import wave
from array import array
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AudioInspection:
    sample_rate: int
    channels: int
    sample_width_bytes: int
    frame_count: int
    duration_seconds: float
    format: str


@dataclass(frozen=True, slots=True)
class AudioQualityAnalysis:
    duration_seconds: float
    rms: float
    peak: float
    dbfs: float | None
    silence_ratio: float
    clipping_ratio: float
    unstable_level_ratio: float
    possible_noise: bool
    low_volume: bool
    clipping_detected: bool
    preprocessing_applied: bool
    preprocessing_strength: str
    preprocessing_steps: tuple[str, ...]
    audio_quality_score: int
    audio_quality_label: str
    warnings: tuple[str, ...]

    def to_metadata(self) -> dict[str, object]:
        return {
            "duration_seconds": self.duration_seconds,
            "rms": self.rms,
            "peak": self.peak,
            "dbfs": self.dbfs,
            "silence_ratio": self.silence_ratio,
            "clipping_ratio": self.clipping_ratio,
            "unstable_level_ratio": self.unstable_level_ratio,
            "possible_noise": self.possible_noise,
            "low_volume": self.low_volume,
            "clipping_detected": self.clipping_detected,
            "preprocessing_applied": self.preprocessing_applied,
            "preprocessing_strength": self.preprocessing_strength,
            "preprocessing_steps": list(self.preprocessing_steps),
            "audio_quality_score": self.audio_quality_score,
            "audio_quality_label": self.audio_quality_label,
            "warnings": list(self.warnings),
        }


def _resolve_ffmpeg_executable() -> str:
    """Return the ffmpeg executable path.

    Reads CMG_RT_FFMPEG_PATH or CMG_FFMPEG_EXE env vars first (same as
    media.py), then falls back to 'ffmpeg' on the system PATH.
    """
    env_value = (os.getenv("CMG_RT_FFMPEG_PATH") or os.getenv("CMG_FFMPEG_EXE") or "").strip()
    if env_value:
        return env_value
    return "ffmpeg"


def normalize_audio(
    source_path: Path,
    target_path: Path,
    sample_rate: int = 16000,
    preprocessing_strength: str = "format_only",
    *,
    trim_silence: bool = False,
    noise_reduction: bool = False,
) -> bool:
    """
    Normalize audio file to standard PCM format using ffmpeg.
    Logs parameters and timing for quality auditing.
    """
    ffmpeg_exe = _resolve_ffmpeg_executable()
    LOGGER.info(
        "Preprocessing audio: %s -> %s (SR: %d, strength=%s)",
        source_path.name,
        target_path.name,
        sample_rate,
        preprocessing_strength,
    )

    command = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(source_path),
    ]
    filters = _ffmpeg_filters(preprocessing_strength, trim_silence=trim_silence, noise_reduction=noise_reduction)
    if filters:
        command.extend(["-af", ",".join(filters)])
    command.extend(
        [
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "-sample_fmt",
            "s16",
            str(target_path),
        ]
    )

    try:
        # Run ffmpeg and capture stderr for quality logs
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        if result.stderr:
            LOGGER.debug("ffmpeg output: %s", result.stderr)
        return True
    except subprocess.CalledProcessError as exc:
        LOGGER.error("ffmpeg normalization failed: %s", exc.stderr)
        if filters:
            LOGGER.warning("Retrying audio normalization with format-only preprocessing.")
            return normalize_audio(source_path, target_path, sample_rate, "format_only")
        return False
    except FileNotFoundError:
        LOGGER.error("ffmpeg not found at '%s'. Audio normalization skipped.", ffmpeg_exe)
        return False


def inspect_audio(path: Path) -> AudioInspection | None:
    """Return WAV container facts for diagnostics, or None if the file is unreadable."""
    try:
        with wave.open(str(path), "rb") as handle:
            sample_rate = handle.getframerate()
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            frame_count = handle.getnframes()
    except (wave.Error, OSError) as exc:
        LOGGER.warning("Audio inspection failed for %s: %s", path, exc)
        return None

    duration = frame_count / sample_rate if sample_rate else 0.0
    return AudioInspection(
        sample_rate=sample_rate,
        channels=channels,
        sample_width_bytes=sample_width,
        frame_count=frame_count,
        duration_seconds=duration,
        format="wav",
    )


def analyze_audio_quality(
    path: Path,
    *,
    preprocessing_applied: bool,
    preprocessing_strength: str,
    preprocessing_steps: Sequence[str] = (),
) -> AudioQualityAnalysis | None:
    """Estimate local audio quality from a mono/stereo PCM WAV file."""
    try:
        samples, sample_rate = _read_wav_samples(path)
    except (wave.Error, OSError, ValueError) as exc:
        LOGGER.warning("Audio quality analysis failed for %s: %s", path, exc)
        return None

    if not samples or sample_rate <= 0:
        return AudioQualityAnalysis(
            duration_seconds=0.0,
            rms=0.0,
            peak=0.0,
            dbfs=None,
            silence_ratio=1.0,
            clipping_ratio=0.0,
            unstable_level_ratio=0.0,
            possible_noise=False,
            low_volume=True,
            clipping_detected=False,
            preprocessing_applied=preprocessing_applied,
            preprocessing_strength=preprocessing_strength,
            preprocessing_steps=tuple(preprocessing_steps),
            audio_quality_score=20,
            audio_quality_label="Low",
            warnings=("low volume", "transcript should be manually reviewed"),
        )

    duration = len(samples) / sample_rate
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    peak = max(abs(sample) for sample in samples)
    dbfs = 20.0 * math.log10(rms) if rms > 0.0 else None
    silence_ratio = sum(1 for sample in samples if abs(sample) < 0.01) / len(samples)
    clipping_ratio = sum(1 for sample in samples if abs(sample) >= 0.98) / len(samples)
    frame_rms_values = _frame_rms_values(samples, sample_rate)
    unstable_level_ratio = _unstable_level_ratio(frame_rms_values)
    possible_noise = _possible_noise(frame_rms_values, silence_ratio)
    low_volume = (dbfs is None) or dbfs < -35.0 or peak < 0.08
    clipping_detected = clipping_ratio >= 0.002
    score, warnings = _score_audio_quality(
        dbfs=dbfs,
        peak=peak,
        silence_ratio=silence_ratio,
        clipping_ratio=clipping_ratio,
        possible_noise=possible_noise,
        unstable_level_ratio=unstable_level_ratio,
        duration=duration,
    )
    return AudioQualityAnalysis(
        duration_seconds=round(duration, 3),
        rms=round(rms, 5),
        peak=round(peak, 5),
        dbfs=round(dbfs, 2) if dbfs is not None else None,
        silence_ratio=round(silence_ratio, 3),
        clipping_ratio=round(clipping_ratio, 5),
        unstable_level_ratio=round(unstable_level_ratio, 3),
        possible_noise=possible_noise,
        low_volume=low_volume,
        clipping_detected=clipping_detected,
        preprocessing_applied=preprocessing_applied,
        preprocessing_strength=preprocessing_strength,
        preprocessing_steps=tuple(preprocessing_steps),
        audio_quality_score=score,
        audio_quality_label=_audio_quality_label(score),
        warnings=tuple(warnings),
    )


def preprocessing_steps(
    preprocessing_strength: str,
    *,
    trim_silence: bool = False,
    noise_reduction: bool = False,
) -> tuple[str, ...]:
    steps = ["mono conversion", "16 kHz conversion", "s16 PCM conversion"]
    strength = preprocessing_strength.strip().lower()
    if strength in {"safe_loudness", "bad_mic_recovery"}:
        steps.append("loudness normalization")
    if strength == "bad_mic_recovery":
        steps.extend(["speech band limiting", "dynamic normalization"])
        if noise_reduction:
            steps.append("noise-safe reduction")
    if trim_silence and strength == "bad_mic_recovery":
        steps.append("safe leading/trailing silence trim")
    return tuple(steps)


def _ffmpeg_filters(preprocessing_strength: str, *, trim_silence: bool, noise_reduction: bool) -> list[str]:
    strength = preprocessing_strength.strip().lower()
    filters: list[str] = []
    if strength == "format_only":
        return filters
    if strength == "safe_loudness":
        filters.append("loudnorm=I=-23:TP=-2:LRA=11")
        return filters
    if strength == "bad_mic_recovery":
        filters.extend(
            [
                "highpass=f=80",
                "lowpass=f=7600",
                "loudnorm=I=-20:TP=-1.5:LRA=11",
                "dynaudnorm=f=150:g=15:p=0.95:m=10",
            ]
        )
        if noise_reduction:
            filters.append("afftdn=nf=-25")
        if trim_silence:
            filters.append(
                "silenceremove=start_periods=1:start_duration=0.15:start_threshold=-55dB:"
                "stop_periods=1:stop_duration=0.25:stop_threshold=-55dB"
            )
    return filters


def _read_wav_samples(path: Path) -> tuple[list[float], int]:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        sample_rate = handle.getframerate()
        raw = handle.readframes(handle.getnframes())

    if sample_width != 2:
        raise ValueError(f"unsupported sample width for analysis: {sample_width}")
    values = array("h")
    values.frombytes(raw)
    if not values:
        return [], sample_rate
    if channels > 1:
        mono: list[float] = []
        for index in range(0, len(values), channels):
            frame = values[index:index + channels]
            mono.append(sum(frame) / max(len(frame), 1) / 32768.0)
        return mono, sample_rate
    return [sample / 32768.0 for sample in values], sample_rate


def _frame_rms_values(samples: list[float], sample_rate: int, frame_ms: int = 30) -> list[float]:
    frame_size = max(1, int(sample_rate * frame_ms / 1000))
    values: list[float] = []
    for start in range(0, len(samples), frame_size):
        frame = samples[start:start + frame_size]
        if not frame:
            continue
        values.append(math.sqrt(sum(sample * sample for sample in frame) / len(frame)))
    return values


def _unstable_level_ratio(frame_rms_values: list[float]) -> float:
    active = [value for value in frame_rms_values if value >= 0.01]
    if len(active) < 3:
        return 0.0
    average = sum(active) / len(active)
    if average <= 0.0:
        return 0.0
    variance = sum((value - average) ** 2 for value in active) / len(active)
    return math.sqrt(variance) / average


def _possible_noise(frame_rms_values: list[float], silence_ratio: float) -> bool:
    active = sorted(value for value in frame_rms_values if value > 0.001)
    if len(active) < 10 or silence_ratio > 0.85:
        return False
    low_index = max(0, int(len(active) * 0.1) - 1)
    high_index = min(len(active) - 1, int(len(active) * 0.9))
    low = active[low_index]
    high = active[high_index]
    if high <= 0.0:
        return False
    return low / high > 0.35


def _score_audio_quality(
    *,
    dbfs: float | None,
    peak: float,
    silence_ratio: float,
    clipping_ratio: float,
    possible_noise: bool,
    unstable_level_ratio: float,
    duration: float,
) -> tuple[int, list[str]]:
    score = 100.0
    warnings: list[str] = []
    if duration <= 0.2:
        score -= 35
        warnings.append("audio duration is too short to judge reliably")
    if dbfs is None or dbfs < -45.0 or peak < 0.03:
        score -= 35
        warnings.append("low volume")
    elif dbfs < -35.0 or peak < 0.08:
        score -= 22
        warnings.append("low volume")
    elif dbfs < -28.0:
        score -= 10
    if silence_ratio > 0.85:
        score -= 25
        warnings.append("high silence ratio")
    elif silence_ratio > 0.65:
        score -= 15
        warnings.append("high silence ratio")
    if clipping_ratio > 0.02:
        score -= 30
        warnings.append("clipping")
    elif clipping_ratio >= 0.002:
        score -= 15
        warnings.append("clipping")
    if possible_noise:
        score -= 12
        warnings.append("noisy/unclear audio")
    if unstable_level_ratio > 1.4:
        score -= 8
        warnings.append("unstable audio level")
    score = int(round(max(0.0, min(100.0, score))))
    if score < 60:
        warnings.append("transcript should be manually reviewed")
    return score, _dedupe(warnings)


def _audio_quality_label(score: int) -> str:
    if score >= 75:
        return "High"
    if score >= 50:
        return "Medium"
    return "Low"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
