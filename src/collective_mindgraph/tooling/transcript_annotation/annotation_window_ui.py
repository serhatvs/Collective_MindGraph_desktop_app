"""Widget construction for the transcript annotation window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from .dataset import ANNOTATION_STATUSES, CONDITION_TAGS


class AnnotationWindowUiMixin:
    """Construct annotation widgets without mixing layout into workflow code."""

    def _build_ui(self) -> None:
        root = QWidget(self)
        root_layout = QVBoxLayout(root)

        actions = QHBoxLayout()
        self.new_button = QPushButton("New Dataset")
        self.open_button = QPushButton("Open Dataset")
        self.add_audio_button = QPushButton("Add Audio")
        self.verify_button = QPushButton("Verify Integrity")
        self.dataset_label = QLabel("No dataset open")
        self.progress_label = QLabel("")
        actions.addWidget(self.new_button)
        actions.addWidget(self.open_button)
        actions.addWidget(self.add_audio_button)
        actions.addWidget(self.verify_button)
        actions.addWidget(self.dataset_label, 1)
        actions.addWidget(self.progress_label)
        root_layout.addLayout(actions)
        self.new_button.clicked.connect(self.create_dataset_dialog)
        self.open_button.clicked.connect(self.open_dataset_dialog)
        self.add_audio_button.clicked.connect(self.add_audio_dialog)
        self.verify_button.clicked.connect(self.verify_integrity)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter, 1)
        recordings_panel = QWidget()
        recordings_layout = QVBoxLayout(recordings_panel)
        recordings_layout.addWidget(QLabel("Recordings"))
        self.recording_list = QListWidget()
        self.recording_list.currentItemChanged.connect(self._on_recording_selected)
        recordings_layout.addWidget(self.recording_list, 1)
        recording_group = QGroupBox("Recording Conditions")
        recording_form = QFormLayout(recording_group)
        self.recording_status = QComboBox()
        self.recording_status.addItems(ANNOTATION_STATUSES)
        self.meeting_id = QLineEdit()
        self.source_name = QLineEdit()
        self.condition_tags = QLineEdit()
        self.condition_tags.setPlaceholderText(", ".join(CONDITION_TAGS[:5]) + ", custom_tag")
        self.microphone_info = QLineEdit()
        self.room_info = QLineEdit()
        self.recording_notes = QPlainTextEdit()
        self.recording_notes.setMaximumHeight(90)
        self.save_recording_button = QPushButton("Save Recording Metadata")
        self.save_recording_button.clicked.connect(self.save_recording_metadata)
        recording_form.addRow("Status", self.recording_status)
        recording_form.addRow("Meeting ID", self.meeting_id)
        recording_form.addRow("Source name", self.source_name)
        recording_form.addRow("Condition tags", self.condition_tags)
        recording_form.addRow("Microphone", self.microphone_info)
        recording_form.addRow("Room", self.room_info)
        recording_form.addRow("Reviewer notes", self.recording_notes)
        recording_form.addRow(self.save_recording_button)
        recordings_layout.addWidget(recording_group)
        splitter.addWidget(recordings_panel)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        self.segment_table = QTableWidget(0, 9)
        self.segment_table.setHorizontalHeaderLabels(
            (
                "#",
                "Status",
                "Start",
                "End",
                "Raw ASR",
                "Selected ASR",
                "Reference",
                "Confidence",
                "Warnings",
            )
        )
        self.segment_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.segment_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.segment_table.itemSelectionChanged.connect(self._on_segment_selected)
        center_layout.addWidget(self.segment_table, 1)

        playback_group = QGroupBox("Local Audio Playback")
        playback_layout = QGridLayout(playback_group)
        self.play_button = QPushButton("Play/Pause")
        self.replay_button = QPushButton("Replay Segment")
        self.previous_button = QPushButton("Previous")
        self.next_button = QPushButton("Next")
        self.slow_checkbox = QCheckBox("0.75×")
        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.setRange(0, 0)
        self.time_label = QLabel("00:00.000 / 00:00.000")
        playback_layout.addWidget(self.play_button, 0, 0)
        playback_layout.addWidget(self.replay_button, 0, 1)
        playback_layout.addWidget(self.previous_button, 0, 2)
        playback_layout.addWidget(self.next_button, 0, 3)
        playback_layout.addWidget(self.slow_checkbox, 0, 4)
        playback_layout.addWidget(self.timeline, 1, 0, 1, 4)
        playback_layout.addWidget(self.time_label, 1, 4)
        self.play_button.clicked.connect(self.toggle_play_pause)
        self.replay_button.clicked.connect(self.replay_current_segment)
        self.previous_button.clicked.connect(lambda: self.move_segment(-1))
        self.next_button.clicked.connect(lambda: self.move_segment(1))
        self.slow_checkbox.toggled.connect(
            lambda checked: self._player.setPlaybackRate(0.75 if checked else 1.0)
        )
        self.timeline.sliderMoved.connect(self._player.setPosition)
        center_layout.addWidget(playback_group)
        splitter.addWidget(center)

        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        boundary_group = QGroupBox("Reviewed Segment")
        boundary_form = QFormLayout(boundary_group)
        self.original_boundary = QLabel("—")
        self.reviewed_start = QDoubleSpinBox()
        self.reviewed_end = QDoubleSpinBox()
        for control in (self.reviewed_start, self.reviewed_end):
            control.setDecimals(3)
            control.setSingleStep(0.05)
            control.setRange(0.0, 24 * 60 * 60)
            control.valueChanged.connect(self._schedule_autosave)
        self.segment_status = QComboBox()
        self.segment_status.addItems(ANNOTATION_STATUSES)
        self.segment_status.currentTextChanged.connect(self._schedule_autosave)
        self.speaker_id = QLineEdit("unknown")
        self.speaker_id.setPlaceholderText("unknown unless supplied by a human")
        self.speaker_id.textChanged.connect(self._schedule_autosave)
        self.boundary_warning = QLabel("")
        self.boundary_warning.setWordWrap(True)
        boundary_form.addRow("Original boundary", self.original_boundary)
        boundary_form.addRow("Reviewed start", self.reviewed_start)
        boundary_form.addRow("Reviewed end", self.reviewed_end)
        boundary_form.addRow("Status", self.segment_status)
        boundary_form.addRow("Human speaker ID", self.speaker_id)
        boundary_form.addRow("Boundary warning", self.boundary_warning)
        editor_layout.addWidget(boundary_group)

        self.raw_text = _read_only_text()
        self.selected_text = _read_only_text()
        self.cleaned_text = _read_only_text()
        self.reference_text = QPlainTextEdit()
        self.reference_text.setPlaceholderText("Write exactly what was spoken; do not summarize.")
        self.reference_text.textChanged.connect(self._schedule_autosave)
        self.segment_notes = QPlainTextEdit()
        self.segment_notes.setMaximumHeight(70)
        self.segment_notes.textChanged.connect(self._schedule_autosave)
        editor_layout.addWidget(_labeled_widget("Original raw ASR", self.raw_text))
        editor_layout.addWidget(_labeled_widget("Selected raw ASR", self.selected_text))
        editor_layout.addWidget(_labeled_widget("Cleaned ASR", self.cleaned_text))
        editor_layout.addWidget(
            _labeled_widget("Human reference", self.reference_text),
            1,
        )
        editor_layout.addWidget(_labeled_widget("Reviewer notes", self.segment_notes))

        status_actions = QHBoxLayout()
        self.save_segment_button = QPushButton("Save Segment")
        self.reviewed_button = QPushButton("Mark Reviewed")
        self.unclear_button = QPushButton("Mark Unclear")
        self.exclude_button = QPushButton("Exclude")
        for button in (
            self.save_segment_button,
            self.reviewed_button,
            self.unclear_button,
            self.exclude_button,
        ):
            status_actions.addWidget(button)
        self.save_segment_button.clicked.connect(self.save_current_segment)
        self.reviewed_button.clicked.connect(lambda: self.set_current_status("reviewed"))
        self.unclear_button.clicked.connect(lambda: self.set_current_status("unclear"))
        self.exclude_button.clicked.connect(lambda: self.set_current_status("excluded"))
        editor_layout.addLayout(status_actions)

        self.segment_warnings = QLabel("")
        self.segment_warnings.setWordWrap(True)
        self.segment_metadata = QPlainTextEdit()
        self.segment_metadata.setReadOnly(True)
        self.segment_metadata.setMaximumHeight(170)
        editor_layout.addWidget(self.segment_warnings)
        editor_layout.addWidget(
            _labeled_widget(
                "Confidence / retranscription metadata",
                self.segment_metadata,
            )
        )
        splitter.addWidget(editor)
        splitter.setSizes([270, 760, 470])
        self.setCentralWidget(root)
        self.statusBar().showMessage("Create or open a local annotation dataset.")

    def _install_shortcuts(self) -> None:
        shortcuts = (
            ("Space", self.toggle_play_pause),
            ("R", self.replay_current_segment),
            ("Alt+Left", lambda: self.move_segment(-1)),
            ("Alt+Right", lambda: self.move_segment(1)),
            ("Ctrl+S", self.save_current_segment),
            ("U", lambda: self.set_current_status("unclear")),
            ("X", lambda: self.set_current_status("excluded")),
        )
        self._shortcuts: list[QShortcut] = []
        for key, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._flush_pending_segment_edit():
            event.ignore()
            return
        if self._worker and self._worker.isRunning():
            QMessageBox.information(
                self,
                "Transcription Running",
                "Wait for local transcription to finish before closing so no work is lost.",
            )
            event.ignore()
            return
        self._player.stop()
        event.accept()


def _read_only_text() -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setReadOnly(True)
    widget.setMaximumHeight(80)
    return widget


def _labeled_widget(label: str, widget: QWidget) -> QGroupBox:
    group = QGroupBox(label)
    layout = QVBoxLayout(group)
    layout.addWidget(widget)
    return group
