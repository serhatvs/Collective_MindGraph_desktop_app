from __future__ import annotations

import math
from pathlib import Path
import wave

from tools.transcript_annotation.app import AnnotationWindow, parse_args
from tools.transcript_annotation.dataset import AnnotationDataset


def test_annotation_window_opens_dataset_and_saves_human_edit(qtbot, tmp_path: Path):
    audio = tmp_path / "meeting.wav"
    _write_wav(audio)
    dataset = AnnotationDataset.create(tmp_path / "dataset", dataset_name="UI Pilot")
    recording = dataset.add_recording(audio, _transcript())

    window = AnnotationWindow(dataset.root)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.dataset is not None)
    window.recording_list.setCurrentRow(0)
    qtbot.waitUntil(lambda: window.segment_table.rowCount() == 1)
    window.segment_table.selectRow(0)
    qtbot.waitUntil(lambda: window.current_segment_id is not None)

    window.reference_text.setPlainText("İnsan tarafından doğrulandı.")
    window.segment_status.setCurrentText("reviewed")
    window.save_current_segment()

    reloaded = AnnotationDataset.load(dataset.root)
    segment = reloaded.get_segment(recording["recording_id"], recording["segments"][0]["segment_id"])
    assert segment["reference_text"] == "İnsan tarafından doğrulandı."
    assert segment["annotation_status"] == "reviewed"
    assert "Transcript Annotation" in window.windowTitle()
    assert len(window._shortcuts) >= 7


def test_annotation_launcher_argument_accepts_dataset_path():
    args = parse_args(["--dataset", "datasets/transcription/pilot"])

    assert args.dataset == Path("datasets/transcription/pilot")


def test_annotation_navigation_flushes_pending_human_edits(qtbot, tmp_path: Path):
    first_audio = tmp_path / "first.wav"
    second_audio = tmp_path / "second.wav"
    _write_wav(first_audio, frequency=220)
    _write_wav(second_audio, frequency=330)
    dataset = AnnotationDataset.create(tmp_path / "dataset", dataset_name="Navigation Pilot")
    first_recording = dataset.add_recording(first_audio, _navigation_transcript())
    second_recording = dataset.add_recording(second_audio, _navigation_transcript())

    window = AnnotationWindow(dataset.root)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.dataset is not None)
    window.recording_list.setCurrentRow(0)
    qtbot.waitUntil(lambda: window.current_recording_id == first_recording["recording_id"])
    window.segment_table.selectRow(0)
    qtbot.waitUntil(
        lambda: window.current_segment_id == first_recording["segments"][0]["segment_id"]
    )

    window.reference_text.setPlainText("Birinci hızlı düzeltme.")
    assert window._autosave.isActive()
    window.segment_table.selectRow(1)
    qtbot.waitUntil(
        lambda: window.current_segment_id == first_recording["segments"][1]["segment_id"]
    )

    window.reference_text.setPlainText("İkinci hızlı düzeltme.")
    assert window._autosave.isActive()
    window.recording_list.setCurrentRow(1)
    qtbot.waitUntil(lambda: window.current_recording_id == second_recording["recording_id"])

    window.segment_table.selectRow(0)
    qtbot.waitUntil(
        lambda: window.current_segment_id == second_recording["segments"][0]["segment_id"]
    )
    window.reference_text.setPlainText("Veri kümesi geçişinden önceki düzeltme.")
    replacement = AnnotationDataset.create(tmp_path / "replacement", dataset_name="Replacement")
    assert window._set_dataset(replacement) is True

    reloaded = AnnotationDataset.load(dataset.root)
    assert reloaded.get_segment(
        first_recording["recording_id"], first_recording["segments"][0]["segment_id"]
    )["reference_text"] == "Birinci hızlı düzeltme."
    assert reloaded.get_segment(
        first_recording["recording_id"], first_recording["segments"][1]["segment_id"]
    )["reference_text"] == "İkinci hızlı düzeltme."
    assert reloaded.get_segment(
        second_recording["recording_id"], second_recording["segments"][0]["segment_id"]
    )["reference_text"] == "Veri kümesi geçişinden önceki düzeltme."


def _transcript() -> dict:
    return {
        "conversation_id": "ui_fixture",
        "source": "test",
        "metadata": {"asr_status": "ASR_STATUS=OK"},
        "segments": [
            {
                "segment_id": "segment_1",
                "start": 0.0,
                "end": 0.8,
                "raw_text": "insan tarafindan dogrulandi",
                "corrected_text": "İnsan tarafından doğrulandı.",
                "metadata": {},
            }
        ],
    }


def _navigation_transcript() -> dict:
    payload = _transcript()
    payload["segments"].extend(
        [
            {
                "segment_id": "segment_2",
                "start": 0.82,
                "end": 0.95,
                "raw_text": "ikinci bolum",
                "corrected_text": "İkinci bölüm.",
                "metadata": {},
            },
        ]
    )
    return payload


def _write_wav(
    path: Path,
    *,
    duration: float = 1.0,
    sample_rate: int = 16000,
    frequency: int = 220,
) -> None:
    frames = bytearray()
    for index in range(int(duration * sample_rate)):
        value = int(math.sin(2 * math.pi * frequency * index / sample_rate) * 0.1 * 32767)
        frames.extend(value.to_bytes(2, byteorder="little", signed=True))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(bytes(frames))
