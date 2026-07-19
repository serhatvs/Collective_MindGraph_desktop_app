from __future__ import annotations

import math
import wave
from pathlib import Path

import pytest

from app.config import Settings
from app.models import ASRSegment, TranscriptionDiagnostics, WordTimestamp
from app.pipeline.asr import _call_faster_whisper_transcribe, resolve_asr_quality_profile
from app.pipeline.orchestrator import TranscriptionPipeline
from app.pipeline.selective_retranscription import (
    SegmentRetranscriptionTrigger,
    build_retranscription_regions,
    find_retranscription_triggers,
)
from app.pipeline.transcription_candidate_selector import TranscriptionCandidateSelector
from app.pipeline.transcription_glossary import parse_term_input, resolve_transcription_glossary


def _selector(min_improvement: float = 6.0) -> TranscriptionCandidateSelector:
    return TranscriptionCandidateSelector(
        min_improvement=min_improvement,
        min_words_per_second=0.45,
        max_words_per_second=5.5,
        min_text_length=4,
    )


def _segment(
    start: float,
    end: float,
    text: str,
    *,
    avg_logprob: float,
    word_probability: float,
    no_speech_prob: float = 0.05,
    compression_ratio: float = 1.2,
) -> ASRSegment:
    words = [
        WordTimestamp(start=start, end=end, word=f" {word}", probability=word_probability)
        for word in text.split()
    ]
    return ASRSegment(
        start=start,
        end=end,
        text=text,
        words=words,
        avg_logprob=avg_logprob,
        no_speech_prob=no_speech_prob,
        compression_ratio=compression_ratio,
        text_length=len(text),
        metadata={"word_confidence": word_probability},
    )


def test_selective_recovery_profile_is_stronger_and_configurable():
    settings = Settings(
        asr_model_name="small",
        asr_compute_type="int8",
        asr_device="cuda",
        selective_retranscription_model="large-v3",
        selective_retranscription_compute_type=None,
        selective_retranscription_beam_size=11,
    )

    profile = resolve_asr_quality_profile(settings, "selective_recovery")

    assert profile.model_name == "large-v3"
    assert profile.compute_type == "float16"
    assert profile.beam_size == 11
    assert profile.word_timestamps is True
    assert profile.vad_filter is False
    assert profile.condition_on_previous_text is False
    assert len(profile.temperature) > 1


def test_trigger_logic_uses_configured_thresholds_and_audio_warnings():
    settings = Settings(
        selective_retranscription_avg_logprob_threshold=-0.8,
        selective_retranscription_candidate_score_threshold=65.0,
    )
    weak = _segment(1.0, 2.5, "x", avg_logprob=-1.4, word_probability=0.2)

    triggers = find_retranscription_triggers(
        [weak],
        settings=settings,
        selector=_selector(),
        language="tr",
        audio_quality={
            "audio_quality_score": 40,
            "low_volume": True,
            "possible_noise": True,
        },
    )

    assert len(triggers) == 1
    reasons = set(triggers[0].reasons)
    assert "avg_logprob_below_threshold" in reasons
    assert "empty_or_nearly_empty_text" in reasons
    assert "audio_quality_score_below_threshold" in reasons
    assert "low_volume_audio" in reasons
    assert "noisy_or_unclear_audio" in reasons


def test_region_planning_clamps_padding_and_merges_adjacent_flagged_segments():
    segments = [
        _segment(0.1, 0.8, "birinci bolum", avg_logprob=-1.0, word_probability=0.4),
        _segment(0.9, 1.5, "ikinci bolum", avg_logprob=-1.0, word_probability=0.4),
        _segment(2.0, 2.8, "komsu saglam", avg_logprob=-0.1, word_probability=0.95),
    ]
    triggers = [
        SegmentRetranscriptionTrigger(0, ("weak",), 30.0),
        SegmentRetranscriptionTrigger(1, ("weak",), 32.0),
    ]

    regions = build_retranscription_regions(
        segments,
        triggers,
        audio_duration=3.0,
        padding_seconds=0.4,
        merge_gap_seconds=0.25,
        max_region_duration=4.0,
        max_regions=3,
    )

    assert len(regions) == 1
    assert regions[0].start == 0.0
    assert regions[0].end == 1.9
    assert regions[0].segment_indices == (0, 1)


def test_region_planning_honors_max_regions():
    segments = [
        _segment(index * 2.0, index * 2.0 + 1.0, f"segment {index}", avg_logprob=-1.2, word_probability=0.3)
        for index in range(4)
    ]
    triggers = [SegmentRetranscriptionTrigger(index, ("weak",), 30.0) for index in range(4)]

    regions = build_retranscription_regions(
        segments,
        triggers,
        audio_duration=8.0,
        padding_seconds=0.1,
        merge_gap_seconds=0.0,
        max_region_duration=2.0,
        max_regions=2,
    )

    assert len(regions) == 2


