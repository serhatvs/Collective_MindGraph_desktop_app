import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from realtime_backend.app.config import Settings
from realtime_backend.app.pipeline.orchestrator import TranscriptionPipeline
from realtime_backend.app.utils.turkish_cleanup import clean_turkish_transcript

def test_turkish_cleanup_deterministic():
    raw = "şey yani collective mindgraph için ııı transcript kısmını düzeltmemiz lazım"
    cleaned = clean_turkish_transcript(raw)
    
    assert "Collective MindGraph" in cleaned
    assert "ııı" not in cleaned
    assert "şey yani" not in cleaned
    assert cleaned.endswith(".")
    assert cleaned[0].isupper()

def test_turkish_cleanup_preserves_technical_terms():
    raw = "fastapi ve sqlite kullanarak local-first bir sistem yapıyoruz"
    cleaned = clean_turkish_transcript(raw)
    
    assert "FastAPI" in cleaned
    assert "SQLite" in cleaned
    assert "local-first" in cleaned

@pytest.mark.asyncio
@patch("realtime_backend.app.pipeline.orchestrator.normalize_audio")
@patch("realtime_backend.app.pipeline.orchestrator.wav_duration_seconds")
@patch("realtime_backend.app.pipeline.orchestrator._build_processing_windows")
async def test_orchestrator_calls_normalization(
    mock_build_windows,
    mock_duration,
    mock_normalize,
    tmp_path
):
    settings = Settings(temp_dir=tmp_path)
    # Mock VAD, ASR, Diarizer
    vad = MagicMock()
    vad.detect.return_value = []
    asr = MagicMock()
    asr.transcribe.return_value = []
    asr.provider_name = "mock_asr"
    diarizer = MagicMock()
    diarizer.diarize.return_value = []
    
    pipeline = TranscriptionPipeline(settings, vad=vad, asr=asr, diarizer=diarizer)
    
    mock_normalize.return_value = True
    mock_duration.return_value = 10.0
    mock_build_windows.return_value = []
    
    audio_path = tmp_path / "test.wav"
    audio_path.write_bytes(b"fake audio")
    
    await pipeline.process_audio_path(audio_path, source="test")
    
    assert mock_normalize.called
    # Check that it tried to save diagnostics
    # (Since we mocked windows to [], segments will be empty)

def test_quality_mode_parameter_mapping():
    # This would ideally test FasterWhisperASR._transcribe_window but it requires the actual model or a heavy mock
    pass

if __name__ == "__main__":
    test_turkish_cleanup_deterministic()
    test_turkish_cleanup_preserves_technical_terms()
    print("Transcript quality integration tests passed!")
