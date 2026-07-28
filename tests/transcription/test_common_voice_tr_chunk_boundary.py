import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from collective_mindgraph.engine.settings import EngineSettings
from collective_mindgraph.infrastructure.transcription.recording_processor import RecordingProcessor

MANIFEST_PATH = Path("tests/transcription/fixtures/expected/common_voice_tr_manifest.json")
FIXTURE_BASE_DIR = Path("tests/transcription/fixtures")


def combine_audio_with_silence(source_paths, target_path, silence_seconds=0.5):
    """Combine multiple audio files into one with silence gaps using ffmpeg."""
    # Build filter_complex string
    # e.g. [0:a]adelay=0|0[a0];[1:a]adelay=500|500[a1];[a0][a1]concat=n=2:v=0:a=1[outa]
    inputs = []
    filters = []
    for i, path in enumerate(source_paths):
        inputs.extend(["-i", str(path)])
        # Note: simple concat for smoke test, delay is optional
        filters.append(f"[{i}:a]")

    filter_str = "".join(filters) + f"concat=n={len(source_paths)}:v=0:a=1[outa]"

    command = (
        ["ffmpeg", "-y"]
        + inputs
        + ["-filter_complex", filter_str, "-map", "[outa]", str(target_path)]
    )
    subprocess.run(command, capture_output=True, check=True)


@pytest.mark.asyncio
async def test_common_voice_tr_chunk_boundary():
    if not MANIFEST_PATH.exists():
        pytest.skip("Common Voice manifest missing.")

    with MANIFEST_PATH.open(encoding="utf-8") as f:
        manifest = json.load(f)

    samples = manifest.get("samples", [])
    if len(samples) < 3:
        pytest.skip("Fewer than 3 samples available for chunk boundary test.")

    # Check if files exist
    audio_paths = [FIXTURE_BASE_DIR / s["audio_path"] for s in samples[:3]]
    if not all(p.exists() for p in audio_paths):
        pytest.skip("Audio files missing. Run the importer script.")

    settings = EngineSettings()
    # Force CPU for tests
    settings.asr_device = "cpu"
    settings.asr_compute_type = "int8"

    # Force smaller windows to trigger chunking logic
    settings.pipeline_max_window_seconds = 5.0
    settings.pipeline_window_overlap_seconds = 1.0

    pipeline = RecordingProcessor(settings)

    with tempfile.TemporaryDirectory() as tmp_dir:
        combined_path = Path(tmp_dir) / "combined_test.wav"
        combine_audio_with_silence(audio_paths, combined_path)

        transcript = await pipeline.process_audio_path(
            combined_path, source="chunk_test", language="tr", quality_mode="balanced"
        )

        assert len(transcript.segments) > 0
        full_text = " ".join(s.corrected_text for s in transcript.segments)
        assert len(full_text.strip()) > 0

        # Verify diagnostics exist
        assert transcript.diagnostics is not None
        assert transcript.diagnostics.chunk_count > 1

        print(f"\nChunk Boundary Test: {transcript.diagnostics.chunk_count} chunks processed.")
