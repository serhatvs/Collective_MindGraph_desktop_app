from __future__ import annotations

import wave
from pathlib import Path

from app.config import Settings
from app.models import ASRSegment, SpeechRegion
from app.pipeline import asr as asr_module
from app.pipeline.asr import (
    FallbackASR,
    MockASR,
    _dedupe_segments,
    _deepgram_request_params,
    _deepgram_segments_from_payload,
    _extract_wav_region,
    _regions_for_asr,
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


def test_deepgram_request_params_enable_language_detection_when_language_absent():
    settings = Settings(deepgram_api_key="dg_key")

    params = _deepgram_request_params(settings, language=None)

    assert params["model"] == "nova-3"
    assert params["detect_language"] == "true"
    assert "language" not in params


def test_deepgram_request_params_prefer_explicit_language():
    settings = Settings(deepgram_api_key="dg_key")

    params = _deepgram_request_params(settings, language="tr")

    assert params["language"] == "tr"
    assert "detect_language" not in params


def test_deepgram_payload_parses_utterances_with_word_offsets():
    payload = {
        "results": {
            "utterances": [
                {
                    "start": 0.5,
                    "end": 2.0,
                    "confidence": 0.97,
                    "transcript": "Merhaba nasilsin?",
                    "words": [
                        {"start": 0.5, "end": 0.9, "word": "Merhaba", "confidence": 0.99},
                        {"start": 1.0, "end": 2.0, "punctuated_word": "nasilsin?", "confidence": 0.95},
                    ],
                }
            ]
        }
    }

    segments = _deepgram_segments_from_payload(payload, offset_seconds=4.0)

    assert len(segments) == 1
    assert segments[0].start == 4.5
    assert segments[0].end == 6.0
    assert segments[0].text == "Merhaba nasilsin?"
    assert segments[0].words[1].word == "nasilsin?"


def test_deepgram_payload_falls_back_to_channel_alternative_words():
    payload = {
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {
                            "transcript": "Selam dunya",
                            "confidence": 0.83,
                            "words": [
                                {"start": 0.1, "end": 0.4, "word": "Selam", "confidence": 0.8},
                                {"start": 0.5, "end": 0.9, "word": "dunya", "confidence": 0.86},
                            ],
                        }
                    ]
                }
            ]
        }
    }

    segments = _deepgram_segments_from_payload(payload, offset_seconds=0.0)

    assert len(segments) == 1
    assert segments[0].start == 0.1
    assert segments[0].end == 0.9
    assert segments[0].text == "Selam dunya"


def test_build_asr_auto_prefers_local_when_no_deepgram_key(monkeypatch):
    created: list[str] = []

    class FakeLocalASR:
        def __init__(self, settings):
            created.append("local")

    monkeypatch.setattr(asr_module, "FasterWhisperASR", FakeLocalASR)

    provider = asr_module.build_asr(Settings(deepgram_api_key=None))

    assert created == ["local"]
    assert isinstance(provider, FakeLocalASR)


def test_build_asr_auto_wraps_deepgram_with_local_fallback(monkeypatch):
    class FakeLocalASR:
        def __init__(self, settings):
            self.name = "local"

    class FakeDeepgramASR:
        def __init__(self, settings):
            self.name = "deepgram"

    monkeypatch.setattr(asr_module, "FasterWhisperASR", FakeLocalASR)
    monkeypatch.setattr(asr_module, "DeepgramASR", FakeDeepgramASR)

    provider = asr_module.build_asr(Settings(deepgram_api_key="dg_key"))

    assert isinstance(provider, FallbackASR)


def test_build_asr_auto_falls_back_to_mock_when_local_unavailable(monkeypatch):
    class BrokenLocalASR:
        def __init__(self, settings):
            raise RuntimeError("missing local runtime")

    monkeypatch.setattr(asr_module, "FasterWhisperASR", BrokenLocalASR)

    provider = asr_module.build_asr(Settings(deepgram_api_key=None))

    assert isinstance(provider, MockASR)


def _write_constant_wav(path: Path, sample_rate: int, duration_seconds: float) -> None:
    total_frames = int(sample_rate * duration_seconds)
    frames = (b"\x00\x00" * total_frames)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(frames)
