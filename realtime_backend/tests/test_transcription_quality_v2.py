from __future__ import annotations

import math
import os
import sys
import wave
from pathlib import Path

from app.config import Settings
from app.models import ASRSegment, TranscriptSegment
from app.pipeline.alignment import merge_transcript_segments
from app.pipeline.asr import _call_faster_whisper_transcribe, resolve_asr_quality_profile
from app.pipeline.speaker_mapper import StableSpeakerMapper
from app.pipeline.transcription_quality import estimate_transcription_confidence
from app.utils.audio_process import analyze_audio_quality, preprocessing_steps, resolve_ffmpeg_executable


def test_bad_mic_recovery_profile_controls_quality_settings():
    settings = Settings(
        asr_model_name="small",
        asr_compute_type="int8",
        asr_bad_mic_model_name="large-v3",
        asr_bad_mic_compute_type="float16",
    )

    profile = resolve_asr_quality_profile(settings, "bad_mic_recovery")

    assert profile.name == "bad_mic_recovery"
    assert profile.model_name == "large-v3"
    assert profile.compute_type == "float16"
    assert profile.beam_size >= 5
    assert profile.word_timestamps is True
    assert profile.vad_filter is False
    assert profile.condition_on_previous_text is False
    assert profile.no_speech_threshold == 0.85
    assert profile.temperature == (0.0, 0.2, 0.4, 0.6)
    assert profile.preprocessing_strength == "bad_mic_recovery"


def test_audio_quality_score_flags_low_volume(tmp_path: Path):
    normal = tmp_path / "normal.wav"
    quiet = tmp_path / "quiet.wav"
    _write_sine_wav(normal, amplitude=0.25)
    _write_sine_wav(quiet, amplitude=0.005)

    normal_quality = analyze_audio_quality(
        normal,
        preprocessing_applied=True,
        preprocessing_strength="safe_loudness",
        preprocessing_steps=preprocessing_steps("safe_loudness"),
    )
    quiet_quality = analyze_audio_quality(
        quiet,
        preprocessing_applied=False,
        preprocessing_strength="format_only",
    )

    assert normal_quality is not None
    assert quiet_quality is not None
    assert normal_quality.audio_quality_score > quiet_quality.audio_quality_score
    assert quiet_quality.audio_quality_label == "Low"
    assert "low volume" in quiet_quality.warnings
    assert quiet_quality.preprocessing_applied is False


def test_ffmpeg_resolver_prefers_environment_override(monkeypatch):
    monkeypatch.setenv("CMG_RT_FFMPEG_PATH", "custom-ffmpeg")
    monkeypatch.setenv("CMG_FFMPEG_EXE", "ignored-ffmpeg")

    assert resolve_ffmpeg_executable() == "custom-ffmpeg"


def test_ffmpeg_resolver_finds_frozen_bundle_binary(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("CMG_RT_FFMPEG_PATH", raising=False)
    monkeypatch.delenv("CMG_FFMPEG_EXE", raising=False)
    executable_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    bundled_ffmpeg = tmp_path / executable_name
    bundled_ffmpeg.touch()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert resolve_ffmpeg_executable() == str(bundled_ffmpeg)


def test_confidence_percentage_combines_audio_and_asr_metadata():
    asr_segments = [
        ASRSegment(
            start=0.0,
            end=3.0,
            text="Merhaba ekip bugun kaliteyi konusuyoruz",
            confidence=0.82,
            avg_logprob=-0.25,
            no_speech_prob=0.08,
            compression_ratio=1.2,
            metadata={"segment_confidence_estimate": 0.82},
        )
    ]
    transcript_segments = [
        TranscriptSegment(
            segment_id="seg_1",
            start=0.0,
            end=3.0,
            speaker="Speaker_1",
            raw_text="Merhaba ekip bugun kaliteyi konusuyoruz",
            corrected_text="Merhaba ekip bugun kaliteyi konusuyoruz.",
            confidence=0.82,
        )
    ]

    estimate = estimate_transcription_confidence(
        audio_quality={"audio_quality_score": 82, "audio_quality_label": "High", "warnings": []},
        asr_segments=asr_segments,
        transcript_segments=transcript_segments,
        language="tr",
        duration_seconds=3.0,
    )

    assert 70 <= estimate.score <= 100
    assert estimate.label in {"Medium", "High"}
    assert estimate.segment_confidence == 0.82
    assert estimate.audio_quality_score == 82
    assert estimate.turkish_text_sanity_score is not None


def test_confidence_percentage_flags_empty_bad_audio():
    estimate = estimate_transcription_confidence(
        audio_quality={
            "audio_quality_score": 25,
            "audio_quality_label": "Low",
            "warnings": ["low volume"],
        },
        asr_segments=[],
        transcript_segments=[],
        language="tr",
        duration_seconds=15.0,
    )

    assert estimate.score < 50
    assert estimate.label == "Low"
    assert "transcript should be manually reviewed" in estimate.warnings
    assert "empty transcript" in estimate.warnings


def test_asr_metadata_survives_alignment_shape():
    asr_segment = ASRSegment(
        start=0.0,
        end=1.5,
        text="test segment",
        confidence=0.7,
        avg_logprob=-0.3,
        no_speech_prob=0.12,
        compression_ratio=1.4,
        text_length=12,
        metadata={"segment_confidence_estimate": 0.7},
    )

    merged = merge_transcript_segments([asr_segment], [], StableSpeakerMapper(), [])

    assert len(merged) == 1
    assert merged[0].metadata["asr"]["avg_logprob"] == -0.3
    assert merged[0].metadata["asr"]["no_speech_prob"] == 0.12
    assert merged[0].metadata["asr"]["compression_ratio"] == 1.4
    assert merged[0].metadata["asr"]["segment_confidence_estimate"] == 0.7


def test_faster_whisper_temperature_fallback_is_optional(tmp_path: Path):
    class LegacyModel:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def transcribe(self, _audio_path: str, **kwargs):
            self.calls.append(dict(kwargs))
            if "temperature" in kwargs:
                raise TypeError("unexpected keyword argument 'temperature'")
            return [], {}

    model = LegacyModel()
    profile = resolve_asr_quality_profile(Settings(), "balanced")
    _call_faster_whisper_transcribe(
        model,
        audio_path=tmp_path / "sample.wav",
        language="tr",
        profile=profile,
        initial_prompt=None,
    )

    assert "temperature" in model.calls[0]
    assert "temperature" not in model.calls[1]


def _write_sine_wav(path: Path, *, amplitude: float, sample_rate: int = 16000, duration: float = 1.0) -> None:
    frames = bytearray()
    for index in range(int(sample_rate * duration)):
        value = int(math.sin(2 * math.pi * 440 * index / sample_rate) * amplitude * 32767)
        frames.extend(value.to_bytes(2, byteorder="little", signed=True))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(bytes(frames))
