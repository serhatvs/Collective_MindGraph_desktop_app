from app.config import Settings
from app.models import SpeechRegion, TranscriptSegment
from app.pipeline import orchestrator as orchestrator_module
from app.pipeline.llm_postprocess import LLMPostProcessor, MockLLMProvider
from app.pipeline.orchestrator import (
    TranscriptionPipeline,
    _build_processing_windows,
    _clip_regions_to_window,
    _replace_timeline_tail,
)
from app.utils.audio import create_temporary_wav_path


class _RuntimeVAD:
    provider_name = "silero"


class _RuntimeASR:
    provider_name = "faster_whisper"
    fallback_provider_name = "mock"
    asr_status = "ASR_STATUS=OK"
    mock_fallback_used = False
    gpu_requested = True
    gpu_loaded = True
    cuda_load_status = "loaded"
    gpu_fallback_happened = False
    gpu_fallback_reason = None


class _RuntimeDiarizer:
    provider_name = "fallback"


def test_build_processing_windows_groups_regions_into_bounded_spans():
    windows = _build_processing_windows(
        total_duration=210.0,
        regions=[
            SpeechRegion(start=4.0, end=18.0),
            SpeechRegion(start=21.0, end=39.0),
            SpeechRegion(start=98.0, end=120.0),
            SpeechRegion(start=125.0, end=154.0),
        ],
        max_window_seconds=45.0,
        overlap_seconds=2.0,
    )

    assert [(round(item.start, 1), round(item.end, 1)) for item in windows] == [
        (2.0, 41.0),
        (96.0, 122.0),
        (123.0, 156.0),
    ]


def test_clip_regions_to_window_offsets_to_local_coordinates():
    clipped = _clip_regions_to_window(
        regions=[
            SpeechRegion(start=8.0, end=12.0),
            SpeechRegion(start=14.0, end=19.0),
            SpeechRegion(start=26.0, end=30.0),
        ],
        window_start=10.0,
        window_end=25.0,
    )

    assert [(item.start, item.end) for item in clipped] == [
        (0.0, 2.0),
        (4.0, 9.0),
    ]


def test_replace_timeline_tail_replaces_boundary_crossing_segments():
    existing = [
        TranscriptSegment(
            segment_id="seg_1",
            start=0.0,
            end=10.0,
            speaker="Speaker_1",
            raw_text="opening",
            corrected_text="opening",
        ),
        TranscriptSegment(
            segment_id="seg_2",
            start=10.0,
            end=16.0,
            speaker="Speaker_2",
            raw_text="replace me",
            corrected_text="replace me",
        ),
    ]
    incoming = [
        TranscriptSegment(
            segment_id="seg_3",
            start=12.0,
            end=18.0,
            speaker="Speaker_2",
            raw_text="fresh",
            corrected_text="fresh",
        )
    ]

    replaced = _replace_timeline_tail(existing, incoming, from_second=12.0)

    assert [item.segment_id for item in replaced] == ["seg_1", "seg_3"]


def test_runtime_status_exposes_immutable_provider_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(
        orchestrator_module,
        "build_asr_diagnostics",
        lambda *_args, **_kwargs: {
            "CUDA available through torch": True,
            "Local LLM enabled": True,
        },
    )
    settings = Settings(data_dir=tmp_path / "data", temp_dir=tmp_path / "temp")
    pipeline = TranscriptionPipeline(
        settings,
        vad=_RuntimeVAD(),
        asr=_RuntimeASR(),
        diarizer=_RuntimeDiarizer(),
        llm_postprocessor=LLMPostProcessor(MockLLMProvider(), batch_size=1),
    )

    status = pipeline.runtime_status()

    assert status.vad_provider == "silero"
    assert status.asr_provider_resolved == "faster_whisper"
    assert status.asr_fallback_provider == "mock"
    assert status.gpu_requested is True
    assert status.gpu_loaded is True
    assert status.llm_provider_resolved == "mock"
    assert status.diagnostics()["LLM provider resolved"] == "mock"


def test_pipeline_normalization_paths_are_unique_and_contained(tmp_path):
    first = create_temporary_wav_path(tmp_path, prefix="pipeline_norm_")
    second = create_temporary_wav_path(tmp_path, prefix="pipeline_norm_")
    try:
        assert first != second
        assert first.parent == tmp_path
        assert second.parent == tmp_path
    finally:
        first.unlink(missing_ok=True)
        second.unlink(missing_ok=True)
