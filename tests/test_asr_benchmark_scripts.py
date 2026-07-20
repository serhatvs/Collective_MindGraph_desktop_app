from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "benchmarks"
sys.path.insert(0, str(SCRIPTS_DIR))

from asr_benchmark_common import provider_status, should_score_accuracy  # noqa: E402
import benchmark_asr_accuracy  # noqa: E402


def test_benchmark_accuracy_refuses_wer_cer_without_reference():
    run = SimpleNamespace(
        label="accuracy",
        profile="gpu_asr",
        model="small",
        requested_vad_provider="energy",
        actual_vad_provider="energy",
        model_load_time_seconds=1.0,
        transcription_time_seconds=2.0,
        real_time_factor=0.5,
        segment_count=1,
        speech_region_count=1,
        metadata={"asr_status": "ASR_STATUS=OK", "mock_fallback_used": False},
        diagnostics={"GPU requested by ASR": True, "GPU actually loaded by ASR": True},
        error=None,
        audio_path=Path("sample.wav"),
        audio_duration=4.0,
        raw_transcript="merhaba",
        cleaned_transcript="Merhaba.",
    )

    report = benchmark_asr_accuracy._build_report(
        status="ASR_ACCURACY_BENCHMARK_RUNTIME_ONLY_NO_REFERENCE",
        run=run,
        reference_path=None,
        reference_text=None,
        wer=None,
        cer=None,
        scoring_enabled=False,
    )

    assert should_score_accuracy(None) is False
    assert "WER: `not computed`" in report
    assert "CER: `not computed`" in report
    assert "WER/CER were not computed because no real reference transcript was provided." in report


def test_silero_vad_unavailable_is_nonblocking_status():
    assert provider_status("silero", "energy", None) == "silero_unavailable_asr_continued"
