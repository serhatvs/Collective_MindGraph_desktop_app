import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QApplication

from collective_mindgraph_desktop.audio_capture import AudioInputDeviceInfo
from collective_mindgraph_desktop.transcription import (
    BackendHealthStatus,
    RealtimeBackendTranscriptionConfig,
    StreamingTranscriptionUpdate,
    TranscriptionResult,
)
from collective_mindgraph_desktop.wake_phrase import WakePhraseConfig
import collective_mindgraph_desktop.ui.voice_command_panel as voice_command_panel_module


class FakeCaptureController(QObject):
    recording_started = Signal(str)
    recording_stopped = Signal(str)
    recording_auto_stopped = Signal(str)
    capture_cleared = Signal()
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._selected_input = AudioInputDeviceInfo(
            device_id="default",
            label="Test Mic",
            is_default=True,
        )
        self.start_calls = 0
        self.clear_calls = 0

    def available_audio_inputs(self) -> list[AudioInputDeviceInfo]:
        return [self._selected_input]

    def selected_audio_input(self) -> AudioInputDeviceInfo | None:
        return self._selected_input

    def set_audio_input_by_id(self, _device_id: str | None) -> AudioInputDeviceInfo | None:
        return self._selected_input

    def set_auto_stop_config(self, _config) -> None:
        return

    def start_recording(self) -> None:
        self.start_calls += 1
        self.recording_started.emit("C:/tmp/test.wav")

    def clear_capture(self) -> None:
        self.clear_calls += 1
        self.capture_cleared.emit()


class FakeWakePhraseController(QObject):
    wake_requested = Signal(str)
    shutdown_requested = Signal(str)
    state_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = WakePhraseConfig(enabled=False)
        self._armed = False
        self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_armed(self) -> bool:
        return self._armed

    @property
    def config(self) -> WakePhraseConfig:
        return self._config

    def status_text(self) -> str:
        return "Wake trigger unavailable in test."

    def apply_config(self, config: WakePhraseConfig) -> None:
        self._config = config
        self._armed = config.enabled

    def toggle_armed(self) -> None:
        self._armed = not self._armed

    def shutdown(self) -> None:
        return


class FakeLiveTranscriptStreamController(QObject):
    partial_received = Signal(object)
    finalized = Signal(object)
    failed = Signal(str)
    state_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.is_active = False
        self.start_calls = 0
        self.finalize_calls = 0
        self.cancel_calls = 0

    def start(self, _output_path: str, _config) -> None:
        self.start_calls += 1
        self.is_active = True

    def finalize(self) -> None:
        self.finalize_calls += 1

    def cancel(self) -> None:
        self.cancel_calls += 1
        self.is_active = False


class FakeBackendManager(QObject):
    state_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.ensure_running_calls: list[str] = []

    def can_manage(self, _base_url: str) -> bool:
        return True

    def ensure_running(self, base_url: str) -> bool:
        self.ensure_running_calls.append(base_url)
        return True

    def shutdown(self) -> None:
        return


def build_panel(monkeypatch, *, transcription_config: RealtimeBackendTranscriptionConfig | None = None):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(voice_command_panel_module, "VoskWakePhraseController", FakeWakePhraseController)
    monkeypatch.setattr(voice_command_panel_module, "LiveTranscriptStreamController", FakeLiveTranscriptStreamController)
    monkeypatch.setattr(voice_command_panel_module, "LocalBackendManager", FakeBackendManager)
    monkeypatch.setattr(
        voice_command_panel_module.VoiceCommandPanel,
        "_refresh_backend_health",
        lambda self, auto_start=False: None,
    )
    panel = voice_command_panel_module.VoiceCommandPanel(
        capture_controller=FakeCaptureController(),
        transcription_config=transcription_config
        or RealtimeBackendTranscriptionConfig(
            stream_live_transcription=False,
            wake_trigger_enabled=False,
        ),
    )
    assert app is not None
    return panel


def set_transcribing_state(panel):
    panel._apply_state(panel._workflow.start_recording())
    panel._apply_state(panel._workflow.stop_recording("C:/tmp/test.wav"))
    panel._apply_state(panel._workflow.transcribe())


def test_voice_command_panel_preserves_startup_retry_message_during_cleanup(monkeypatch):
    panel = build_panel(monkeypatch)
    panel._health_thread = QThread(panel)
    panel._health_worker = QObject(panel)

    panel._handle_backend_health_failed("Connection refused.")

    assert panel.provider_status_label.text() == "Starting local backend and retrying health check..."

    panel._cleanup_health_worker()

    assert panel.provider_status_label.text() == "Starting local backend and retrying health check..."
    panel.close()


