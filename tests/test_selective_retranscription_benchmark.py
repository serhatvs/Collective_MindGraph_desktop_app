from __future__ import annotations

from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from benchmark_selective_retranscription import (  # noqa: E402
    BenchmarkRun,
    build_report,
    calculate_domain_term_accuracy,
    discover_audio,
)


def test_report_does_not_emit_wer_or_cer_without_reference():
    run = BenchmarkRun(
        audio_path=Path("sample.wav"),
        mode="selective_retranscription",
        profile="balanced",
        reference_path=None,
        reference_text=None,
        selected_text="Merhaba ekip.",
        confidence_estimate=72,
        candidate_scores=[{"first_pass_score": 40, "second_pass_score": 78}],
    )

    report = build_report([run])

    assert "Confidence Estimate" in report
    assert "WER" not in report
    assert "CER" not in report
    assert "Selected candidate text" in report


def test_report_emits_reference_metrics_and_operations_only_with_reference():
    run = BenchmarkRun(
        audio_path=Path("sample.wav"),
        mode="selective_retranscription",
        profile="balanced",
        reference_path=Path("sample.txt"),
        reference_text="Merhaba ekip",
        selected_text="Merhaba takim",
        metrics={
            "wer": 0.5,
            "cer": 0.2,
            "notable_substitutions": [{"reference": "ekip", "actual": "takim"}],
            "notable_deletions": [],
            "notable_insertions": [],
        },
        domain_term_accuracy=0.5,
    )

    report = build_report([run])

    assert "WER" in report
    assert "CER" in report
    assert "Substitutions" in report
    assert "Domain term accuracy" in report


def test_domain_term_accuracy_uses_only_terms_present_in_reference():
    score = calculate_domain_term_accuracy(
        "MindGraph toplantisi basladi",
        "MindGraph oturumu basladi",
        ["MindGraph", "FastAPI"],
    )

    assert score == 1.0


def test_discover_audio_accepts_file_and_directory(tmp_path: Path):
    wav = tmp_path / "a.wav"
    flac = tmp_path / "nested" / "b.flac"
    text = tmp_path / "ignore.txt"
    flac.parent.mkdir()
    wav.write_bytes(b"wav")
    flac.write_bytes(b"flac")
    text.write_text("ignore", encoding="utf-8")

    assert discover_audio(wav) == [wav.resolve()]
    assert discover_audio(tmp_path) == [wav.resolve(), flac.resolve()]
