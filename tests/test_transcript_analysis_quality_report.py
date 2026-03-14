from dataclasses import replace

from collective_mindgraph_desktop.database import Database
from collective_mindgraph_desktop.services import CollectiveMindGraphService
from collective_mindgraph_desktop.transcription import TranscriptionResult


def build_service(tmp_path) -> CollectiveMindGraphService:
    return CollectiveMindGraphService(Database(tmp_path / "collective_mindgraph.sqlite3"))


def build_transcription_result(audio_path: str) -> TranscriptionResult:
    return TranscriptionResult(
        text="Speaker_1: hello\nSpeaker_2: ready now",
        model_id="realtime_backend",
        audio_path=audio_path,
        conversation_id="conv_quality_report",
        corrected_text_output=(
            "[00:00.000 - 00:01.000] Speaker_1: Hello.\n"
            "[00:01.000 - 00:02.000] Speaker_2: Ready now."
        ),
        segments=[
            {
                "segment_id": "seg_1",
                "start": 0.0,
                "end": 1.0,
                "speaker": "Speaker_1",
                "raw_text": "hello",
                "corrected_text": "Hello.",
                "confidence": 0.95,
                "speaker_confidence": 0.9,
                "overlap": False,
                "notes": [],
            },
            {
                "segment_id": "seg_2",
                "start": 1.0,
                "end": 2.0,
                "speaker": "Speaker_2",
                "raw_text": "ready now",
                "corrected_text": "Ready now.",
                "confidence": 0.92,
                "speaker_confidence": 0.88,
                "overlap": False,
                "notes": [],
            },
        ],
        quality_report={
            "segment_count": 2,
            "speaker_count": 2,
            "unresolved_segments": 0,
            "overlap_ratio": 0.0,
            "avg_asr_confidence": 0.935,
            "avg_speaker_confidence": 0.89,
            "word_timing_coverage": 1.0,
            "corrected_change_ratio": 0.2,
            "topic_count": 1,
            "action_item_count": 1,
            "decision_count": 1,
            "question_count": 0,
            "summary_present": True,
            "warnings": ["initial warning"],
        },
    )


def test_save_transcript_analysis_corrections_recalculates_quality_report_for_unresolved_speakers(tmp_path):
    service = build_service(tmp_path)
    session = service.ingest_transcription_result(build_transcription_result(str(tmp_path / "sample.wav")))
    detail = service.get_session_detail(session.id)

    assert detail is not None
    transcript = detail.transcripts[-1]
    analysis = detail.transcript_analyses[transcript.id]
    assert analysis.quality_report is not None
    assert analysis.quality_report.unresolved_segments == 0
    assert analysis.quality_report.speaker_count == 2

    service.save_transcript_analysis_corrections(
        transcript.id,
        [
            replace(analysis.segments[0], speaker="Unknown_1"),
            replace(analysis.segments[1], speaker="Unknown_1"),
        ],
    )

    unresolved_detail = service.get_session_detail(session.id)

    assert unresolved_detail is not None
    unresolved_analysis = unresolved_detail.transcript_analyses[transcript.id]

    assert unresolved_analysis.quality_report is not None
    assert unresolved_analysis.quality_report.segment_count == 2
    assert unresolved_analysis.quality_report.speaker_count == 1
    assert unresolved_analysis.quality_report.unresolved_segments == 2
    assert unresolved_analysis.quality_report.corrected_change_ratio == 0.2
    assert unresolved_analysis.quality_report.warnings == ["initial warning"]

    service.save_transcript_analysis_corrections(
        transcript.id,
        [
            replace(unresolved_analysis.segments[0], speaker="Hasan"),
            replace(unresolved_analysis.segments[1], speaker="Ayla"),
        ],
    )

    resolved_detail = service.get_session_detail(session.id)

    assert resolved_detail is not None
    resolved_analysis = resolved_detail.transcript_analyses[transcript.id]

    assert resolved_analysis.quality_report is not None
    assert resolved_analysis.quality_report.segment_count == 2
    assert resolved_analysis.quality_report.speaker_count == 2
    assert resolved_analysis.quality_report.unresolved_segments == 0
    assert resolved_analysis.quality_report.avg_asr_confidence == 0.935
    assert resolved_analysis.quality_report.avg_speaker_confidence == 0.89
