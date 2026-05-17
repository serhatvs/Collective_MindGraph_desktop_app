import json
from pathlib import Path
from realtime_backend.app.models import CorrectionRequest, TranscriptSegment, CorrectionResult
from realtime_backend.app.pipeline.llm_postprocess import _build_prompt, _parse_json_results

def test_turkish_prompt_generation():
    segments = [
        TranscriptSegment(
            segment_id="s1",
            start=0.0,
            end=2.0,
            speaker="SPEAKER_00",
            raw_text="merhaba nasılsınız",
            corrected_text=""
        )
    ]
    request = CorrectionRequest(
        conversation_id="c1",
        language="tr",
        segments=segments
    )
    prompt = _build_prompt(request)
    
    assert "Turkish (tr)" in prompt
    assert "ç, ğ, ı, İ, ö, ş, ü" in prompt
    assert "merhaba nasılsınız" in prompt

def test_turkish_character_preservation_in_json():
    # Test that json.loads handles Turkish characters correctly from LLM response
    content = json.dumps({
        "segments": [
            {
                "segment_id": "s1",
                "corrected_text": "Merhaba, nasılsınız? İyi misiniz?",
                "notes": ["Turkish punctuation added"]
            }
        ]
    }, ensure_ascii=False)
    
    source_segments = [
        TranscriptSegment(
            segment_id="s1",
            start=0.0,
            end=2.0,
            speaker="SPEAKER_00",
            raw_text="merhaba nasılsınız iyi misiniz",
            corrected_text=""
        )
    ]
    
    results = _parse_json_results(content, source_segments)
    assert len(results) == 1
    assert results[0].corrected_text == "Merhaba, nasılsınız? İyi misiniz?"
    assert "ı" in results[0].corrected_text

def test_turkish_end_to_end_logic():
    # Simulate a realistic Turkish transcript with characters, mixed words, and fillers
    raw_turkish_text = "merhaba arkadaşlar bugün yani şey mindgraph projesi hakkında konuşacağız ııı bence bu sistem çok useful olacak"
    
    segments = [
        TranscriptSegment(
            segment_id="s1",
            start=0.0,
            end=5.0,
            speaker="Speaker_1",
            raw_text=raw_turkish_text,
            corrected_text=""
        )
    ]
    
    # Simulate LLM response that cleans fillers but preserves Turkish characters and meaningful mixed words
    # It should NOT translate "useful" to "yararlı" if we want to keep technical mixed speech, 
    # but cleaning it to proper Turkish or keeping it is up to the prompt.
    # The prompt says "Preserve meaning" and "Preserve Turkish characters".
    
    mock_corrected_text = "Merhaba arkadaşlar, bugün MindGraph projesi hakkında konuşacağız. Bence bu sistem çok useful olacak."
    
    content = json.dumps({
        "segments": [
            {
                "segment_id": "s1",
                "corrected_text": mock_corrected_text,
                "notes": ["cleaned fillers", "fixed capitalization"]
            }
        ]
    }, ensure_ascii=False)
    
    results = _parse_json_results(content, segments)
    
    assert len(results) == 1
    assert "ııı" not in results[0].corrected_text
    assert "yani şey" not in results[0].corrected_text
    assert "Merhaba" in results[0].corrected_text
    assert "MindGraph" in results[0].corrected_text
    assert "useful" in results[0].corrected_text # Mixed word preserved
    assert "arkadaşlar" in results[0].corrected_text # Turkish character 'ş' preserved
    
    # Verify raw text is preserved in the original segment if we were to apply this
    updated_segment = segments[0].model_copy(update={"corrected_text": results[0].corrected_text})
    assert updated_segment.raw_text == raw_turkish_text
    assert updated_segment.corrected_text == mock_corrected_text

if __name__ == "__main__":
    test_turkish_prompt_generation()
    test_turkish_character_preservation_in_json()
    test_turkish_end_to_end_logic()
    print("Turkish transcription tests passed!")
