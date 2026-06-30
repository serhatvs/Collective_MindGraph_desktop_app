"""Voice command panel for the main application window."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot, Qt
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
from ..runtime_paths import is_frozen_build
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
from .components.status_badge import StatusBadge
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
    backend_health_updated = Signal(object)

    def current_transcription_config(self) -> RealtimeBackendTranscriptionConfig:
        return self._transcription_config

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
        self._transcript_output_override: str | None = None
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

        # NEW COMPACT UI LAYOUT
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.card = CardWidget("Voice Ingest")
        root_layout.addWidget(self.card)

        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        self.status_badge = StatusBadge("IDLE", stage="idle")
        self.status_badge.setMinimumWidth(140)
        self.status_badge.setMinimumHeight(32)
        top_row.addWidget(self.status_badge)

        self.pipeline_label = QLabel("Capture technical conversation for automated analysis.")
        self.pipeline_label.setObjectName("MutedText")
        top_row.addWidget(self.pipeline_label, 1)

        self.card.body_layout.addLayout(top_row)

        control_row = QHBoxLayout()
        control_row.setSpacing(10)

        self.start_button = QPushButton("Start Recording")
        self.start_button.clicked.connect(self._handle_start)

        self.stop_button = QPushButton("Stop & Transcribe")
        self.stop_button.setProperty("secondary", True)
        self.stop_button.clicked.connect(self._handle_stop)
        self.stop_button.setEnabled(False)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setProperty("secondary", True)
        self.clear_button.clicked.connect(self._handle_clear)
        self.clear_button.setEnabled(False)

        self.settings_button = QPushButton("Settings")
        self.settings_button.setProperty("secondary", True)
        self.settings_button.clicked.connect(self._handle_open_settings)

        control_row.addWidget(self.start_button)
        control_row.addWidget(self.stop_button)
        control_row.addWidget(self.clear_button)
        control_row.addStretch(1)
        control_row.addWidget(self.settings_button)

        self.card.body_layout.addLayout(control_row)

        # Provider / Health status at the bottom of the card
        self.provider_status_label = QLabel("Backend Status: Checking...")
        self.provider_status_label.setObjectName("MutedText")
        self.provider_status_label.setStyleSheet("font-size: 9pt;")
        self.card.body_layout.addWidget(self.provider_status_label)

        # Compatibility placeholders (Hidden)
        self.guidance_label = QLabel()
        self.capture_path_label = QLabel()
        self.config_summary_label = QLabel()
        self.wake_status_label = QLabel()
        self.transcript_output = QPlainTextEdit()
        self.processing_hint_label = QLabel()
        self.transcribe_button = QPushButton()
        self.wake_toggle_button = QPushButton()
        self.refresh_backend_button = QPushButton()
        self.transcribe_button.clicked.connect(self._handle_transcribe)
        self.wake_toggle_button.clicked.connect(self._handle_toggle_wake_trigger)
        self.refresh_backend_button.clicked.connect(lambda: self._refresh_backend_health(auto_start=True))

        # Wire signals
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

        self._apply_state(self._workflow.state)
        self._backend_health_timer.start()
        QTimer.singleShot(0, lambda: self._refresh_backend_health(auto_start=True))

    def _handle_start(self) -> None:
        if self._transcription_thread is not None:
            return
        self._transcript_output_override = None
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

        self._transcript_output_override = None
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
        self._transcript_output_override = None
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
        self.status_badge.set_stage(state.stage)

        self.guidance_label.setText(state.guidance_text)
        self.capture_path_label.setText(state.audio_path or "No audio clip captured yet.")
        self._refresh_config_summary()
        self.transcript_output.setPlainText(state.transcript_text or self._transcript_output_override or "")
        self.processing_hint_label.setText(self._processing_hint(state))
        self.wake_status_label.setText(self._wake_phrase_controller.status_text())
        self.provider_status_label.setText(self._backend_status_text())

        self.start_button.setEnabled(state.start_enabled)
        self.stop_button.setEnabled(state.stop_enabled)
        self.transcribe_button.setEnabled(state.transcribe_enabled)
        self.wake_toggle_button.setText(
            "Disable Wake Trigger" if self._wake_phrase_controller.is_armed else "Enable Wake Trigger"
        )
        self.wake_toggle_button.setEnabled(
            self._transcription_thread is None and self._wake_phrase_controller.is_available
        )
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
        self.activity_reported.emit("Recording stopped and will be transcribed.")
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
        if self._workflow.state.stage in {"recording", "transcribing"}:
            return
        self.activity_reported.emit(f"Wake phrase detected: {recognized_text}")
        self._handle_start()

    def _handle_shutdown_requested(self, recognized_text: str) -> None:
        if self._workflow.state.stage == "transcribing":
            self.activity_reported.emit("Current transcription will finish before shutdown.")
            return
        if self._workflow.state.stage != "recording":
            return
        self.activity_reported.emit(f"Shutdown phrase detected: {recognized_text}")
        self._handle_stop()

    def _handle_wake_state_changed(self, message: str) -> None:
        self._apply_state(self._workflow.state)
        if message:
            self.activity_reported.emit(message)

    def _handle_wake_error(self, message: str) -> None:
        self.activity_reported.emit(f"Wake trigger error: {message}")

    def _handle_live_partial_received(self, update: StreamingTranscriptionUpdate) -> None:
        if self._live_stream_finalizing:
            return
        self._transcript_output_override = update.corrected_text_output or update.text
        self._apply_state(self._workflow.state)

    def _handle_live_finalized(self, result: TranscriptionResult) -> None:
        self._live_stream_attempted = False
        self._live_stream_failed = False
        self._live_stream_finalizing = False
        self._complete_transcription_result(result)

    def _handle_live_failed(self, message: str) -> None:
        if not self._live_stream_finalizing:
            self.activity_reported.emit(f"Live stream failed: {message}. Falling back to upload.")
            return
        self._live_stream_finalizing = False
        self._live_stream_failed = True
        self.activity_reported.emit(f"{message} Falling back to final file upload.")
        QTimer.singleShot(0, self._handle_transcribe)

    def _handle_live_state_changed(self, message: str) -> None:
        if message:
            self.activity_reported.emit(message)

    def _handle_backend_manager_state_changed(self, message: str) -> None:
        if message:
            self.activity_reported.emit(message)

    def _handle_backend_manager_error(self, message: str) -> None:
        self.activity_reported.emit(message)

    def _refresh_backend_health(self, auto_start: bool = False) -> None:
        try:
            if not self.isVisible() and not self.parent(): # Basic liveness check
                 pass
        except RuntimeError:
            return

        if self._health_thread is not None:
            return
        self._health_thread = QThread(self)
        self._health_worker = BackendHealthWorker(self._transcription_config)
        self._health_worker.moveToThread(self._health_thread)
        self._health_thread.started.connect(self._health_worker.run)
        self._health_worker.finished.connect(self._handle_backend_health_finished)
        self._health_worker.failed.connect(self._handle_backend_health_failed)
        self._health_worker.finished.connect(self._health_thread.quit)
        self._health_worker.failed.connect(self._health_thread.quit)
        self._health_thread.finished.connect(self._cleanup_health_worker)
        self._backend_health_retry_after_start = auto_start
        self._health_thread.start()

    def _handle_backend_health_finished(self, status: BackendHealthStatus) -> None:
        self._backend_health = status
        self._backend_status_override = None
        self.backend_health_updated.emit(status)
        self._apply_state(self._workflow.state)

    def _handle_backend_health_failed(self, message: str) -> None:
        self._backend_health = None
        can_retry = self._backend_health_retry_after_start or self._backend_manager.can_manage(self._transcription_config.base_url)
        if can_retry and not is_frozen_build():
            self._backend_status_override = "Starting local backend and retrying health check..."
            self._backend_manager.ensure_running(self._transcription_config.base_url)
            self._backend_health_retry_after_start = False
            QTimer.singleShot(5000, self._refresh_backend_health)
        else:
            self._backend_status_override = None
        self._apply_state(self._workflow.state)

    def _cleanup_transcription_worker(self) -> None:
        self._transcription_thread = None
        self._transcription_worker = None
        self._apply_state(self._workflow.state)

    def _cleanup_health_worker(self) -> None:
        self._health_thread = None
        self._health_worker = None

    def _complete_transcription_result(self, result: TranscriptionResult) -> None:
        display_text = result.corrected_text_output or result.text
        self._transcript_output_override = display_text
        self._apply_state(self._workflow.complete_transcription(display_text))
        self.transcript_captured.emit(result)

    def _cancel_live_stream(self) -> None:
        if hasattr(self._live_stream_controller, "stop"):
            self._live_stream_controller.stop()
        elif hasattr(self._live_stream_controller, "cancel"):
            self._live_stream_controller.cancel()
        self._live_stream_attempted = False
        self._live_stream_failed = False
        self._live_stream_finalizing = False

    def _backend_status_text(self) -> str:
        if self._backend_status_override:
            return self._backend_status_override
        if self._backend_health is None:
            return f"Backend unreachable at {self._transcription_config.base_url}"
        
        h = self._backend_health
        asr_resolved = h.asr_provider_resolved or h.asr_provider
        llm_resolved = h.llm_provider_resolved or h.llm_provider
        asr_fallback = f" (fallback {h.asr_fallback_provider})" if h.asr_fallback_provider else ""
        llm_fallback = f" (fallback {h.llm_fallback_provider})" if h.llm_fallback_provider else ""
        gpu_status = (
            f"ASR runtime: profile={h.asr_runtime_profile or '-'}, "
            f"model={h.asr_model_name or '-'}, device={h.asr_device or '-'}, "
            f"compute={h.asr_compute_type or '-'}, cuda_available={_bool_text(h.cuda_available_through_torch)}, "
            f"gpu_requested={_bool_text(h.gpu_requested)}, gpu_used={_bool_text(h.gpu_actually_used_by_asr)}, "
            f"fallback={_bool_text(h.gpu_fallback_happened)}"
        )
        if h.gpu_fallback_reason:
            gpu_status = f"{gpu_status}, reason={h.gpu_fallback_reason}"
        llm_reachability = (
            "LLM reachability: LM Studio is active; mock cleanup is ready as the last fallback."
            if llm_resolved == "lmstudio"
            else "LLM fallback active: LM Studio is unreachable, so mock cleanup is handling corrections."
            if llm_resolved == "mock"
            else f"LLM provider resolved: {llm_resolved}."
        )
        return (
            f"{h.app_name} [{h.status}] | "
            f"STT: {h.asr_provider} -> {asr_resolved}{asr_fallback} | "
            f"LLM: {h.llm_provider} -> {llm_resolved}{llm_fallback} | "
            f"{gpu_status} | "
            f"{llm_reachability}"
        )

    def _processing_hint(self, state: VoiceCommandState) -> str:
        if state.stage == "recording":
            return "Speaking... Click stop or wait for auto-stop."
        if state.stage == "transcribing":
            return "Running local Faster-Whisper inference..."
        return ""

    def _activity_message(self, state: VoiceCommandState) -> str:
        if state.stage == "recording":
            return "Voice capture active."
        if state.stage == "transcribing":
            return "Transcribing audio locally."
        if state.stage == "completed":
            return "Transcription finished."
        if state.stage == "error":
            return f"Error: {state.status_label}"
        return ""

    def _apply_runtime_config(
        self,
        config: RealtimeBackendTranscriptionConfig,
        emit_activity: bool = True,
    ) -> RealtimeBackendTranscriptionConfig:
        return config

    def _load_transcription_config(self) -> RealtimeBackendTranscriptionConfig:
        return self._settings_store.load()

    def _refresh_config_summary(self) -> None:
        pass


def _bool_text(value: bool | None) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "unknown"
