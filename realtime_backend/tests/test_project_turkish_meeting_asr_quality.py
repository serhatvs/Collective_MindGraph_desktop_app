import json
import pytest
from pathlib import Path
from realtime_backend.app.config import Settings
from realtime_backend.app.pipeline.orchestrator import TranscriptionPipeline

FIXTURE_BASE_DIR = Path("realtime_backend/tests/fixtures")
AUDIO_PATH = FIXTURE_BASE_DIR / "audio" / "turkish_meeting_sample.wav"
EXPECTED_PATH = FIXTURE_BASE_DIR / "expected" / "turkish_meeting_sample.expected.txt"

def levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def calculate_metrics(expected, actual):
    def tokenize(t):
        return [w.lower().strip(".,?!") for w in t.split() if w.strip(".,?!")]
    
    exp_tokens = tokenize(expected)
    act_tokens = tokenize(actual)
    
    exp_set = set(exp_tokens)
    act_set = set(act_tokens)
    
    overlap = len(exp_set.intersection(act_set)) / len(exp_set) if exp_set else 0.0
    wer = levenshtein_distance(exp_tokens, act_tokens) / len(exp_tokens) if exp_tokens else 0.0
    
    return overlap, wer

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
    
    raw_overlap, raw_wer = calculate_metrics(expected_text, raw_text)
    clean_overlap, clean_wer = calculate_metrics(expected_text, cleaned_text)
    
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
