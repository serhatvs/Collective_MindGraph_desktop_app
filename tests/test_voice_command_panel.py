import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QApplication

from collective_mindgraph_desktop.audio_capture import AudioInputDeviceInfo
from collective_mindgraph_desktop.transcription import BackendHealthStatus, RealtimeBackendTranscriptionConfig
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

    def available_audio_inputs(self) -> list[AudioInputDeviceInfo]:
        return [self._selected_input]

    def selected_audio_input(self) -> AudioInputDeviceInfo | None:
        return self._selected_input

    def set_audio_input_by_id(self, _device_id: str | None) -> AudioInputDeviceInfo | None:
        return self._selected_input

    def set_auto_stop_config(self, _config) -> None:
        return

    def clear_capture(self) -> None:
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

    def cancel(self) -> None:
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


def build_panel(monkeypatch):
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
        transcription_config=RealtimeBackendTranscriptionConfig(
            stream_live_transcription=False,
            wake_trigger_enabled=False,
        ),
    )
    assert app is not None
    return panel


def test_voice_command_panel_preserves_startup_retry_message_during_cleanup(monkeypatch):
    panel = build_panel(monkeypatch)
    panel._health_thread = QThread(panel)
    panel._health_worker = QObject(panel)

    panel._handle_backend_health_failed("Connection refused.")

    assert panel.provider_status_label.text() == "Starting local backend and retrying health check..."

    panel._cleanup_health_worker()

    assert panel.provider_status_label.text() == "Starting local backend and retrying health check..."
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
    panel.close()
