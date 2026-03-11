from __future__ import annotations

import wave
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from app.config import Settings
from app.pipeline.vad import EnergyVAD, _postprocess_regions
from app.models import SpeechRegion


def test_postprocess_regions_merges_close_regions_and_splits_long_windows():
    settings = Settings(
        vad_provider="energy",
        vad_merge_gap_ms=200,
        vad_max_region_seconds=8.0,
        vad_target_region_seconds=4.0,
        vad_split_search_seconds=1.0,
    )
    energies = np.concatenate(
        [
            np.full(60, 0.6, dtype=np.float32),
            np.array([0.02, 0.01, 0.03], dtype=np.float32),
            np.full(60, 0.5, dtype=np.float32),
        ]
    )
    regions = [
        SpeechRegion(start=0.0, end=5.0, confidence=0.8),
        SpeechRegion(start=5.1, end=12.5, confidence=0.7),
    ]

    processed = _postprocess_regions(
        regions=regions,
        frame_energies=energies,
        frame_ms=100,
        total_duration_seconds=12.5,
        settings=settings,
    )

    assert len(processed) >= 2
    assert processed[0].start == 0.0
    assert processed[-1].end <= 12.5
    assert all((region.end - region.start) <= 8.0 for region in processed)


def test_energy_vad_detects_two_speech_regions_from_synthetic_wav(tmp_path: Path):
    sample_rate = 16000
    audio = np.concatenate(
        [
            np.zeros(int(sample_rate * 0.35), dtype=np.float32),
            _tone(sample_rate, 0.55, 220.0),
            np.zeros(int(sample_rate * 0.45), dtype=np.float32),
            _tone(sample_rate, 0.65, 440.0),
            np.zeros(int(sample_rate * 0.30), dtype=np.float32),
        ]
    )
    wav_path = tmp_path / "vad_test.wav"
    _write_wav(wav_path, sample_rate, audio)

    vad = EnergyVAD(
        Settings(
            vad_provider="energy",
            vad_frame_ms=20,
            vad_min_speech_ms=120,
            vad_min_silence_ms=180,
            vad_padding_ms=40,
            vad_merge_gap_ms=80,
            vad_energy_threshold=0.01,
        )
    )

    regions = vad.detect(wav_path)

    assert len(regions) == 2
    assert 0.2 <= regions[0].start <= 0.45
    assert 0.75 <= regions[0].end <= 1.05
    assert 1.15 <= regions[1].start <= 1.55
    assert 1.85 <= regions[1].end <= 2.20


def _tone(sample_rate: int, duration_seconds: float, frequency_hz: float) -> np.ndarray:
    timeline = np.arange(int(sample_rate * duration_seconds), dtype=np.float32) / sample_rate
    return (0.35 * np.sin(2 * np.pi * frequency_hz * timeline)).astype(np.float32)


def _write_wav(path: Path, sample_rate: int, audio: np.ndarray) -> None:
    pcm = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
