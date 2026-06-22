from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from realtime_backend.app.config import Settings
from realtime_backend.app.pipeline.orchestrator import TranscriptionPipeline
from realtime_backend.app.utils.turkish_cleanup import clean_turkish_transcript


def test_turkish_cleanup_conservative_preserves_fillers():
    raw = "\u015fey yani collective mindgraph i\u00e7in \u0131\u0131\u0131 transcript k\u0131sm\u0131n\u0131 d\u00fczeltmemiz laz\u0131m"
    cleaned = clean_turkish_transcript(raw)

    assert "Collective MindGraph" in cleaned
    assert "\u015fey yani" in cleaned.lower()
    assert "\u0131\u0131\u0131" in cleaned
    assert cleaned.endswith(".")
    assert cleaned[0].isupper()


def test_turkish_cleanup_aggressive_can_remove_fillers():
    raw = "\u015fey yani collective mindgraph i\u00e7in \u0131\u0131\u0131 transcript k\u0131sm\u0131n\u0131 d\u00fczeltmemiz laz\u0131m"
    cleaned = clean_turkish_transcript(raw, mode="aggressive")

    assert "\u015fey" not in cleaned.lower()
    assert "\u0131\u0131\u0131" not in cleaned
    assert "Collective MindGraph" in cleaned


def test_turkish_cleanup_preserves_technical_terms():
    raw = "fastapi ve sqlite kullanarak local-first bir sistem yap\u0131yoruz"
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
    tmp_path: Path,
):
    settings = Settings(temp_dir=tmp_path)
    vad = MagicMock()
    vad.detect.return_value = []
    vad.provider_name = "test_vad"
    asr = MagicMock()
    asr.transcribe.return_value = []
    asr.provider_name = "mock_asr"
    asr.asr_status = "ASR_STATUS=OK"
    asr.mock_fallback_used = False
    diarizer = MagicMock()
    diarizer.diarize.return_value = []

    pipeline = TranscriptionPipeline(settings, vad=vad, asr=asr, diarizer=diarizer)

    mock_normalize.return_value = True
    mock_duration.return_value = 10.0
    mock_build_windows.return_value = []

    audio_path = tmp_path / "test.wav"
    audio_path.write_bytes(b"fake audio")

    transcript = await pipeline.process_audio_path(audio_path, source="test")

    assert mock_normalize.called
    assert transcript.metadata["asr_provider"] == "mock_asr"
    assert transcript.metadata["quality_profile"] == "max_quality"
    assert transcript.metadata["preprocessing_status"] == "ffmpeg_normalized"


def test_quality_mode_parameter_mapping():
    settings = Settings()

    assert settings.transcription_quality_mode == "max_quality"
    assert settings.transcript_cleanup_mode == "conservative"


if __name__ == "__main__":
    test_turkish_cleanup_conservative_preserves_fillers()
    test_turkish_cleanup_aggressive_can_remove_fillers()
    test_turkish_cleanup_preserves_technical_terms()
    test_quality_mode_parameter_mapping()
    print("Transcript quality integration tests passed!")