def test_candidate_selector_requires_minimum_improvement_and_retains_worse_second_pass():
    first = _segment(0.0, 2.0, "toplanti notlari hazir", avg_logprob=-0.25, word_probability=0.9)
    marginal = _segment(0.0, 2.0, "toplanti notlari hazir", avg_logprob=-0.22, word_probability=0.91)
    worse = _segment(0.0, 2.0, "x x x x x x", avg_logprob=-1.4, word_probability=0.2)

    marginal_selection = _selector(min_improvement=8.0).select(first, marginal, language="tr")
    worse_selection = _selector().select(first, worse, language="tr")

    assert marginal_selection.selected_pass == "first"
    assert worse_selection.selected_pass == "first"


def test_candidate_selector_replaces_clearly_better_candidate_without_length_reward():
    first = _segment(0.0, 2.0, "x", avg_logprob=-1.6, word_probability=0.15, no_speech_prob=0.7)
    second = _segment(
        0.1,
        1.9,
        "teknik toplanti basliyor",
        avg_logprob=-0.15,
        word_probability=0.94,
    )

    selection = _selector().select(first, second, language="tr", glossary_terms=["MindGraph"])

    assert selection.selected_pass == "second"
    assert selection.score_difference >= 6.0
    assert selection.second_pass.score > selection.first_pass.score


def test_glossary_precedence_deduplication_and_limits(tmp_path: Path):
    project_path = tmp_path / "project.json"
    project_path.write_text('["ProjectTerm", "FastAPI", "VeryLongProjectTerminology"]', encoding="utf-8")
    settings = Settings(
        transcription_project_glossary_path=project_path,
        transcription_glossary_max_terms=5,
        transcription_glossary_max_prompt_chars=80,
        transcription_glossary_max_term_length=20,
    )

    resolved = resolve_transcription_glossary(
        settings,
        user_hotwords=["Hotword", "SessionTerm"],
        session_terms=["sessionterm", "FastAPI"],
    )

    assert resolved.terms[:3] == ("Hotword", "SessionTerm", "FastAPI")
    assert resolved.metadata["removed_duplicates"] >= 2
    assert resolved.metadata["omitted_too_long"] == 1
    assert resolved.metadata["omitted_count"] > 0
    assert len(resolved.terms) <= 5


def test_glossary_input_accepts_json_and_delimited_text():
    assert parse_term_input('["bir", "iki"]') == ["bir", "iki"]
    assert parse_term_input("bir, iki;uc") == ["bir", "iki", "uc"]


def test_faster_whisper_hotwords_are_forwarded_when_supported(tmp_path: Path):
    class HotwordModel:
        def __init__(self) -> None:
            self.received_hotwords = None

        def transcribe(self, _audio_path: str, *, hotwords=None, **_kwargs):
            self.received_hotwords = hotwords
            return [], {}

    model = HotwordModel()
    _segments, _info, call_metadata = _call_faster_whisper_transcribe(
        model,
        audio_path=tmp_path / "sample.wav",
        language="tr",
        profile=resolve_asr_quality_profile(Settings(), "balanced"),
        initial_prompt="MindGraph",
        hotwords="MindGraph, ozel terim",
    )

    assert model.received_hotwords == "MindGraph, ozel terim"
    assert call_metadata["hotwords_applied"] is True


def test_old_diagnostics_payload_receives_backward_compatible_defaults():
    diagnostics = TranscriptionDiagnostics(provider="faster_whisper", model="small", audio_duration=1.0)

    assert diagnostics.selective_retranscription_enabled is False
    assert diagnostics.selective_retranscription_regions == 0
    assert diagnostics.glossary_metadata == {}