def test_voice_command_panel_wake_request_starts_recording_when_idle(monkeypatch):
    panel = build_panel(monkeypatch)
    activity_messages: list[str] = []
    panel.activity_reported.connect(activity_messages.append)

    panel._handle_wake_requested("command wake")

    assert panel._capture_controller.start_calls == 1
    assert panel._workflow.state.stage == "recording"
    assert "Wake phrase detected: command wake" in activity_messages
    panel.close()


def test_voice_command_panel_wake_request_is_ignored_while_transcribing(monkeypatch):
    panel = build_panel(monkeypatch)
    activity_messages: list[str] = []
    panel.activity_reported.connect(activity_messages.append)
    set_transcribing_state(panel)
    start_calls_before = panel._capture_controller.start_calls

    panel._handle_wake_requested("command wake")

    assert panel._capture_controller.start_calls == start_calls_before
    assert panel._workflow.state.stage == "transcribing"
    assert "Wake phrase detected: command wake" not in activity_messages
    panel.close()


def test_voice_command_panel_shutdown_request_cancels_active_recording(monkeypatch):
    panel = build_panel(monkeypatch)
    activity_messages: list[str] = []
    panel.activity_reported.connect(activity_messages.append)
    panel._handle_start()

    panel._handle_shutdown_requested("command shut")

    assert panel._capture_controller.clear_calls == 1
    assert panel._workflow.state.stage == "idle"
    assert any("Active voice turn was cancelled." in item for item in activity_messages)
    panel.close()


def test_voice_command_panel_shutdown_request_during_transcribing_keeps_state(monkeypatch):
    panel = build_panel(monkeypatch)
    activity_messages: list[str] = []
    panel.activity_reported.connect(activity_messages.append)
    set_transcribing_state(panel)

    panel._handle_shutdown_requested("command shut")

    assert panel._capture_controller.clear_calls == 0
    assert panel._workflow.state.stage == "transcribing"
    assert any("Current transcription will finish" in item for item in activity_messages)
    panel.close()


def test_voice_command_panel_finalizes_live_stream_on_capture_stop(monkeypatch):
    panel = build_panel(
        monkeypatch,
        transcription_config=RealtimeBackendTranscriptionConfig(
            stream_live_transcription=True,
            wake_trigger_enabled=False,
        ),
    )
    transcribe_calls: list[str] = []
    panel._handle_transcribe = lambda: transcribe_calls.append("called")  # type: ignore[method-assign]
    panel._handle_start()
    panel._handle_capture_stopped("C:/tmp/test.wav")

    assert panel._live_stream_controller.start_calls == 1
    assert panel._live_stream_controller.finalize_calls == 1
    assert panel._live_stream_finalizing is True
    assert panel._workflow.state.stage == "transcribing"
    assert transcribe_calls == []
    panel.close()


def test_voice_command_panel_falls_back_to_file_upload_when_live_finalize_fails(monkeypatch):
    panel = build_panel(
        monkeypatch,
        transcription_config=RealtimeBackendTranscriptionConfig(
            stream_live_transcription=True,
            wake_trigger_enabled=False,
        ),
    )
    activity_messages: list[str] = []
    transcribe_calls: list[str] = []
    panel.activity_reported.connect(activity_messages.append)
    monkeypatch.setattr(voice_command_panel_module.QTimer, "singleShot", lambda _delay, callback: callback())
    panel._handle_transcribe = lambda: transcribe_calls.append("called")  # type: ignore[method-assign]
    panel._handle_start()
    panel._handle_capture_stopped("C:/tmp/test.wav")

    panel._handle_live_failed("Live stream dropped.")

    assert panel._live_stream_finalizing is False
    assert panel._live_stream_failed is True
    assert transcribe_calls == ["called"]
    assert any("Live stream dropped. Falling back to final file upload." in item for item in activity_messages)
    panel.close()


def test_voice_command_panel_renders_live_partial_text(monkeypatch):
    panel = build_panel(monkeypatch)

    panel._handle_live_partial_received(
        StreamingTranscriptionUpdate(
            conversation_id="conv_partial",
            audio_path="C:/tmp/test.wav",
            text="Speaker_1: partial raw",
            corrected_text_output="Speaker_1: Partial corrected.",
            is_final=False,
        )
    )

    assert panel.transcript_output.toPlainText() == "Speaker_1: Partial corrected."
    panel.close()


