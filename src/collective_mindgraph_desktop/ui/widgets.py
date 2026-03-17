"""Reusable Qt widgets for the application."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..audio_capture import AudioInputDeviceInfo
from ..models import AppSummary
from ..transcription import RealtimeBackendTranscriptionConfig
from ..wake_phrase import DEFAULT_SHUTDOWN_PHRASE, DEFAULT_WAKE_PHRASE


class CardWidget(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CardWidget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        layout.addWidget(title_label)

        self.body_layout = QVBoxLayout()
        self.body_layout.setSpacing(10)
        layout.addLayout(self.body_layout)


class MetricPill(QFrame):
    def __init__(self, label_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MetricPill")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        caption = QLabel(label_text)
        caption.setStyleSheet("color: #5a6b7d;")
        self.value_label = QLabel("0")
        self.value_label.setObjectName("MetricValue")

        layout.addWidget(caption)
        layout.addWidget(self.value_label)

    def set_value(self, value: int) -> None:
        self.value_label.setText(str(value))


class SummaryBar(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SummaryBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        self._metrics = {
            "sessions": MetricPill("Sessions"),
            "active": MetricPill("Active"),
            "transcripts": MetricPill("Transcripts"),
            "nodes": MetricPill("Graph Nodes"),
            "snapshots": MetricPill("Snapshots"),
        }
        for widget in self._metrics.values():
            layout.addWidget(widget)

    def set_summary(self, summary: AppSummary) -> None:
        self._metrics["sessions"].set_value(summary.total_sessions)
        self._metrics["active"].set_value(summary.active_sessions)
        self._metrics["transcripts"].set_value(summary.total_transcripts)
        self._metrics["nodes"].set_value(summary.total_nodes)
        self._metrics["snapshots"].set_value(summary.total_snapshots)


class EmptyStateWidget(QWidget):
    def __init__(self, title: str, message: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setStyleSheet("color: #66788a;")

        layout.addWidget(title_label)
        layout.addWidget(message_label)


class ActionEmptyStateWidget(QWidget):
    def __init__(
        self,
        title: str,
        message: str,
        primary_label: str,
        secondary_label: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setStyleSheet("color: #66788a;")
        message_label.setMaximumWidth(420)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.primary_button = QPushButton(primary_label)
        button_row.addWidget(self.primary_button)

        self.secondary_button: QPushButton | None = None
        if secondary_label:
            self.secondary_button = QPushButton(secondary_label)
            self.secondary_button.setProperty("secondary", True)
            button_row.addWidget(self.secondary_button)

        layout.addWidget(title_label)
        layout.addWidget(message_label)
        layout.addLayout(button_row)


class SessionDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Session")
        self.resize(380, 180)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(10)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Reasoning session title")

        self.device_edit = QLineEdit()
        self.device_edit.setPlaceholderText("e.g. WS-ENG-03")

        self.status_combo = QComboBox()
        self.status_combo.setEditable(True)
        self.status_combo.addItems(["active", "paused", "archived"])
        self.status_combo.setCurrentText("active")

        form_layout.addRow("Title", self.title_edit)
        form_layout.addRow("Device ID", self.device_edit)
        form_layout.addRow("Status", self.status_combo)
        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setProperty("secondary", True)
        self.button_box.accepted.connect(self._validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def values(self) -> tuple[str, str, str]:
        return (
            self.title_edit.text().strip(),
            self.device_edit.text().strip(),
            self.status_combo.currentText().strip().lower(),
        )

    def _validate_and_accept(self) -> None:
        title, device_id, _status = self.values()
        if not title:
            self.title_edit.setFocus()
            return
        if not device_id:
            self.device_edit.setFocus()
            return
        self.accept()


class TranscriptionSettingsDialog(QDialog):
    def __init__(
        self,
        config: RealtimeBackendTranscriptionConfig,
        audio_input_options: list[AudioInputDeviceInfo] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Transcript Settings")
        self.resize(560, 520)
        self._audio_input_options = list(audio_input_options or [])

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(10)

        self.base_url_edit = QLineEdit(config.base_url)
        self.base_url_edit.setPlaceholderText("e.g. http://127.0.0.1:8080")

        self.language_edit = QLineEdit(config.language or "")
        self.language_edit.setPlaceholderText("Blank = backend auto detect")

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 3600)
        self.timeout_spin.setValue(config.request_timeout_seconds)
        self.timeout_spin.setSuffix(" s")

        self.live_stream_checkbox = QCheckBox("Show live transcript while recording")
        self.live_stream_checkbox.setChecked(config.stream_live_transcription)

        self.stream_flush_spin = QSpinBox()
        self.stream_flush_spin.setRange(250, 10_000)
        self.stream_flush_spin.setSingleStep(100)
        self.stream_flush_spin.setValue(config.stream_flush_interval_ms)
        self.stream_flush_spin.setSuffix(" ms")

        self.audio_input_combo = QComboBox()
        self.audio_input_combo.addItem("System default microphone", None)
        selected_index = 0
        for index, option in enumerate(self._audio_input_options, start=1):
            label = f"{option.label} (Default)" if option.is_default else option.label
            self.audio_input_combo.addItem(label, option.device_id)
            if config.audio_input_device_id and option.device_id == config.audio_input_device_id:
                selected_index = index
        if config.audio_input_device_id and selected_index == 0:
            unavailable_label = config.audio_input_device_label or "Unavailable microphone"
            self.audio_input_combo.addItem(f"{unavailable_label} (Unavailable)", config.audio_input_device_id)
            selected_index = self.audio_input_combo.count() - 1
        self.audio_input_combo.setCurrentIndex(selected_index)

        self.auto_stop_checkbox = QCheckBox("Auto-stop after a short silence")
        self.auto_stop_checkbox.setChecked(config.auto_stop_enabled)

        self.auto_stop_min_speech_spin = QDoubleSpinBox()
        self.auto_stop_min_speech_spin.setRange(0.1, 5.0)
        self.auto_stop_min_speech_spin.setSingleStep(0.05)
        self.auto_stop_min_speech_spin.setDecimals(2)
        self.auto_stop_min_speech_spin.setValue(config.auto_stop_min_speech_seconds)
        self.auto_stop_min_speech_spin.setSuffix(" s")

        self.auto_stop_silence_spin = QDoubleSpinBox()
        self.auto_stop_silence_spin.setRange(0.2, 10.0)
        self.auto_stop_silence_spin.setSingleStep(0.1)
        self.auto_stop_silence_spin.setDecimals(2)
        self.auto_stop_silence_spin.setValue(config.auto_stop_silence_seconds)
        self.auto_stop_silence_spin.setSuffix(" s")

        self.auto_stop_threshold_spin = QDoubleSpinBox()
        self.auto_stop_threshold_spin.setRange(0.001, 0.2)
        self.auto_stop_threshold_spin.setSingleStep(0.001)
        self.auto_stop_threshold_spin.setDecimals(3)
        self.auto_stop_threshold_spin.setValue(config.auto_stop_silence_threshold)

        self.wake_enabled_checkbox = QCheckBox("Enable wake trigger on startup")
        self.wake_enabled_checkbox.setChecked(config.wake_trigger_enabled)

        self.wake_phrase_edit = QLineEdit(config.wake_phrase)
        self.wake_phrase_edit.setPlaceholderText("e.g. command wake")

        self.shutdown_phrase_edit = QLineEdit(config.shutdown_phrase)
        self.shutdown_phrase_edit.setPlaceholderText("e.g. command shut")

        self.wake_cooldown_spin = QDoubleSpinBox()
        self.wake_cooldown_spin.setRange(0.2, 10.0)
        self.wake_cooldown_spin.setSingleStep(0.1)
        self.wake_cooldown_spin.setDecimals(1)
        self.wake_cooldown_spin.setValue(config.wake_cooldown_seconds)
        self.wake_cooldown_spin.setSuffix(" s")

        form_layout.addRow("Backend URL", self.base_url_edit)
        form_layout.addRow("Language", self.language_edit)
        form_layout.addRow("Request Timeout", self.timeout_spin)
        form_layout.addRow("Live Transcript", self.live_stream_checkbox)
        form_layout.addRow("Stream Flush Interval", self.stream_flush_spin)
        form_layout.addRow("Microphone Input", self.audio_input_combo)
        form_layout.addRow("Auto-stop", self.auto_stop_checkbox)
        form_layout.addRow("Min Speech Before Auto-stop", self.auto_stop_min_speech_spin)
        form_layout.addRow("Silence Needed to Stop", self.auto_stop_silence_spin)
        form_layout.addRow("Silence Threshold", self.auto_stop_threshold_spin)
        form_layout.addRow("Wake Trigger", self.wake_enabled_checkbox)
        form_layout.addRow("Wake Phrase", self.wake_phrase_edit)
        form_layout.addRow("Shutdown Phrase", self.shutdown_phrase_edit)
        form_layout.addRow("Wake Cooldown", self.wake_cooldown_spin)
        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setProperty("secondary", True)
        self.button_box.accepted.connect(self._validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def config(self) -> RealtimeBackendTranscriptionConfig:
        selected_device_id = self.audio_input_combo.currentData()
        selected_label = self.audio_input_combo.currentText()
        is_default_selection = selected_device_id in (None, "")
        return RealtimeBackendTranscriptionConfig(
            base_url=self.base_url_edit.text().strip().rstrip("/"),
            language=self.language_edit.text().strip() or None,
            request_timeout_seconds=self.timeout_spin.value(),
            stream_live_transcription=self.live_stream_checkbox.isChecked(),
            stream_flush_interval_ms=self.stream_flush_spin.value(),
            audio_input_device_id=None if is_default_selection else str(selected_device_id),
            audio_input_device_label=None if is_default_selection else selected_label,
            auto_stop_enabled=self.auto_stop_checkbox.isChecked(),
            auto_stop_min_speech_seconds=self.auto_stop_min_speech_spin.value(),
            auto_stop_silence_seconds=self.auto_stop_silence_spin.value(),
            auto_stop_silence_threshold=self.auto_stop_threshold_spin.value(),
            wake_trigger_enabled=self.wake_enabled_checkbox.isChecked(),
            wake_phrase=self.wake_phrase_edit.text().strip() or DEFAULT_WAKE_PHRASE,
            shutdown_phrase=self.shutdown_phrase_edit.text().strip() or DEFAULT_SHUTDOWN_PHRASE,
            wake_cooldown_seconds=self.wake_cooldown_spin.value(),
        )

    def _validate_and_accept(self) -> None:
        if not self.base_url_edit.text().strip():
            self.base_url_edit.setFocus()
            return
        if not self.wake_phrase_edit.text().strip():
            self.wake_phrase_edit.setFocus()
            return
        if not self.shutdown_phrase_edit.text().strip():
            self.shutdown_phrase_edit.setFocus()
            return
        self.accept()