@pytest.mark.asyncio
async def test_pipeline_selectively_replaces_only_weak_segment_and_preserves_raw_candidates(
    tmp_path: Path,
    monkeypatch,
):
    audio_path = tmp_path / "meeting.wav"
    _write_wav(audio_path, duration=3.0)
    monkeypatch.setattr("app.pipeline.orchestrator.normalize_audio", lambda *_args, **_kwargs: False)

    first_pass = [
        _segment(0.1, 0.8, "ilk segment saglam", avg_logprob=-0.1, word_probability=0.95),
        _segment(1.0, 2.0, "x", avg_logprob=-1.6, word_probability=0.15, no_speech_prob=0.72),
        _segment(2.2, 2.8, "son segment saglam", avg_logprob=-0.1, word_probability=0.95),
    ]
    asr = _TwoPassASR(first_pass=first_pass)
    settings = Settings(
        data_dir=tmp_path / "data",
        temp_dir=tmp_path / "temp",
        selective_retranscription_enabled=True,
        selective_retranscription_model="large-v3",
        enable_summary=False,
        llm_provider="disabled",
    )
    pipeline = TranscriptionPipeline(
        settings,
        vad=_NoVAD(),
        asr=asr,
        diarizer=_NoDiarizer(),
    )

    transcript = await pipeline.process_audio_path(
        audio_path,
        source="test",
        language="tr",
        include_summary=False,
    )

    assert [segment.raw_text for segment in transcript.segments] == [
        "ilk segment saglam",
        "teknik toplanti duzeldi",
        "son segment saglam",
    ]
    assert transcript.segments[1].start == pytest.approx(1.0)
    assert transcript.segments[1].end == pytest.approx(1.9)
    assert transcript.segments[0].raw_text == first_pass[0].text
    assert transcript.segments[2].raw_text == first_pass[2].text
    assert transcript.segments[1].corrected_text != transcript.segments[1].raw_text
    metadata = transcript.metadata["selective_retranscription"]
    assert metadata["number_of_flagged_segments"] == 1
    assert metadata["number_of_second_pass_regions"] == 1
    assert metadata["number_of_replaced_segments"] == 1
    assert metadata["number_of_retained_first_pass_segments"] == 2
    assert metadata["first_pass_segments"][1]["text"] == "x"
    assert metadata["regions"][0]["selected_pass"] == "second"
    assert metadata["regions"][0]["first_pass_text"] == "x"
    assert metadata["regions"][0]["second_pass_text"] == "teknik toplanti duzeldi"
    assert metadata["regions"][0]["first_pass_raw_segments"][0]["text"] == "x"
    assert metadata["regions"][0]["second_pass_raw_segments"][0]["text"] == "teknik toplanti duzeldi"
    assert asr.quality_modes == ["max_quality", "selective_recovery"]


@pytest.mark.asyncio
async def test_pipeline_retains_first_pass_when_stronger_model_is_unavailable(tmp_path: Path, monkeypatch):
    audio_path = tmp_path / "meeting.wav"
    _write_wav(audio_path, duration=2.0)
    monkeypatch.setattr("app.pipeline.orchestrator.normalize_audio", lambda *_args, **_kwargs: False)
    asr = _TwoPassASR(
        first_pass=[
            _segment(0.4, 1.4, "x", avg_logprob=-1.6, word_probability=0.15, no_speech_prob=0.72)
        ],
        fail_second_pass=True,
    )
    settings = Settings(
        data_dir=tmp_path / "data",
        temp_dir=tmp_path / "temp",
        selective_retranscription_enabled=True,
        enable_summary=False,
        llm_provider="disabled",
    )
    pipeline = TranscriptionPipeline(settings, vad=_NoVAD(), asr=asr, diarizer=_NoDiarizer())

    transcript = await pipeline.process_audio_path(audio_path, source="test", language="tr", include_summary=False)

    assert transcript.segments[0].raw_text == "x"
    metadata = transcript.metadata["selective_retranscription"]
    assert metadata["number_of_replaced_segments"] == 0
    assert "model unavailable" in metadata["fallback_reason"]
    assert any("retained first pass" in warning for warning in transcript.metadata["warnings"])


class _NoVAD:
    provider_name = "none"

    def detect(self, _audio_path: Path):
        return []


class _NoDiarizer:
    provider_name = "none"

    def diarize(self, _audio_path: Path, _regions=None):
        return []


class _TwoPassASR:
    provider_name = "test_asr"
    asr_status = "ASR_STATUS=OK"
    mock_fallback_used = False
    fallback_reason = None

    def __init__(self, *, first_pass: list[ASRSegment], fail_second_pass: bool = False) -> None:
        self.first_pass = first_pass
        self.fail_second_pass = fail_second_pass
        self.quality_modes: list[str] = []

    def transcribe(
        self,
        _audio_path: Path,
        _language: str | None = None,
        _regions=None,
        quality_mode: str | None = None,
        glossary=None,
    ) -> list[ASRSegment]:
        self.quality_modes.append(str(quality_mode))
        if quality_mode != "selective_recovery":
            return [segment.model_copy(deep=True) for segment in self.first_pass]
        if self.fail_second_pass:
            raise RuntimeError("model unavailable in local cache")
        return [
            _segment(
                0.2,
                1.1,
                "teknik toplanti duzeldi",
                avg_logprob=-0.08,
                word_probability=0.97,
                no_speech_prob=0.01,
            )
        ]


def _write_wav(path: Path, *, duration: float, sample_rate: int = 16_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = bytearray()
    for index in range(int(duration * sample_rate)):
        value = int(math.sin(2 * math.pi * 220 * index / sample_rate) * 0.15 * 32767)
        frames.extend(value.to_bytes(2, byteorder="little", signed=True))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(bytes(frames))
