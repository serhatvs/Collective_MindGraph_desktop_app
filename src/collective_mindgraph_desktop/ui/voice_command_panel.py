"""Voice command panel for the main application window."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..audio_capture import AudioCaptureController
from ..backend_runtime import LocalBackendManager
from ..live_transcription import LiveTranscriptStreamController
from ..transcription import (
    BackendHealthStatus,
    RealtimeBackendTranscriptionConfig,
    RealtimeBackendTranscriptionService,
    RealtimeBackendTranscriptionSettingsStore,
    StreamingTranscriptionUpdate,
    TranscriptionResult,
)
from ..voice_command import VoiceCommandState, VoiceCommandWorkflow
from ..wake_phrase import VoskWakePhraseController, WakePhraseConfig, describe_stream_input_device
from .widgets import CardWidget, TranscriptionSettingsDialog


class BackendTranscriptionWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        audio_path: str,
        config: RealtimeBackendTranscriptionConfig,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._audio_path = audio_path
        self._config = config

    @Slot()
    def run(self) -> None:
        try:
            result = RealtimeBackendTranscriptionService(config=self._config).transcribe_file(self._audio_path)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class BackendHealthWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        config: RealtimeBackendTranscriptionConfig,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config

    @Slot()
    def run(self) -> None:
        try:
            result = RealtimeBackendTranscriptionService(config=self._config).fetch_health()
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class VoiceCommandPanel(QWidget):
    activity_reported = Signal(str)
    transcript_captured = Signal(object)

    def __init__(
        self,
        workflow: VoiceCommandWorkflow | None = None,
        capture_controller: AudioCaptureController | None = None,
        transcription_config: RealtimeBackendTranscriptionConfig | None = None,
        settings_store: RealtimeBackendTranscriptionSettingsStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._workflow = workflow or VoiceCommandWorkflow()
        self._settings_store = settings_store or RealtimeBackendTranscriptionSettingsStore()
        self._transcription_config = transcription_config or self._load_transcription_config()
        self._capture_controller = capture_controller or AudioCaptureController(parent=self)
        self._transcription_thread: QThread | None = None
        self._transcription_worker: BackendTranscriptionWorker | None = None
        self._health_thread: QThread | None = None
        self._health_worker: BackendHealthWorker | None = None
        self._backend_health: BackendHealthStatus | None = None
        self._backend_health_retry_after_start = False
        self._backend_status_override: str | None = None
        self._wake_phrase_controller = VoskWakePhraseController(parent=self)
        self._live_stream_controller = LiveTranscriptStreamController(parent=self)
        self._backend_manager = LocalBackendManager(parent=self)
        self._backend_health_timer = QTimer(self)
        self._backend_health_timer.setInterval(15000)
        self._backend_health_timer.timeout.connect(self._refresh_backend_health)
        self._live_stream_attempted = False
        self._live_stream_failed = False
        self._live_stream_finalizing = False
        self._transcription_config = self._apply_runtime_config(self._transcription_config, emit_activity=False)

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

        self.pipeline_label = QLabel("Input: recorded speech  ->  Local backend transcript  ->  Session")
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

        config_label = QLabel("Transcription Backend")
        config_label.setObjectName("MutedText")
        card.body_layout.addWidget(config_label)

        self.config_summary_label = QLabel()
        self.config_summary_label.setObjectName("MutedText")
        self.config_summary_label.setWordWrap(True)
        card.body_layout.addWidget(self.config_summary_label)

        backend_label = QLabel("Backend Runtime")
        backend_label.setObjectName("MutedText")
        card.body_layout.addWidget(backend_label)

        self.provider_status_label = QLabel("Checking backend providers...")
        self.provider_status_label.setObjectName("MutedText")
        self.provider_status_label.setWordWrap(True)
        card.body_layout.addWidget(self.provider_status_label)

        wake_label = QLabel("Wake Trigger")
        wake_label.setObjectName("MutedText")
        card.body_layout.addWidget(wake_label)

        self.wake_status_label = QLabel()
        self.wake_status_label.setObjectName("MutedText")
        self.wake_status_label.setWordWrap(True)
        card.body_layout.addWidget(self.wake_status_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        self.start_button = QPushButton("Start Recording")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setProperty("secondary", True)
        self.transcribe_button = QPushButton("Retry Transcribe")
        self.wake_toggle_button = QPushButton("Disable Wake Trigger")
        self.wake_toggle_button.setProperty("secondary", True)
        self.settings_button = QPushButton("Backend Settings")
        self.settings_button.setProperty("secondary", True)
        self.refresh_backend_button = QPushButton("Refresh Backend")
        self.refresh_backend_button.setProperty("secondary", True)
        self.clear_button = QPushButton("Clear")
        self.clear_button.setProperty("secondary", True)

        self.start_button.clicked.connect(self._handle_start)
        self.stop_button.clicked.connect(self._handle_stop)
        self.transcribe_button.clicked.connect(self._handle_transcribe)
        self.wake_toggle_button.clicked.connect(self._handle_toggle_wake_trigger)
        self.settings_button.clicked.connect(self._handle_open_settings)
        self.refresh_backend_button.clicked.connect(lambda: self._refresh_backend_health(auto_start=True))
        self.clear_button.clicked.connect(self._handle_clear)
        self._capture_controller.recording_started.connect(self._handle_capture_started)
        self._capture_controller.recording_stopped.connect(self._handle_capture_stopped)
        self._capture_controller.recording_auto_stopped.connect(self._handle_capture_auto_stopped)
        self._capture_controller.capture_cleared.connect(self._handle_capture_cleared)
        self._capture_controller.error_occurred.connect(self._handle_capture_error)
        self._wake_phrase_controller.wake_requested.connect(self._handle_wake_requested)
        self._wake_phrase_controller.shutdown_requested.connect(self._handle_shutdown_requested)
        self._wake_phrase_controller.state_changed.connect(self._handle_wake_state_changed)
        self._wake_phrase_controller.error_occurred.connect(self._handle_wake_error)
        self._live_stream_controller.partial_received.connect(self._handle_live_partial_received)
        self._live_stream_controller.finalized.connect(self._handle_live_finalized)
        self._live_stream_controller.failed.connect(self._handle_live_failed)
        self._live_stream_controller.state_changed.connect(self._handle_live_state_changed)
        self._backend_manager.state_changed.connect(self._handle_backend_manager_state_changed)
        self._backend_manager.error_occurred.connect(self._handle_backend_manager_error)

        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.transcribe_button)
        button_row.addWidget(self.wake_toggle_button)
        button_row.addWidget(self.settings_button)
        button_row.addWidget(self.refresh_backend_button)
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
            "Transcript text from the local backend will appear here after transcription."
        )
        card.body_layout.addWidget(self.transcript_output)

        self.processing_hint_label = QLabel()
        self.processing_hint_label.setObjectName("MutedText")
        self.processing_hint_label.setWordWrap(True)
        card.body_layout.addWidget(self.processing_hint_label)

        self._apply_state(self._workflow.state)
        self._backend_health_timer.start()
        QTimer.singleShot(0, lambda: self._refresh_backend_health(auto_start=True))

    def _handle_start(self) -> None:
        if self._transcription_thread is not None:
            return
        self._live_stream_attempted = False
        self._live_stream_failed = False
        self._live_stream_finalizing = False
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
        self._transcription_worker = BackendTranscriptionWorker(audio_path, self._transcription_config)
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
        self._cancel_live_stream()
        self._capture_controller.clear_capture()
        self._apply_state(self._workflow.clear())

    def _handle_open_settings(self) -> None:
        if self._transcription_thread is not None:
            return
        dialog = TranscriptionSettingsDialog(
            self._transcription_config,
            audio_input_options=self._capture_controller.available_audio_inputs(),
            parent=self,
        )
        if dialog.exec() != TranscriptionSettingsDialog.DialogCode.Accepted:
            return

        self._transcription_config = self._apply_runtime_config(dialog.config())
        saved_path = self._settings_store.save(self._transcription_config)
        self._refresh_config_summary()
        self.activity_reported.emit(f"Transcript settings saved to {saved_path}")
        self._refresh_backend_health(auto_start=True)

    def _apply_state(self, state: VoiceCommandState) -> None:
        self.status_badge.setText(state.status_label)
        self.status_badge.setProperty("stage", state.stage)
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

        self.guidance_label.setText(state.guidance_text)
        self.capture_path_label.setText(state.audio_path or "No audio clip captured yet.")
        self._refresh_config_summary()
        self.transcript_output.setPlainText(state.transcript_text)
        self.processing_hint_label.setText(self._processing_hint(state))
        self.wake_status_label.setText(self._wake_phrase_controller.status_text())
        self.provider_status_label.setText(self._backend_status_text())

        self.start_button.setEnabled(state.start_enabled)
        self.stop_button.setEnabled(state.stop_enabled)
        self.transcribe_button.setEnabled(state.transcribe_enabled)
        self.wake_toggle_button.setText(
            "Disable Wake Trigger" if self._wake_phrase_controller.is_armed else "Enable Wake Trigger"
        )
        self.wake_toggle_button.setEnabled(self._transcription_thread is None and self._wake_phrase_controller.is_available)
        self.settings_button.setEnabled(self._transcription_thread is None)
        self.refresh_backend_button.setEnabled(self._health_thread is None)
        self.clear_button.setEnabled(state.clear_enabled)

        self.activity_reported.emit(self._activity_message(state))

    def _handle_capture_started(self, output_path: str) -> None:
        self.activity_reported.emit(f"Recording voice command to {output_path}")
        if not self._transcription_config.stream_live_transcription:
            return
        try:
            self._live_stream_controller.start(output_path, self._transcription_config)
            self._live_stream_attempted = True
            self._live_stream_failed = False
        except Exception as exc:
            self._live_stream_attempted = False
            self._live_stream_failed = True
            self.activity_reported.emit(f"Live transcript stream could not start. Falling back to final upload. {exc}")

    def _handle_capture_stopped(self, output_path: str) -> None:
        self._apply_state(self._workflow.stop_recording(output_path))
        if self._live_stream_attempted and self._live_stream_controller.is_active and not self._live_stream_failed:
            self._live_stream_finalizing = True
            self._apply_state(self._workflow.transcribe())
            self._live_stream_controller.finalize()
            return
        QTimer.singleShot(0, self._handle_transcribe)

    def _handle_capture_auto_stopped(self, output_path: str) -> None:
        self.activity_reported.emit(
            f"Silence detected. Recording stopped automatically and will be transcribed from {output_path}"
        )

    def _handle_capture_cleared(self) -> None:
        self.activity_reported.emit("Voice command capture cleared.")

    def _handle_capture_error(self, message: str) -> None:
        self._cancel_live_stream()
        self._apply_state(self._workflow.set_error(message, self._workflow.state.audio_path))

    def _handle_transcription_finished(self, result: TranscriptionResult) -> None:
        self._complete_transcription_result(result)

    def _handle_transcription_failed(self, message: str) -> None:
        self._apply_state(self._workflow.set_error(message, self._workflow.state.audio_path))
        self._refresh_backend_health(auto_start=True)

    def _handle_toggle_wake_trigger(self) -> None:
        self._wake_phrase_controller.toggle_armed()
        self._apply_state(self._workflow.state)
        if self._wake_phrase_controller.is_armed:
            self.activity_reported.emit("Wake trigger armed.")
            return
        self.activity_reported.emit("Wake trigger disabled. Use the button or restart to re-arm it.")

    def _handle_wake_requested(self, recognized_text: str) -> None:
        if self._transcription_thread is not None:
            return
        if self._workflow.state.stage == "recording":
            return
        self.activity_reported.emit(f"Wake phrase detected: {recognized_text}")
        self._handle_start()

    def _handle_shutdown_requested(self, recognized_text: str) -> None:
        if self._workflow.state.stage == "recording":
            self._cancel_live_stream()
            self._capture_controller.clear_capture()
            self._apply_state(self._workflow.clear())
            self.activity_reported.emit(
                f"Shutdown phrase detected: {recognized_text}. Active voice turn was cancelled."
            )
            return
        if self._workflow.state.stage == "transcribing":
            self.activity_reported.emit(
                f"Shutdown phrase detected: {recognized_text}. Current transcription will finish, "
                "but the wake trigger stays armed."
            )
            return
        self._apply_state(self._workflow.state)
        self.activity_reported.emit(
            f"Shutdown phrase detected: {recognized_text}. Wake trigger remains armed."
        )

    def _handle_wake_state_changed(self, _message: str) -> None:
        self._apply_state(self._workflow.state)

    def _handle_wake_error(self, message: str) -> None:
        self.activity_reported.emit(message)
        self._apply_state(self._workflow.state)

    def _handle_live_partial_received(self, update: StreamingTranscriptionUpdate) -> None:
        live_text = update.corrected_text_output or update.text
        if live_text:
            self.transcript_output.setPlainText(live_text)

    def _handle_live_finalized(self, result: TranscriptionResult) -> None:
        self._live_stream_attempted = False
        self._live_stream_failed = False
        self._live_stream_finalizing = False
        self._complete_transcription_result(result)

    def _handle_live_failed(self, message: str) -> None:
        self._live_stream_attempted = False
        self._live_stream_failed = True
        was_waiting_for_final = self._live_stream_finalizing
        self._live_stream_finalizing = False
        self.activity_reported.emit(f"{message} Falling back to final file upload.")
        if was_waiting_for_final and self._workflow.state.audio_path and self._transcription_thread is None:
            self._apply_state(self._workflow.stop_recording(self._workflow.state.audio_path))
            QTimer.singleShot(0, self._handle_transcribe)

    def _handle_live_state_changed(self, message: str) -> None:
        if message:
            self.activity_reported.emit(message)

    def _handle_backend_health_finished(self, result: BackendHealthStatus) -> None:
        self._backend_health = result
        self._backend_health_retry_after_start = False
        self._backend_status_override = None
        self._apply_state(self._workflow.state)

    def _handle_backend_health_failed(self, message: str) -> None:
        self._backend_health = None
        if self._backend_health_retry_after_start:
            self._backend_health_retry_after_start = False
            self._backend_status_override = None
            self.provider_status_label.setText(self._backend_status_text(message))
            self.activity_reported.emit(message)
            self._apply_state(self._workflow.state)
            return

        if self._backend_manager.can_manage(self._transcription_config.base_url):
            started = self._backend_manager.ensure_running(self._transcription_config.base_url)
            if started:
                self._backend_health_retry_after_start = True
                self._backend_status_override = "Starting local backend and retrying health check..."
                self.provider_status_label.setText(self._backend_status_text())
                QTimer.singleShot(2000, lambda: self._refresh_backend_health(auto_start=False))
                return

        self._backend_status_override = None
        self.provider_status_label.setText(self._backend_status_text(message))
        self.activity_reported.emit(message)
        self._apply_state(self._workflow.state)

    def _handle_backend_manager_state_changed(self, message: str) -> None:
        self.activity_reported.emit(message)

    def _handle_backend_manager_error(self, message: str) -> None:
        self.activity_reported.emit(message)

    def _cleanup_transcription_worker(self) -> None:
        if self._transcription_worker is not None:
            self._transcription_worker.deleteLater()
        if self._transcription_thread is not None:
            self._transcription_thread.deleteLater()
        self._transcription_worker = None
        self._transcription_thread = None
        self._refresh_config_summary()
        self._apply_state(self._workflow.state)

    def _cleanup_health_worker(self) -> None:
        if self._health_worker is not None:
            self._health_worker.deleteLater()
        if self._health_thread is not None:
            self._health_thread.deleteLater()
        self._health_worker = None
        self._health_thread = None
        self._apply_state(self._workflow.state)

    def _load_transcription_config(self) -> RealtimeBackendTranscriptionConfig:
        try:
            return self._settings_store.load()
        except Exception:
            return RealtimeBackendTranscriptionConfig.from_env()

    def _refresh_config_summary(self) -> None:
        selected_input = self._capture_controller.selected_audio_input()
        microphone_label = (
            self._transcription_config.audio_input_device_label
            or (selected_input.label if selected_input is not None else "No microphone")
        )
        if self._transcription_config.audio_input_device_id is None and selected_input is not None:
            microphone_label = f"System default ({selected_input.label})"
        stream_mode = "live + final" if self._transcription_config.stream_live_transcription else "final only"
        auto_stop_mode = (
            f"on, {self._transcription_config.auto_stop_silence_seconds:.2f}s silence, "
            f"threshold {self._transcription_config.auto_stop_silence_threshold:.3f}"
            if self._transcription_config.auto_stop_enabled
            else "off"
        )
        wake_mode = (
            f"on, '{self._transcription_config.wake_phrase}' / '{self._transcription_config.shutdown_phrase}'"
            if self._transcription_config.wake_trigger_enabled
            else "off"
        )
        wake_input_label = describe_stream_input_device(self._wake_phrase_controller.config.input_device)
        self.config_summary_label.setText(
            (
                f"URL: {self._transcription_config.base_url}\n"
                f"Language: {self._transcription_config.language or 'auto'}  |  "
                f"Timeout: {self._transcription_config.request_timeout_seconds}s  |  Stream: {stream_mode}\n"
                f"Microphone: {microphone_label}\n"
                f"Auto-stop: {auto_stop_mode}\n"
                f"Wake trigger: {wake_mode}\n"
                f"Wake input: {wake_input_label}"
            )
        )

    def _refresh_backend_health(self, *, auto_start: bool = False) -> None:
        if self._health_thread is not None:
            return
        if auto_start and self._backend_manager.can_manage(self._transcription_config.base_url):
            self._backend_health_retry_after_start = False
        if not self._backend_health_retry_after_start:
            self._backend_status_override = None
        self._health_thread = QThread(self)
        self._health_worker = BackendHealthWorker(self._transcription_config)
        self._health_worker.moveToThread(self._health_thread)
        self._health_thread.started.connect(self._health_worker.run)
        self._health_worker.finished.connect(self._handle_backend_health_finished)
        self._health_worker.failed.connect(self._handle_backend_health_failed)
        self._health_worker.finished.connect(self._health_thread.quit)
        self._health_worker.failed.connect(self._health_thread.quit)
        self._health_thread.finished.connect(self._cleanup_health_worker)
        self._health_thread.start()

    def _apply_runtime_config(
        self,
        config: RealtimeBackendTranscriptionConfig,
        *,
        emit_activity: bool = True,
    ) -> RealtimeBackendTranscriptionConfig:
        self._capture_controller.set_auto_stop_config(config.to_auto_stop_config())
        config = self._apply_audio_input_config(config, emit_activity=emit_activity)
        wake_input_label: str | None = None
        selected_input = self._capture_controller.selected_audio_input()
        if config.audio_input_device_id is not None and selected_input is not None:
            wake_input_label = selected_input.label
        existing_wake_config = self._wake_phrase_controller.config
        self._wake_phrase_controller.apply_config(
            WakePhraseConfig(
                enabled=config.wake_trigger_enabled,
                wake_phrase=config.wake_phrase,
                shutdown_phrase=config.shutdown_phrase,
                sample_rate=existing_wake_config.sample_rate,
                block_size=existing_wake_config.block_size,
                cooldown_seconds=config.wake_cooldown_seconds,
                model_path=existing_wake_config.model_path,
                input_device=wake_input_label,
            )
        )
        return config

    def _apply_audio_input_config(
        self,
        config: RealtimeBackendTranscriptionConfig,
        *,
        emit_activity: bool = True,
    ) -> RealtimeBackendTranscriptionConfig:
        try:
            selected_input = self._capture_controller.set_audio_input_by_id(config.audio_input_device_id)
        except ValueError as exc:
            selected_input = self._capture_controller.set_audio_input_by_id(None)
            config = replace(
                config,
                audio_input_device_id=None,
                audio_input_device_label=None,
            )
            if emit_activity:
                self.activity_reported.emit(f"{exc} Using the system default microphone instead.")
            return config

        if selected_input is None:
            return replace(config, audio_input_device_id=None, audio_input_device_label=None)

        if config.audio_input_device_id is None:
            return replace(config, audio_input_device_id=None, audio_input_device_label=selected_input.label)

        return replace(config, audio_input_device_label=selected_input.label)

    @staticmethod
    def _processing_hint(state: VoiceCommandState) -> str:
        if state.stage == "recording":
            return "Recording from the active microphone. Live transcript will update when stream mode is on."
        if state.stage == "audio_ready":
            return "Audio ready. The panel will start transcription automatically."
        if state.stage == "transcribing":
            return "Backend pipeline running: VAD, ASR, diarization, alignment, and transcript cleanup."
        if state.stage == "transcript_ready":
            return "Transcript saved locally and linked to the current session flow."
        if state.stage == "error":
            return "If the backend is down, open `realtime_backend` and start uvicorn on port 8080."
        return "Say 'command wake' to start hands-free, then pause briefly to auto-stop."

    @staticmethod
    def _activity_message(state: VoiceCommandState) -> str:
        if state.stage == "recording":
            return "Voice command capture started from the active microphone."
        if state.stage == "audio_ready":
            return f"Audio capture saved to {state.audio_path}"
        if state.stage == "transcribing":
            return "Sending audio to the local transcription backend."
        if state.stage == "transcript_ready":
            return "Transcript received from the local backend."
        if state.stage == "error":
            return state.guidance_text
        return "Voice command panel reset."

    def closeEvent(self, event: QCloseEvent) -> None:
        self._cancel_live_stream()
        self._backend_health_timer.stop()
        self._backend_manager.shutdown()
        self._wake_phrase_controller.shutdown()
        super().closeEvent(event)

    def _complete_transcription_result(self, result: TranscriptionResult) -> None:
        transcript_text = result.text
        self._apply_state(self._workflow.complete_transcription(transcript_text))
        self.transcript_output.setPlainText(result.corrected_text_output or transcript_text)
        self.transcript_captured.emit(result)

    def _cancel_live_stream(self) -> None:
        self._live_stream_attempted = False
        self._live_stream_failed = False
        self._live_stream_finalizing = False
        if self._live_stream_controller.is_active:
            self._live_stream_controller.cancel()

    def _backend_status_text(self, fallback_message: str | None = None) -> str:
        if self._backend_status_override:
            return self._backend_status_override
        if self._backend_health is None:
            if fallback_message:
                return f"Backend health unavailable. {fallback_message}"
            return "Backend health unavailable."
        health = self._backend_health
        asr_status = f"{health.asr_provider} -> {health.asr_provider_resolved or '-'}"
        if health.asr_fallback_provider:
            asr_status += f" (fallback {health.asr_fallback_provider})"
        llm_status = f"{health.llm_provider} -> {health.llm_provider_resolved or '-'}"
        if health.llm_fallback_provider:
            llm_status += f" (fallback {health.llm_fallback_provider})"
        return (
            f"{health.app_name} [{health.status}]  |  "
            f"STT: {asr_status}  |  "
            f"LLM: {llm_status}  |  "
            f"VAD: {health.vad_provider}  |  Diarizer: {health.diarizer_provider}"
        )
