"""Voice command panel for the main application window."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..audio_capture import AudioCaptureController
from ..transcription import (
    AmazonNovaTranscriptionConfig,
    AmazonNovaTranscriptionService,
    AmazonNovaTranscriptionSettingsStore,
)
from ..voice_command import VoiceCommandState, VoiceCommandWorkflow
from .widgets import CardWidget, TranscriptionSettingsDialog


class NovaTranscriptionWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        audio_path: str,
        config: AmazonNovaTranscriptionConfig,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._audio_path = audio_path
        self._config = config

    @Slot()
    def run(self) -> None:
        try:
            result = AmazonNovaTranscriptionService(config=self._config).transcribe_file(self._audio_path)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result.text)


class VoiceCommandPanel(QWidget):
    activity_reported = Signal(str)
    transcript_captured = Signal(str)

    def __init__(
        self,
        workflow: VoiceCommandWorkflow | None = None,
        capture_controller: AudioCaptureController | None = None,
        transcription_config: AmazonNovaTranscriptionConfig | None = None,
        settings_store: AmazonNovaTranscriptionSettingsStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._workflow = workflow or VoiceCommandWorkflow()
        self._capture_controller = capture_controller or AudioCaptureController(parent=self)
        self._settings_store = settings_store or AmazonNovaTranscriptionSettingsStore()
        self._transcription_config = transcription_config or self._load_transcription_config()
        self._transcription_thread: QThread | None = None
        self._transcription_worker: NovaTranscriptionWorker | None = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        card = CardWidget("Voice Command")
        root_layout.addWidget(card)

        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        self.status_badge = QLabel()
        self.status_badge.setObjectName("VoiceStatusBadge")
        self.status_badge.setMinimumWidth(128)
        header_row.addWidget(self.status_badge)

        self.pipeline_label = QLabel("Input: spoken command  ->  Output: command text")
        self.pipeline_label.setObjectName("MutedText")
        self.pipeline_label.setWordWrap(True)
        header_row.addWidget(self.pipeline_label, 1)
        card.body_layout.addLayout(header_row)

        self.guidance_label = QLabel()
        self.guidance_label.setObjectName("MutedText")
        self.guidance_label.setWordWrap(True)
        card.body_layout.addWidget(self.guidance_label)

        capture_label = QLabel("Captured Audio")
        capture_label.setObjectName("MutedText")
        card.body_layout.addWidget(capture_label)

        self.capture_path_label = QLabel()
        self.capture_path_label.setObjectName("MutedText")
        self.capture_path_label.setWordWrap(True)
        card.body_layout.addWidget(self.capture_path_label)

        config_label = QLabel("Transcript Settings")
        config_label.setObjectName("MutedText")
        card.body_layout.addWidget(config_label)

        self.config_summary_label = QLabel()
        self.config_summary_label.setObjectName("MutedText")
        self.config_summary_label.setWordWrap(True)
        card.body_layout.addWidget(self.config_summary_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        self.start_button = QPushButton("Start Recording")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setProperty("secondary", True)
        self.transcribe_button = QPushButton("Transcribe")
        self.settings_button = QPushButton("Transcript Settings")
        self.settings_button.setProperty("secondary", True)
        self.clear_button = QPushButton("Clear")
        self.clear_button.setProperty("secondary", True)

        self.start_button.clicked.connect(self._handle_start)
        self.stop_button.clicked.connect(self._handle_stop)
        self.transcribe_button.clicked.connect(self._handle_transcribe)
        self.settings_button.clicked.connect(self._handle_open_settings)
        self.clear_button.clicked.connect(self._handle_clear)
        self._capture_controller.recording_started.connect(self._handle_capture_started)
        self._capture_controller.recording_stopped.connect(self._handle_capture_stopped)
        self._capture_controller.capture_cleared.connect(self._handle_capture_cleared)
        self._capture_controller.error_occurred.connect(self._handle_capture_error)

        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.transcribe_button)
        button_row.addWidget(self.settings_button)
        button_row.addWidget(self.clear_button)
        button_row.addStretch(1)
        card.body_layout.addLayout(button_row)

        transcript_label = QLabel("Transcript Output")
        transcript_label.setObjectName("MutedText")
        card.body_layout.addWidget(transcript_label)

        self.transcript_output = QPlainTextEdit()
        self.transcript_output.setReadOnly(True)
        self.transcript_output.setMinimumHeight(110)
        self.transcript_output.setPlaceholderText(
            "Transcript text will appear here after the transcription step."
        )
        card.body_layout.addWidget(self.transcript_output)

        self._apply_state(self._workflow.state)

    def _handle_start(self) -> None:
        if self._transcription_thread is not None:
            return
        try:
            self._capture_controller.start_recording()
        except ValueError as exc:
            self._apply_state(self._workflow.set_error(str(exc), self._workflow.state.audio_path))
            return
        self._apply_state(self._workflow.start_recording())

    def _handle_stop(self) -> None:
        try:
            self.stop_button.setEnabled(False)
            self._capture_controller.stop_recording()
        except ValueError as exc:
            self._apply_state(self._workflow.set_error(str(exc), self._workflow.state.audio_path))

    def _handle_transcribe(self) -> None:
        audio_path = self._workflow.state.audio_path
        if not audio_path:
            self._apply_state(self._workflow.set_error("Record audio before requesting transcription."))
            return
        if self._transcription_thread is not None:
            return

        self._apply_state(self._workflow.transcribe())
        self._transcription_thread = QThread(self)
        self._transcription_worker = NovaTranscriptionWorker(audio_path, self._transcription_config)
        self._transcription_worker.moveToThread(self._transcription_thread)
        self._transcription_thread.started.connect(self._transcription_worker.run)
        self._transcription_worker.finished.connect(self._handle_transcription_finished)
        self._transcription_worker.failed.connect(self._handle_transcription_failed)
        self._transcription_worker.finished.connect(self._transcription_thread.quit)
        self._transcription_worker.failed.connect(self._transcription_thread.quit)
        self._transcription_thread.finished.connect(self._cleanup_transcription_worker)
        self._transcription_thread.start()

    def _handle_clear(self) -> None:
        if self._transcription_thread is not None:
            return
        self._capture_controller.clear_capture()
        self._apply_state(self._workflow.clear())

    def _handle_open_settings(self) -> None:
        if self._transcription_thread is not None:
            return
        dialog = TranscriptionSettingsDialog(self._transcription_config, self)
        if dialog.exec() != TranscriptionSettingsDialog.DialogCode.Accepted:
            return

        self._transcription_config = dialog.config()
        saved_path = self._settings_store.save(self._transcription_config)
        self._refresh_config_summary()
        self.activity_reported.emit(f"Transcript settings saved to {saved_path}")

    def _apply_state(self, state: VoiceCommandState) -> None:
        self.status_badge.setText(state.status_label)
        self.status_badge.setProperty("stage", state.stage)
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

        self.guidance_label.setText(state.guidance_text)
        self.capture_path_label.setText(state.audio_path or "No audio clip captured yet.")
        self._refresh_config_summary()
        self.transcript_output.setPlainText(state.transcript_text)

        self.start_button.setEnabled(state.start_enabled)
        self.stop_button.setEnabled(state.stop_enabled)
        self.transcribe_button.setEnabled(state.transcribe_enabled)
        self.settings_button.setEnabled(self._transcription_thread is None)
        self.clear_button.setEnabled(state.clear_enabled)

        self.activity_reported.emit(self._activity_message(state))

    def _handle_capture_started(self, output_path: str) -> None:
        self.activity_reported.emit(f"Recording voice command to {output_path}")

    def _handle_capture_stopped(self, output_path: str) -> None:
        self._apply_state(self._workflow.stop_recording(output_path))

    def _handle_capture_cleared(self) -> None:
        self.activity_reported.emit("Voice command capture cleared.")

    def _handle_capture_error(self, message: str) -> None:
        self._apply_state(self._workflow.set_error(message, self._workflow.state.audio_path))

    def _handle_transcription_finished(self, transcript_text: str) -> None:
        self._apply_state(self._workflow.complete_transcription(transcript_text))
        self.transcript_captured.emit(transcript_text)

    def _handle_transcription_failed(self, message: str) -> None:
        self._apply_state(self._workflow.set_error(message, self._workflow.state.audio_path))

    def _cleanup_transcription_worker(self) -> None:
        if self._transcription_worker is not None:
            self._transcription_worker.deleteLater()
        if self._transcription_thread is not None:
            self._transcription_thread.deleteLater()
        self._transcription_worker = None
        self._transcription_thread = None
        self._refresh_config_summary()

    def _load_transcription_config(self) -> AmazonNovaTranscriptionConfig:
        try:
            return self._settings_store.load()
        except Exception:
            return AmazonNovaTranscriptionConfig.from_env()

    def _refresh_config_summary(self) -> None:
        region = self._transcription_config.region_name or "Not set"
        self.config_summary_label.setText(
            (
                f"Region: {region}  |  Model: {self._transcription_config.model_id}\n"
                f"Max Tokens: {self._transcription_config.max_tokens}  |  "
                f"Temp: {self._transcription_config.temperature:.2f}  |  "
                f"Top P: {self._transcription_config.top_p:.2f}"
            )
        )

    @staticmethod
    def _activity_message(state: VoiceCommandState) -> str:
        if state.stage == "recording":
            return "Voice command capture started from the active microphone."
        if state.stage == "audio_ready":
            return f"Audio capture saved to {state.audio_path}"
        if state.stage == "transcribing":
            return "Sending audio to Amazon Nova for transcription."
        if state.stage == "transcript_ready":
            return "Amazon Nova transcription received."
        if state.stage == "error":
            return state.guidance_text
        return "Voice command panel reset."
