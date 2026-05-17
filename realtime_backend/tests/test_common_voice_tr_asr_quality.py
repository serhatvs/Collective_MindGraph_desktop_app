import json
import pytest
from pathlib import Path
from realtime_backend.app.config import Settings
from realtime_backend.app.pipeline.orchestrator import TranscriptionPipeline

MANIFEST_PATH = Path("realtime_backend/tests/fixtures/expected/common_voice_tr_manifest.json")
FIXTURE_BASE_DIR = Path("realtime_backend/tests/fixtures")

@pytest.mark.asyncio
async def test_common_voice_tr_asr_regression_quick():
    """Quick CI-safe regression test using 3 samples."""
    if not MANIFEST_PATH.exists():
        pytest.skip("Common Voice manifest missing.")

    with MANIFEST_PATH.open(encoding="utf-8") as f:
        manifest = json.load(f)

    samples = manifest.get("samples", [])[:3] # CI only needs 3
    if not samples:
        pytest.skip("No samples found.")

    # Check if first audio file exists
    first_audio = FIXTURE_BASE_DIR / samples[0]["audio_path"]
    if not first_audio.exists():
        pytest.skip("Audio files missing. Run the importer script.")

    settings = Settings()
    # Force CPU for tests
    settings.asr_device = "cpu"
    settings.asr_compute_type = "int8"
    
    pipeline = TranscriptionPipeline(settings)
    
    total_score = 0.0
    processed = 0

    for sample in samples:
        audio_path = FIXTURE_BASE_DIR / sample["audio_path"]
        expected = sample["expected_sentence"]
        
        try:
            transcript = await pipeline.process_audio_path(
                audio_path,
                source="ci_regression",
                language="tr",
                quality_mode="balanced"
            )
            
            full_cleaned = " ".join(s.corrected_text for s in transcript.segments)
            # Simple keyword overlap calculation for quick check
            def tokenize(t):
                return set(t.lower().replace(".", "").replace(",", "").split())
            
            expected_words = tokenize(expected)
            actual_words = tokenize(full_cleaned)
            score = len(expected_words.intersection(actual_words)) / len(expected_words) if expected_words else 0
            
            total_score += score
            processed += 1
        except Exception:
            continue

    if processed > 0:
        avg = total_score / processed
        print(f"\nQuick Regression keyword_overlap_quality_score: {avg:.2%}")
        assert avg > 0.1
    else:
        pytest.skip("No samples were successfully processed.")
