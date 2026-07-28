"""Standalone PySide6 application for local transcript annotation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QTableWidgetItem,
)

from .annotation_formatting import confidence_label as _confidence_label
from .annotation_formatting import format_milliseconds as _format_ms
from .annotation_formatting import safe_directory_name as _safe_directory_name
from .annotation_launcher import parse_args as parse_args
from .annotation_window_ui import AnnotationWindowUiMixin
from .dataset import AnnotationDataset, DatasetIntegrityError
from .transcription_worker import TranscriptionWorker

AUDIO_FILTER = "Audio (*.wav *.mp3 *.flac *.m4a *.ogg *.opus *.aac *.wma)"
PROFILES = ("balanced", "max_quality", "bad_mic_recovery", "fast")


class AnnotationWindow(AnnotationWindowUiMixin, QMainWindow):
    def __init__(self, dataset_path: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Collective MindGraph — Transcript Annotation")
        self.resize(1500, 900)
        self.dataset: AnnotationDataset | None = None
        self.current_recording_id: str | None = None
        self.current_segment_id: str | None = None
        self._loading_editor = False
        self._segment_edit_dirty = False
        self._segment_stop_ms: int | None = None
        self._pending_audio: list[Path] = []
        self._pending_profile = "balanced"
        self._pending_copy_audio = False
        self._worker: TranscriptionWorker | None = None
        self._autosave = QTimer(self)
        self._autosave.setSingleShot(True)
        self._autosave.setInterval(650)
        self._autosave.timeout.connect(self.save_current_segment)

        self._audio_output = QAudioOutput(self)
        self._audio_output.setVolume(0.8)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.errorOccurred.connect(self._on_player_error)

        self._build_ui()
        self._install_shortcuts()
        self._set_dataset_controls_enabled(False)
        if dataset_path:
            QTimer.singleShot(0, lambda: self.open_dataset(dataset_path))

    def create_dataset_dialog(self) -> None:
        parent = QFileDialog.getExistingDirectory(self, "Choose Dataset Parent Directory")
        if not parent:
            return
        name, accepted = QInputDialog.getText(self, "Dataset Name", "Dataset name")
        if not accepted or not name.strip():
            return
        try:
            dataset = AnnotationDataset.create(
                Path(parent) / _safe_directory_name(name), dataset_name=name
            )
        except Exception as exc:
            QMessageBox.critical(self, "Cannot Create Dataset", str(exc))
            return
        self._set_dataset(dataset)

    def open_dataset_dialog(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Open Annotation Dataset")
        if directory:
            self.open_dataset(Path(directory))

    def open_dataset(self, path: Path) -> None:
        try:
            dataset = AnnotationDataset.load(path)
        except Exception as exc:
            QMessageBox.critical(self, "Cannot Open Dataset", str(exc))
            return
        if not self._set_dataset(dataset):
            return
        if dataset.load_warnings:
            QMessageBox.warning(self, "Dataset Warnings", "\n".join(dataset.load_warnings[:20]))

    def _set_dataset(self, dataset: AnnotationDataset) -> bool:
        if not self._flush_pending_segment_edit():
            return False
        self._autosave.stop()
        self._segment_edit_dirty = False
        self.dataset = dataset
        self.current_recording_id = None
        self.current_segment_id = None
        self.dataset_label.setText(f"{dataset.manifest['dataset_name']} — {dataset.root}")
        self._set_dataset_controls_enabled(True)
        self.refresh_recording_list()
        self.statusBar().showMessage("Dataset opened. Human edits autosave atomically.")
        return True

    def add_audio_dialog(self) -> None:
        if not self.dataset:
            return
        files, _selected = QFileDialog.getOpenFileNames(
            self, "Add Audio Recordings", "", AUDIO_FILTER
        )
        if not files:
            return
        profile, accepted = QInputDialog.getItem(
            self, "Initial Transcription Profile", "Profile", PROFILES, 0, False
        )
        if not accepted:
            return
        copy_choice = QMessageBox.question(
            self,
            "Copy Audio?",
            "Copy audio into the dataset? Choose No to keep only its path. Original audio is never deleted or overwritten.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        self._pending_audio = [Path(item) for item in files]
        self._pending_profile = profile
        self._pending_copy_audio = copy_choice == QMessageBox.StandardButton.Yes
        self._start_next_transcription()

    def _start_next_transcription(self) -> None:
        if not self.dataset or not self._pending_audio:
            self._worker = None
            self.new_button.setEnabled(True)
            self.open_button.setEnabled(True)
            self._set_dataset_controls_enabled(bool(self.dataset))
            return
        audio_path = self._pending_audio.pop(0)
        self.new_button.setEnabled(False)
        self.open_button.setEnabled(False)
        self._set_dataset_controls_enabled(False)
        self.statusBar().showMessage(
            f"Transcribing {audio_path.name} with {self._pending_profile}…"
        )
        worker = TranscriptionWorker(audio_path, self._pending_profile, self)
        worker.completed.connect(self._transcription_completed)
        worker.failed.connect(self._transcription_failed)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _transcription_completed(self, audio_path: str, transcript: object) -> None:
        assert self.dataset is not None
        try:
            recording = self.dataset.add_recording(
                Path(audio_path),
                transcript,
                initial_profile=self._pending_profile,
                copy_audio=self._pending_copy_audio,
            )
            self.statusBar().showMessage(
                f"Added {Path(audio_path).name}; reference fields remain pending until reviewed."
            )
            self.refresh_recording_list(select_recording=str(recording["recording_id"]))
        except Exception as exc:
            QMessageBox.critical(self, "Cannot Add Recording", str(exc))
        self._start_next_transcription()

    def _transcription_failed(self, audio_path: str, error: str) -> None:
        QMessageBox.critical(
            self,
            "Real Local ASR Unavailable",
            f"{Path(audio_path).name} was not added.\n\n{error}",
        )
        self._start_next_transcription()

    def refresh_recording_list(self, *, select_recording: str | None = None) -> None:
        if not self.dataset:
            return
        selected = select_recording or self.current_recording_id
        self.recording_list.clear()
        for recording in self.dataset.recordings:
            segments = recording.get("segments", [])
            reviewed = sum(item.get("annotation_status") == "reviewed" for item in segments)
            item = QListWidgetItem(
                f"[{recording.get('annotation_status', 'pending')}] {recording.get('source_name')}  ({reviewed}/{len(segments)})"
            )
            item.setData(Qt.ItemDataRole.UserRole, recording["recording_id"])
            self.recording_list.addItem(item)
            if recording["recording_id"] == selected:
                self.recording_list.setCurrentItem(item)
        stats = self.dataset.manifest.get("annotation_statistics", {})
        self.progress_label.setText(
            f"Segments reviewed: {stats.get('segments_by_status', {}).get('reviewed', 0)}/{stats.get('segment_count', 0)}"
        )

    def _on_recording_selected(
        self, current: QListWidgetItem | None, previous: QListWidgetItem | None
    ) -> None:
        if not self.dataset or current is None:
            return
        if not self._flush_pending_segment_edit():
            if previous is not None:
                with QSignalBlocker(self.recording_list):
                    self.recording_list.setCurrentItem(previous)
            return
        self.current_recording_id = str(current.data(Qt.ItemDataRole.UserRole))
        recording = self.dataset.get_recording(self.current_recording_id)
        self.current_segment_id = None
        self.recording_status.setCurrentText(str(recording.get("annotation_status") or "pending"))
        self.meeting_id.setText(str(recording.get("meeting_id") or self.current_recording_id))
        self.source_name.setText(str(recording.get("source_name") or ""))
        self.condition_tags.setText(", ".join(recording.get("recording_condition_tags") or []))
        self.microphone_info.setText(str(recording.get("microphone_information") or ""))
        self.room_info.setText(str(recording.get("room_information") or ""))
        self.recording_notes.setPlainText(str(recording.get("reviewer_notes") or ""))
        audio_path = self.dataset.resolve_audio_path(recording)
        self._player.stop()
        self._player.setSource(QUrl.fromLocalFile(str(audio_path)))
        self._populate_segments(recording)

    def _populate_segments(self, recording: dict[str, Any]) -> None:
        segments = recording.get("segments", [])
        self.segment_table.setRowCount(len(segments))
        for row, segment in enumerate(segments):
            values = (
                str(row + 1),
                str(segment.get("annotation_status") or "pending"),
                f"{float(segment.get('reviewed_start') or 0.0):.3f}",
                f"{float(segment.get('reviewed_end') or 0.0):.3f}",
                str(segment.get("raw_asr_text") or ""),
                str(segment.get("selected_asr_text") or ""),
                str(segment.get("reference_text") or ""),
                _confidence_label(segment),
                "; ".join([*segment.get("warnings", []), *segment.get("boundary_warnings", [])]),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, segment["segment_id"])
                self.segment_table.setItem(row, column, item)
        self.segment_table.resizeColumnsToContents()
        if segments:
            self.segment_table.selectRow(0)

    def _on_segment_selected(self) -> None:
        if not self.dataset or not self.current_recording_id:
            return
        selected_rows = self.segment_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        segment_id = str(self.segment_table.item(row, 0).data(Qt.ItemDataRole.UserRole))
        previous_segment_id = self.current_segment_id
        if not self._flush_pending_segment_edit():
            previous_row = self._segment_row(previous_segment_id)
            if previous_row >= 0:
                with QSignalBlocker(self.segment_table):
                    self.segment_table.selectRow(previous_row)
            return
        self.current_segment_id = segment_id
        segment = self.dataset.get_segment(self.current_recording_id, segment_id)
        recording = self.dataset.get_recording(self.current_recording_id)
        self._loading_editor = True
        try:
            self.original_boundary.setText(
                f"{float(segment['original_start']):.3f} — {float(segment['original_end']):.3f} seconds (immutable)"
            )
            with (
                QSignalBlocker(self.reviewed_start),
                QSignalBlocker(self.reviewed_end),
                QSignalBlocker(self.segment_status),
                QSignalBlocker(self.speaker_id),
                QSignalBlocker(self.reference_text),
                QSignalBlocker(self.segment_notes),
            ):
                maximum = max(0.001, float(recording.get("duration") or 24 * 60 * 60))
                self.reviewed_start.setMaximum(maximum)
                self.reviewed_end.setMaximum(maximum)
                self.reviewed_start.setValue(float(segment["reviewed_start"]))
                self.reviewed_end.setValue(float(segment["reviewed_end"]))
                self.segment_status.setCurrentText(str(segment["annotation_status"]))
                self.speaker_id.setText(str(segment.get("speaker_id") or "unknown"))
                self.reference_text.setPlainText(str(segment.get("reference_text") or ""))
                self.segment_notes.setPlainText(str(segment.get("reviewer_notes") or ""))
            self.raw_text.setPlainText(str(segment.get("raw_asr_text") or ""))
            self.selected_text.setPlainText(str(segment.get("selected_asr_text") or ""))
            self.cleaned_text.setPlainText(str(segment.get("cleaned_asr_text") or ""))
            self.boundary_warning.setText(
                "; ".join(segment.get("boundary_warnings") or []) or "None"
            )
            warnings = [*segment.get("warnings", []), *segment.get("boundary_warnings", [])]
            self.segment_warnings.setText(
                "Warnings: " + ("; ".join(warnings) if warnings else "none")
            )
            self.segment_metadata.setPlainText(
                json.dumps(
                    {
                        "confidence": segment.get("confidence_metadata"),
                        "selective_retranscription": segment.get(
                            "selective_retranscription_metadata"
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            self._segment_stop_ms = int(float(segment["reviewed_end"]) * 1000)
        finally:
            self._loading_editor = False
        self._segment_edit_dirty = False

    def _schedule_autosave(self, *_args: object) -> None:
        if not self._loading_editor and self.current_segment_id:
            self._segment_edit_dirty = True
            self._autosave.start()

    def _flush_pending_segment_edit(self) -> bool:
        if not self._segment_edit_dirty:
            return True
        self._autosave.stop()
        return self.save_current_segment()

    def save_current_segment(self) -> bool:
        if (
            self._loading_editor
            or not self.dataset
            or not self.current_recording_id
            or not self.current_segment_id
        ):
            return False
        self._autosave.stop()
        recording_id = self.current_recording_id
        segment_id = self.current_segment_id
        status = self.segment_status.currentText()
        reference = self.reference_text.toPlainText()
        if status == "reviewed" and not reference.strip():
            self.statusBar().showMessage(
                "A reviewed segment must have non-empty human reference text."
            )
            return False
        try:
            warnings = self.dataset.update_segment(
                recording_id,
                segment_id,
                reference_text=reference,
                reviewed_start=self.reviewed_start.value(),
                reviewed_end=self.reviewed_end.value(),
                annotation_status=status,
                reviewer_notes=self.segment_notes.toPlainText(),
                exclusion_reason="excluded by reviewer" if status == "excluded" else "",
                speaker_id=self.speaker_id.text(),
            )
        except DatasetIntegrityError as exc:
            self.statusBar().showMessage(str(exc))
            return False
        self._segment_edit_dirty = False
        self.boundary_warning.setText("; ".join(warnings) or "None")
        self.statusBar().showMessage(
            "Segment autosaved atomically; original ASR fields were not changed."
        )
        recording = self.dataset.get_recording(recording_id)
        segment = self.dataset.get_segment(recording_id, segment_id)
        row = self._segment_row(segment_id)
        if row >= 0:
            values = (
                str(row + 1),
                str(segment.get("annotation_status") or "pending"),
                f"{float(segment.get('reviewed_start') or 0.0):.3f}",
                f"{float(segment.get('reviewed_end') or 0.0):.3f}",
                str(segment.get("raw_asr_text") or ""),
                str(segment.get("selected_asr_text") or ""),
                str(segment.get("reference_text") or ""),
                _confidence_label(segment),
                "; ".join([*segment.get("warnings", []), *segment.get("boundary_warnings", [])]),
            )
            for column, value in enumerate(values):
                self.segment_table.item(row, column).setText(value)
        reviewed = sum(
            item.get("annotation_status") == "reviewed" for item in recording.get("segments", [])
        )
        for index in range(self.recording_list.count()):
            item = self.recording_list.item(index)
            if str(item.data(Qt.ItemDataRole.UserRole)) == recording_id:
                item.setText(
                    f"[{recording.get('annotation_status', 'pending')}] {recording.get('source_name')}  "
                    f"({reviewed}/{len(recording.get('segments', []))})"
                )
                break
        stats = self.dataset.manifest.get("annotation_statistics", {})
        self.progress_label.setText(
            f"Segments reviewed: {stats.get('segments_by_status', {}).get('reviewed', 0)}/{stats.get('segment_count', 0)}"
        )
        return True

    def _segment_row(self, segment_id: str | None) -> int:
        if not segment_id:
            return -1
        for row in range(self.segment_table.rowCount()):
            item = self.segment_table.item(row, 0)
            if item is not None and str(item.data(Qt.ItemDataRole.UserRole)) == segment_id:
                return row
        return -1

    def set_current_status(self, status: str) -> None:
        if not self.current_segment_id:
            return
        self.segment_status.setCurrentText(status)
        self.save_current_segment()

    def save_recording_metadata(self) -> None:
        if not self.dataset or not self.current_recording_id:
            return
        tags = [item.strip() for item in self.condition_tags.text().replace(";", ",").split(",")]
        self.dataset.update_recording(
            self.current_recording_id,
            annotation_status=self.recording_status.currentText(),
            condition_tags=tags,
            microphone_information=self.microphone_info.text(),
            room_information=self.room_info.text(),
            reviewer_notes=self.recording_notes.toPlainText(),
            meeting_id=self.meeting_id.text(),
            source_name=self.source_name.text(),
        )
        self.refresh_recording_list(select_recording=self.current_recording_id)
        self.statusBar().showMessage("Recording metadata saved.")

    def verify_integrity(self) -> None:
        if not self.dataset:
            return
        report = self.dataset.integrity_report(verify_hashes=True)
        text = json.dumps(report, ensure_ascii=False, indent=2)
        if report["valid"]:
            QMessageBox.information(self, "Dataset Integrity", text)
        else:
            QMessageBox.warning(self, "Dataset Integrity Problems", text)

    def toggle_play_pause(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._segment_stop_ms = None
            self._player.play()

    def replay_current_segment(self) -> None:
        if not self.current_segment_id:
            return
        self._player.setPosition(int(self.reviewed_start.value() * 1000))
        self._segment_stop_ms = int(self.reviewed_end.value() * 1000)
        self._player.play()

    def move_segment(self, offset: int) -> None:
        row_count = self.segment_table.rowCount()
        if not row_count:
            return
        row = self.segment_table.currentRow()
        next_row = min(row_count - 1, max(0, row + offset))
        self.segment_table.selectRow(next_row)

    def _on_position_changed(self, position: int) -> None:
        if not self.timeline.isSliderDown():
            self.timeline.setValue(position)
        self.time_label.setText(f"{_format_ms(position)} / {_format_ms(self._player.duration())}")
        if self._segment_stop_ms is not None and position >= self._segment_stop_ms:
            self._player.pause()
            self._segment_stop_ms = None

    def _on_duration_changed(self, duration: int) -> None:
        self.timeline.setRange(0, max(0, duration))
        self.time_label.setText(f"{_format_ms(self._player.position())} / {_format_ms(duration)}")

    def _on_player_error(self, _error: QMediaPlayer.Error, error_text: str) -> None:
        if error_text:
            self.statusBar().showMessage(f"Audio playback error: {error_text}")

    def _set_dataset_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.add_audio_button,
            self.verify_button,
            self.recording_list,
            self.segment_table,
            self.save_recording_button,
            self.save_segment_button,
            self.reviewed_button,
            self.unclear_button,
            self.exclude_button,
            self.play_button,
            self.replay_button,
        ):
            widget.setEnabled(enabled)
