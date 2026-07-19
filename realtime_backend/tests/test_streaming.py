from pathlib import Path

import pytest

from app.config import Settings
from app.models import ConversationTranscript, TranscriptSegment
from app.services.streaming import StreamSession, StreamingTranscriptionService


class StubNormalizer:
    def __init__(self) -> None:
        self.created_paths: list[Path] = []

    def pcm_to_wav(self, pcm_data: bytes, target_path: Path, sample_width_bytes: int) -> Path:
        self.created_paths.append(target_path)
        target_path.write_bytes(b"RIFF" + pcm_data)
        return target_path


class StubPipeline:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.paths_seen_while_processing: list[Path] = []

    async def process_audio_path(self, audio_path: Path, **kwargs) -> ConversationTranscript:
        assert audio_path.exists()
        self.paths_seen_while_processing.append(audio_path)
        if self.error is not None:
            raise self.error
        return ConversationTranscript(
            conversation_id=str(kwargs["conversation_id"]),
            source="stream",
            metadata={"asr_status": "ASR_STATUS=OK"},
        )


class StubStore:
    def __init__(self) -> None:
        self.saved: list[ConversationTranscript] = []

    def save(self, transcript: ConversationTranscript) -> None:
        self.saved.append(transcript)


def build_streaming_service(tmp_path: Path, *, pipeline_error: Exception | None = None):
    normalizer = StubNormalizer()
    pipeline = StubPipeline(error=pipeline_error)
    service = StreamingTranscriptionService(
        settings=Settings(
            temp_dir=tmp_path,
            sample_rate=1,
            channels=1,
            sample_width_bytes=1,
        ),
        pipeline=pipeline,
        normalizer=normalizer,
        store=StubStore(),
    )
    return service, normalizer, pipeline


def test_replace_tail_drops_segments_that_cross_reprocess_boundary():
    existing = [
        TranscriptSegment(
            segment_id="seg_1",
            start=0.0,
            end=2.5,
            speaker="Speaker_1",
            raw_text="opening",
            corrected_text="opening",
        ),
        TranscriptSegment(
            segment_id="seg_2",
            start=2.8,
            end=4.1,
            speaker="Speaker_2",
            raw_text="boundary",
            corrected_text="boundary",
        ),
    ]
    incoming = [
        TranscriptSegment(
            segment_id="seg_3",
            start=2.7,
            end=3.6,
            speaker="Speaker_2",
            raw_text="reprocessed",
            corrected_text="reprocessed",
        )
    ]

    replaced = StreamingTranscriptionService._replace_tail(existing, incoming, from_second=3.0)

    assert [segment.segment_id for segment in replaced] == ["seg_1", "seg_3"]


def test_window_start_uses_bounded_recent_history():
    service = object.__new__(StreamingTranscriptionService)
    service._settings = Settings(
        stream_partial_window_seconds=8.0,
        stream_overlap_seconds=1.5,
    )
    session = StreamSession(conversation_id="conv_1", language="en")
    session.buffer_start_seconds = 0.0
    session.committed_seconds = 20.0

    window_start = service._window_start_seconds(session, buffer_end=24.0, finalize=False)

    assert window_start == 16.0


def test_compact_buffer_keeps_recent_audio_only():
    service = object.__new__(StreamingTranscriptionService)
    service._settings = Settings(
        sample_rate=16_000,
        channels=1,
        sample_width_bytes=2,
        stream_partial_window_seconds=8.0,
        stream_overlap_seconds=1.5,
        stream_buffer_retention_seconds=12.0,
    )
    session = StreamSession(conversation_id="conv_2", language="en")
    bytes_per_second = (
        service._settings.sample_rate * service._settings.channels * service._settings.sample_width_bytes
    )
    session.pcm_buffer = bytearray(b"\x00" * int(bytes_per_second * 20))

    service._compact_buffer(session, buffer_end=20.0)

    assert round(session.buffer_start_seconds, 3) == 8.0
    assert len(session.pcm_buffer) == int(bytes_per_second * 12)


@pytest.mark.asyncio
async def test_flush_removes_temporary_wav_after_success(tmp_path: Path):
    service, normalizer, pipeline = build_streaming_service(tmp_path)
    session = service.create_session(language="tr")
    session.pcm_buffer.extend(b"\x00")

    transcript = await service.flush_partial(session.conversation_id)

    assert transcript.metadata["asr_status"] == "ASR_STATUS=OK"
    assert pipeline.paths_seen_while_processing == normalizer.created_paths
    assert len(normalizer.created_paths) == 1
    assert not normalizer.created_paths[0].exists()
    assert list(tmp_path.glob("*.wav")) == []


@pytest.mark.asyncio
async def test_flush_removes_temporary_wav_when_pipeline_fails(tmp_path: Path):
    service, normalizer, pipeline = build_streaming_service(
        tmp_path,
        pipeline_error=RuntimeError("pipeline failed"),
    )
    session = service.create_session(language="tr")
    session.pcm_buffer.extend(b"\x00")

    with pytest.raises(RuntimeError, match="pipeline failed"):
        await service.flush_partial(session.conversation_id)

    assert pipeline.paths_seen_while_processing == normalizer.created_paths
    assert len(normalizer.created_paths) == 1
    assert not normalizer.created_paths[0].exists()
    assert list(tmp_path.glob("*.wav")) == []


def test_discard_session_is_idempotent(tmp_path: Path):
    service, _normalizer, _pipeline = build_streaming_service(tmp_path)
    session = service.create_session(language="tr")

    service.discard_session(session.conversation_id)
    service.discard_session(session.conversation_id)

    assert service.get_session(session.conversation_id) is None
