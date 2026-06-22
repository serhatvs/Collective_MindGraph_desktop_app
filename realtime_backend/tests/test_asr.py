from __future__ import annotations

import wave
from pathlib import Path

from app.config import Settings
from app.models import ASRSegment, SpeechRegion
from app.pipeline import asr as asr_module
from app.pipeline.asr import (
    ASR_STATUS_MOCK_EXPLICIT,
    ASR_STATUS_MOCK_FALLBACK,
    MockASR,
    _dedupe_segments,
    _extract_wav_region,
    _regions_for_asr,
    resolve_asr_quality_profile,
)


def test_regions_for_asr_add_padding_and_merge_overlaps():
    regions = _regions_for_asr(
        [
            SpeechRegion(start=1.0, end=2.0, confidence=0.8),
            SpeechRegion(start=2.05, end=3.0, confidence=0.7),
            SpeechRegion(start=5.0, end=6.0, confidence=0.9),
        ],
        padding_seconds=0.1,
    )

    assert len(regions) == 2
    assert regions[0].start == 0.9
    assert regions[0].end == 3.1
    assert regions[1].start == 4.9


def test_extract_wav_region_preserves_expected_duration(tmp_path: Path):
    source = tmp_path / "source.wav"
    _write_constant_wav(source, sample_rate=16000, duration_seconds=3.0)

    region_path = _extract_wav_region(source, start_seconds=0.5, end_seconds=1.75, target_dir=tmp_path)
    try:
        with wave.open(str(region_path), "rb") as handle:
            duration = handle.getnframes() / handle.getframerate()
        assert 1.20 <= duration <= 1.30
    finally:
        region_path.unlink(missing_ok=True)


def test_dedupe_segments_drops_overlapping_duplicates():
    deduped = _dedupe_segments(
        [
            ASRSegment(start=0.0, end=1.0, text="Hello world", confidence=0.8),
            ASRSegment(start=0.02, end=1.01, text="hello world", confidence=0.9),
            ASRSegment(start=1.2, end=2.0, text="Second line", confidence=0.8),
        ]
    )

    assert len(deduped) == 2
    assert deduped[0].text == "Hello world"
    assert deduped[1].text == "Second line"


def test_mock_asr_emits_segments_per_vad_region():
    asr = MockASR()
    segments = asr.transcribe(
        Path("sample.wav"),
        regions=[
            SpeechRegion(start=0.0, end=0.8),
            SpeechRegion(start=1.0, end=1.7),
        ],
    )

    assert len(segments) == 2
    assert segments[0].start == 0.0
    assert segments[1].end == 1.7
    assert segments[0].text.startswith("[ASR_STATUS=MOCK_EXPLICIT]")
    assert segments[0].confidence == 0.0


def test_build_asr_auto_prefers_local(monkeypatch):
    created: list[str] = []

    class FakeLocalASR:
        def __init__(self, settings):
            created.append("local")

    monkeypatch.setattr(asr_module, "FasterWhisperASR", FakeLocalASR)

    provider = asr_module.build_asr(Settings())

    assert created == ["local"]
    assert isinstance(provider, FakeLocalASR)


def test_build_asr_auto_falls_back_to_mock_when_local_unavailable(monkeypatch):
    class BrokenLocalASR:
        def __init__(self, settings):
            raise RuntimeError("missing local runtime")

    monkeypatch.setattr(asr_module, "FasterWhisperASR", BrokenLocalASR)

    provider = asr_module.build_asr(Settings())

    assert isinstance(provider, MockASR)
    assert provider.asr_status == ASR_STATUS_MOCK_FALLBACK
    assert provider.mock_fallback_used is True


def test_explicit_mock_asr_status_is_not_fallback():
    provider = asr_module.build_asr(Settings(asr_provider="mock"))

    assert isinstance(provider, MockASR)
    assert provider.asr_status == ASR_STATUS_MOCK_EXPLICIT
    assert provider.mock_fallback_used is False


def test_resolve_asr_quality_profiles_are_explicit():
    settings = Settings()

    fast = resolve_asr_quality_profile(settings, "fast")
    balanced = resolve_asr_quality_profile(settings, "balanced")
    max_quality = resolve_asr_quality_profile(settings, "max_quality")
    accurate_alias = resolve_asr_quality_profile(settings, "accurate")

    assert fast.name == "fast"
    assert fast.beam_size == 1
    assert balanced.name == "balanced"
    assert balanced.word_timestamps is True
    assert balanced.vad_filter is False
    assert max_quality.name == "max_quality"
    assert max_quality.beam_size >= 5
    assert max_quality.word_timestamps is True
    assert max_quality.vad_filter is False
    assert accurate_alias.name == "max_quality"


def _write_constant_wav(path: Path, sample_rate: int, duration_seconds: float) -> None:
    total_frames = int(sample_rate * duration_seconds)
    frames = (b"\x00\x00" * total_frames)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(frames)