def test_voice_command_panel_emits_transcript_captured_after_live_finalization(monkeypatch):
    panel = build_panel(monkeypatch)
    captured_results: list[TranscriptionResult] = []
    panel.transcript_captured.connect(captured_results.append)
    set_transcribing_state(panel)
    panel._live_stream_attempted = True
    panel._live_stream_failed = True
    panel._live_stream_finalizing = True
    result = TranscriptionResult(
        text="Speaker_1: Final raw.",
        model_id="realtime_backend",
        audio_path="C:/tmp/test.wav",
        conversation_id="conv_final",
        corrected_text_output="Speaker_1: Final corrected.",
    )

    panel._handle_live_finalized(result)

    assert panel._live_stream_attempted is False
    assert panel._live_stream_failed is False
    assert panel._live_stream_finalizing is False
    assert panel._workflow.state.stage == "transcript_ready"
    assert panel.transcript_output.toPlainText() == "Speaker_1: Final corrected."
    assert captured_results == [result]
    panel.close()


def test_voice_command_panel_surfaces_backend_manager_state_and_error_events(monkeypatch):
    panel = build_panel(monkeypatch)
    activity_messages: list[str] = []
    panel.activity_reported.connect(activity_messages.append)

    panel._backend_manager.state_changed.emit("Started local backend.")
    panel._backend_manager.error_occurred.emit("Local backend crashed.")

    assert "Started local backend." in activity_messages
    assert "Local backend crashed." in activity_messages
    panel.close()


def test_voice_command_panel_refresh_button_requests_backend_health_with_autostart(monkeypatch):
    panel = build_panel(monkeypatch)
    refresh_calls: list[bool] = []
    panel._refresh_backend_health = lambda auto_start=False: refresh_calls.append(auto_start)  # type: ignore[method-assign]

    panel.refresh_backend_button.click()

    assert refresh_calls == [True]
    panel.close()


def test_voice_command_panel_clears_retry_message_after_successful_health_retry(monkeypatch):
    panel = build_panel(monkeypatch)

    panel._handle_backend_health_failed("Connection refused.")
    panel._handle_backend_health_finished(
        BackendHealthStatus(
            status="ok",
            app_name="Realtime Backend",
            vad_provider="silero",
            asr_provider="auto",
            asr_provider_resolved="deepgram",
            asr_fallback_provider="faster_whisper",
            diarizer_provider="pyannote",
            llm_provider="bedrock_auto_local",
            llm_provider_resolved="bedrock",
            llm_fallback_provider="lmstudio",
        )
    )

    assert "Starting local backend and retrying health check..." not in panel.provider_status_label.text()
    assert "Realtime Backend [ok]" in panel.provider_status_label.text()
    assert "STT: auto -> deepgram (fallback faster_whisper)" in panel.provider_status_label.text()
    assert "LLM: bedrock_auto_local -> bedrock (fallback lmstudio)" in panel.provider_status_label.text()
    assert "LLM reachability: Amazon Bedrock is active; LM Studio is ready as fallback." in panel.provider_status_label.text()
    panel.close()


def test_voice_command_panel_surfaces_bedrock_fallback_activity(monkeypatch):
    panel = build_panel(monkeypatch)

    panel._handle_backend_health_finished(
        BackendHealthStatus(
            status="ok",
            app_name="Realtime Backend",
            vad_provider="silero",
            asr_provider="auto",
            asr_provider_resolved="faster_whisper",
            asr_fallback_provider="mock",
            diarizer_provider="pyannote",
            llm_provider="bedrock_auto_local",
            llm_provider_resolved="lmstudio",
            llm_fallback_provider="mock",
        )
    )

    assert "LLM: bedrock_auto_local -> lmstudio (fallback mock)" in panel.provider_status_label.text()
    assert (
        "LLM fallback active: Amazon Bedrock is unreachable, so LM Studio is handling corrections."
        in panel.provider_status_label.text()
    )
    assert "Mock cleanup remains the last fallback." in panel.provider_status_label.text()
    panel.close()


def test_voice_command_panel_surfaces_auto_local_mock_fallback(monkeypatch):
    panel = build_panel(monkeypatch)

    panel._handle_backend_health_finished(
        BackendHealthStatus(
            status="ok",
            app_name="Realtime Backend",
            vad_provider="silero",
            asr_provider="auto",
            asr_provider_resolved="faster_whisper",
            asr_fallback_provider="mock",
            diarizer_provider="pyannote",
            llm_provider="auto_local",
            llm_provider_resolved="mock",
            llm_fallback_provider="mock",
        )
    )

    assert "LLM: auto_local -> mock (fallback mock)" in panel.provider_status_label.text()
    assert (
        "LLM fallback active: LM Studio is unreachable, so mock cleanup is handling corrections."
        in panel.provider_status_label.text()
    )
    panel.close()
