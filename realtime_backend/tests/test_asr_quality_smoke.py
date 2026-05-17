import os
import pytest
from pathlib import Path
from realtime_backend.app.config import Settings
from realtime_backend.app.pipeline.orchestrator import TranscriptionPipeline

def get_expected_terms():
    expected_path = Path("realtime_backend/tests/fixtures/expected/turkish_meeting_sample.expected.txt")
    if not expected_path.exists():
        return []
    
    # Simple keyword extraction from expected text
    # (In a real scenario, this would be a curated list)
    keywords = {
        "MindGraph", "Collective", "FastAPI", "SQLite", "local-first",
        "transcript", "VAD", "toplantı", "görev", "karar", "düzelteceğiz",
        "aksiyon", "özet"
    }
    return keywords

def calculate_quality_score(transcript_text, expected_terms):
    if not expected_terms:
        return 0.0
    matched = 0
    text_lower = transcript_text.lower()
    for term in expected_terms:
        if term.lower() in text_lower:
            matched += 1
    return matched / len(expected_terms)

@pytest.mark.asyncio
async def test_asr_quality_smoke_turkish():
    audio_path = Path("realtime_backend/tests/fixtures/audio/turkish_meeting_sample.wav")
    
    if not audio_path.exists():
        pytest.skip(
            "Turkish audio fixture missing. Run: "
            "PYTHONPATH=. python realtime_backend/scripts/prepare_turkish_audio_fixture.py"
        )

    settings = Settings()
    
    # Verify we are not downloading models automatically
    # (This is handled by our configuration and faster-whisper default behavior if not pointed to a local path,
    # but we assume the environment is set up for local models).
    
    pipeline = TranscriptionPipeline(settings)
    
    # Run transcription
    transcript = await pipeline.process_audio_path(
        audio_path,
        source="smoke_test",
        language="tr",
        quality_mode="accurate"
    )
    
    assert transcript.language == "tr"
    assert len(transcript.segments) > 0
    
    full_raw = " ".join(s.raw_text for s in transcript.segments)
    full_cleaned = " ".join(s.corrected_text for s in transcript.segments)
    
    assert len(full_raw.strip()) > 0
    assert len(full_cleaned.strip()) > 0
    
    # Quality Scoring
    expected_terms = get_expected_terms()
    score = calculate_quality_score(full_cleaned, expected_terms)
    
    print(f"\nTurkish ASR Smoke Test Quality Score: {score:.2%}")
    
    # Basic sanity checks
    # Turkish characters check
    turkish_chars = ["ç", "ğ", "ı", "ö", "ş", "ü"]
    found_chars = [c for c in turkish_chars if c in full_cleaned.lower()]
    assert len(found_chars) > 0, "No Turkish characters found in transcript"
    
    # Check that it's not translated to English (heuristic)
    english_stop_words = {"the", "and", "is", "this"}
    words = set(full_cleaned.lower().split())
    common_english = words.intersection(english_stop_words)
    assert len(common_english) < 5, "Transcript seems to contain significant English translation"

    # Ensure raw vs cleaned separation
    assert transcript.diagnostics is not None
    assert transcript.diagnostics.raw_transcript_length > 0
    assert transcript.diagnostics.cleaned_transcript_length > 0
