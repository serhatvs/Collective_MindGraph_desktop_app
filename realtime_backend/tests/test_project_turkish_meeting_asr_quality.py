from pathlib import Path

import pytest

from realtime_backend.app.config import Settings
from realtime_backend.app.evaluation.transcription_metrics import evaluate_transcription
from realtime_backend.app.pipeline.orchestrator import TranscriptionPipeline

FIXTURE_BASE_DIR = Path("realtime_backend/tests/fixtures")
AUDIO_PATH = FIXTURE_BASE_DIR / "audio" / "turkish_meeting_sample.wav"
EXPECTED_PATH = FIXTURE_BASE_DIR / "expected" / "turkish_meeting_sample.expected.txt"


def keyword_overlap(evaluation) -> float:
    expected = set(evaluation.normalized.reference_text.split())
    actual = set(evaluation.normalized.hypothesis_text.split())
    return len(expected.intersection(actual)) / len(expected) if expected else 0.0


@pytest.mark.asyncio
async def test_project_turkish_meeting_asr_quality():
    if not AUDIO_PATH.exists():
        pytest.skip(
            "Project-specific Turkish meeting WAV is missing. This is optional for now. "
            "To run this validation later, record realtime_backend/tests/fixtures/audio/turkish_meeting_sample.wav "
            "using prepare_turkish_audio_fixture.py."
        )
    
    if not EXPECTED_PATH.exists():
        pytest.skip(f"Expected transcript missing at {EXPECTED_PATH}")

    settings = Settings()
    # Ensure CPU for consistent validation
    settings.asr_device = "cpu"
    settings.asr_compute_type = "int8"
    
    pipeline = TranscriptionPipeline(settings)
    
    print("\n--- Running Project-Specific Meeting Validation ---")
    
    transcript = await pipeline.process_audio_path(
        AUDIO_PATH,
        source="meeting_test",
        language="tr",
        quality_mode="accurate"
    )
    
    expected_text = EXPECTED_PATH.read_text(encoding="utf-8").strip()
    raw_text = " ".join(s.raw_text for s in transcript.segments)
    cleaned_text = " ".join(s.corrected_text for s in transcript.segments)
    
    raw_evaluation = evaluate_transcription(expected_text, raw_text)
    clean_evaluation = evaluate_transcription(expected_text, cleaned_text)
    assert raw_evaluation is not None
    assert clean_evaluation is not None
    raw_overlap = keyword_overlap(raw_evaluation)
    clean_overlap = keyword_overlap(clean_evaluation)
    raw_wer = raw_evaluation.normalized.wer or 0.0
    clean_wer = clean_evaluation.normalized.wer or 0.0
    
    print(f"\nRaw Keyword Overlap: {raw_overlap:.2%}")
    print(f"Cleaned Keyword Overlap: {clean_overlap:.2%}")
    print(f"Raw WER (approx): {raw_wer:.2%}")
    print(f"Cleaned WER (approx): {clean_wer:.2%}")
    print(f"Improvement Delta (Overlap): {clean_overlap - raw_overlap:+.2%}")
    
    # Key terms verification
    key_terms = ["collective mindgraph", "fastapi", "sqlite", "vad", "transcript", "karar", "görev"]
    missing = [t for t in key_terms if t not in cleaned_text.lower()]
    if missing:
        print(f"⚠️ Missing Key Terms: {missing}")

    # Filler check (Heuristic: cleaned should have fewer fillers than raw)
    fillers = ["şey", "yani", "ııı"]
    raw_filler_count = sum(raw_text.lower().count(f) for f in fillers)
    clean_filler_count = sum(cleaned_text.lower().count(f) for f in fillers)
    
    print(f"Fillers (Raw): {raw_filler_count} | Fillers (Cleaned): {clean_filler_count}")
    
    assert clean_overlap >= raw_overlap, "Cleanup layer degraded keyword overlap"
    assert "ı" in cleaned_text or "ş" in cleaned_text or "ğ" in cleaned_text, "Turkish characters lost"
    
    # Ensure raw vs cleaned distinction in segments
    for s in transcript.segments:
        assert s.raw_text is not None
        assert s.corrected_text is not None
