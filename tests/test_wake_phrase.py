from PySide6.QtWidgets import QApplication

from collective_mindgraph_desktop import wake_phrase as wake_phrase_module
from collective_mindgraph_desktop.wake_phrase import (
    DEFAULT_SHUTDOWN_PHRASE,
    DEFAULT_WAKE_PHRASE,
    VoskWakePhraseController,
    WakePhraseConfig,
    detect_control_phrase,
    normalize_command_text,
    phrase_variants,
)


def build_app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_normalize_command_text_collapses_noise():
    assert normalize_command_text("Command...   wake!!") == "command wake"


def test_detect_control_phrase_matches_wake_phrase_inside_partial_sentence():
    detected = detect_control_phrase(
        text="hey there command wake now",
        wake_phrase=DEFAULT_WAKE_PHRASE,
        shutdown_phrase=DEFAULT_SHUTDOWN_PHRASE,
    )

    assert detected == "wake"


def test_detect_control_phrase_matches_shutdown_phrase():
    detected = detect_control_phrase(
        text="okay command shut please",
        wake_phrase=DEFAULT_WAKE_PHRASE,
        shutdown_phrase=DEFAULT_SHUTDOWN_PHRASE,
    )

    assert detected == "shutdown"


def test_detect_control_phrase_matches_common_vosk_shortened_wake_variants():
    for text in ("i command wake", "command wake up", "command wake", "i command wakeup", "command wakeup"):
        detected = detect_control_phrase(
            text=text,
            wake_phrase=DEFAULT_WAKE_PHRASE,
            shutdown_phrase=DEFAULT_SHUTDOWN_PHRASE,
        )

        assert detected == "wake"


def test_detect_control_phrase_matches_common_vosk_shortened_shutdown_variants():
    for text in ("i command shut", "command shut down", "command shut", "i command shutdown", "command shutdown"):
        detected = detect_control_phrase(
            text=text,
            wake_phrase=DEFAULT_WAKE_PHRASE,
            shutdown_phrase=DEFAULT_SHUTDOWN_PHRASE,
        )

        assert detected == "shutdown"


def test_detect_control_phrase_does_not_trigger_on_plain_wake_up_without_command():
    detected = detect_control_phrase(
        text="please wake up now",
        wake_phrase=DEFAULT_WAKE_PHRASE,
        shutdown_phrase=DEFAULT_SHUTDOWN_PHRASE,
    )

    assert detected is None


def test_detect_control_phrase_returns_none_for_irrelevant_text():
    detected = detect_control_phrase(
        text="this is just ordinary dictation",
        wake_phrase=DEFAULT_WAKE_PHRASE,
        shutdown_phrase=DEFAULT_SHUTDOWN_PHRASE,
    )

    assert detected is None


def test_phrase_variants_include_shortened_and_compound_aliases():
    wake_variants = phrase_variants(DEFAULT_WAKE_PHRASE)
    shutdown_variants = phrase_variants(DEFAULT_SHUTDOWN_PHRASE)

    assert "command wake" in wake_variants
    assert "command wake" == DEFAULT_WAKE_PHRASE
    assert "command shut" in shutdown_variants
    assert "command shut" == DEFAULT_SHUTDOWN_PHRASE


def test_wake_phrase_controller_updates_status_for_arm_and_suspend_states(monkeypatch):
    build_app()
    stop_calls: list[str] = []
    ensure_calls: list[str] = []

    monkeypatch.setattr(wake_phrase_module, "_check_runtime_availability", lambda _config: (True, "ready"))
    monkeypatch.setattr(
        VoskWakePhraseController,
        "_ensure_worker",
        lambda self: ensure_calls.append("ensure"),
    )
    monkeypatch.setattr(
        VoskWakePhraseController,
        "_stop_worker",
        lambda self: stop_calls.append("stop"),
    )

    controller = VoskWakePhraseController(config=WakePhraseConfig(model_path="stub-model"))

    assert controller.is_available is True
    assert controller.is_armed is True
    assert ensure_calls == ["ensure"]

    controller.disarm()

    assert controller.is_armed is False
    assert controller.status_text() == "Wake trigger is off. Use the button to re-arm it."
    assert stop_calls == ["stop"]

    controller.arm()

    assert controller.is_armed is True
    assert controller.status_text().startswith("Wake trigger armed.")
    assert ensure_calls == ["ensure", "ensure"]

    controller.suspend()

    assert controller.status_text() == "Wake trigger paused while the app is recording or transcribing."
    assert stop_calls == ["stop", "stop"]

    controller.resume()

    assert controller.status_text().startswith("Wake trigger armed.")
    assert ensure_calls == ["ensure", "ensure", "ensure"]


def test_wake_phrase_controller_reports_failure_and_disarms(monkeypatch):
    build_app()
    monkeypatch.setattr(wake_phrase_module, "_check_runtime_availability", lambda _config: (True, "ready"))
    monkeypatch.setattr(VoskWakePhraseController, "_ensure_worker", lambda self: None)
    monkeypatch.setattr(VoskWakePhraseController, "_stop_worker", lambda self: None)

    controller = VoskWakePhraseController(config=WakePhraseConfig(model_path="stub-model"))
    errors: list[str] = []
    states: list[str] = []
    controller.error_occurred.connect(errors.append)
    controller.state_changed.connect(states.append)

    controller._handle_worker_failure("VOSK wake trigger failed: device missing")

    assert errors == ["VOSK wake trigger failed: device missing"]
    assert states == ["VOSK wake trigger failed: device missing"]
    assert controller.is_available is False
    assert controller.is_armed is False
    assert controller.status_text() == "VOSK wake trigger failed: device missing"


def test_wake_phrase_controller_restarts_worker_after_input_device_change(monkeypatch):
    build_app()
    stop_calls: list[str | None] = []
    ensure_calls: list[str | None] = []

    monkeypatch.setattr(wake_phrase_module, "_check_runtime_availability", lambda _config: (True, "ready"))

    def fake_ensure(self) -> None:
        ensure_calls.append(self._config.input_device)
        self._worker_thread = object()
        self._worker = None

    monkeypatch.setattr(VoskWakePhraseController, "_ensure_worker", fake_ensure)
    monkeypatch.setattr(
        VoskWakePhraseController,
        "_stop_worker",
        lambda self: stop_calls.append(self._config.input_device),
    )

    controller = VoskWakePhraseController(config=WakePhraseConfig(model_path="stub-model"))

    assert ensure_calls == [None]
    assert controller._worker_thread is not None

    controller.set_input_device("Desk Mic")

    assert controller.config.input_device == "Desk Mic"
    assert stop_calls == ["Desk Mic"]
    assert ensure_calls == [None]
    assert controller._desired_running is True

    controller._cleanup_worker()

    assert ensure_calls == [None, "Desk Mic"]
    assert controller._worker_thread is not None


def test_wake_phrase_controller_routes_detected_wake_and_shutdown_signals(monkeypatch):
    build_app()
    monkeypatch.setattr(wake_phrase_module, "_check_runtime_availability", lambda _config: (True, "ready"))
    monkeypatch.setattr(VoskWakePhraseController, "_ensure_worker", lambda self: None)
    monkeypatch.setattr(VoskWakePhraseController, "_stop_worker", lambda self: None)

    controller = VoskWakePhraseController(config=WakePhraseConfig(model_path="stub-model"))
    wake_requests: list[str] = []
    shutdown_requests: list[str] = []
    controller.wake_requested.connect(wake_requests.append)
    controller.shutdown_requested.connect(shutdown_requests.append)

    controller._handle_detected_phrase("wake", "command wake")
    controller._handle_detected_phrase("shutdown", "command shut")

    assert wake_requests == ["command wake"]
    assert shutdown_requests == ["command shut"]


def test_wake_phrase_controller_toggle_armed_switches_worker_state(monkeypatch):
    build_app()
    stop_calls: list[str] = []
    ensure_calls: list[str] = []
    states: list[str] = []

    monkeypatch.setattr(wake_phrase_module, "_check_runtime_availability", lambda _config: (True, "ready"))
    monkeypatch.setattr(VoskWakePhraseController, "_ensure_worker", lambda self: ensure_calls.append("ensure"))
    monkeypatch.setattr(VoskWakePhraseController, "_stop_worker", lambda self: stop_calls.append("stop"))

    controller = VoskWakePhraseController(config=WakePhraseConfig(model_path="stub-model"))
    controller.state_changed.connect(states.append)

    controller.toggle_armed()

    assert controller.is_armed is False
    assert stop_calls == ["stop"]
    assert states == ["Wake trigger is off. Use the button to re-arm it."]

    controller.toggle_armed()

    assert controller.is_armed is True
    assert ensure_calls == ["ensure", "ensure"]
    assert states[-1].startswith("Wake trigger armed.")


def test_wake_phrase_controller_apply_config_rearms_and_starts_worker(monkeypatch):
    build_app()
    stop_calls: list[str | None] = []
    ensure_calls: list[str | None] = []
    states: list[str] = []

    monkeypatch.setattr(wake_phrase_module, "_check_runtime_availability", lambda _config: (True, "ready"))
    monkeypatch.setattr(
        VoskWakePhraseController,
        "_ensure_worker",
        lambda self: ensure_calls.append(self.config.input_device),
    )
    monkeypatch.setattr(
        VoskWakePhraseController,
        "_stop_worker",
        lambda self: stop_calls.append(self.config.input_device),
    )

    controller = VoskWakePhraseController(config=WakePhraseConfig(enabled=False, model_path="stub-model"))
    controller.state_changed.connect(states.append)
    ensure_calls.clear()
    stop_calls.clear()

    controller.apply_config(WakePhraseConfig(enabled=True, model_path="stub-model", input_device="Desk Mic"))

    assert controller.is_armed is True
    assert controller.config.input_device == "Desk Mic"
    assert ensure_calls == ["Desk Mic"]
    assert stop_calls == []
    assert states == ["Wake trigger armed. Say 'command wake' to start and 'command shut' to cancel the active voice turn."]


def test_wake_phrase_controller_apply_config_disarms_and_stops_worker(monkeypatch):
    build_app()
    stop_calls: list[str | None] = []
    ensure_calls: list[str | None] = []
    states: list[str] = []

    monkeypatch.setattr(wake_phrase_module, "_check_runtime_availability", lambda _config: (True, "ready"))
    monkeypatch.setattr(
        VoskWakePhraseController,
        "_ensure_worker",
        lambda self: ensure_calls.append(self.config.input_device),
    )
    monkeypatch.setattr(
        VoskWakePhraseController,
        "_stop_worker",
        lambda self: stop_calls.append(self.config.input_device),
    )

    controller = VoskWakePhraseController(config=WakePhraseConfig(model_path="stub-model", input_device="Desk Mic"))
    controller.state_changed.connect(states.append)
    ensure_calls.clear()
    stop_calls.clear()

    controller.apply_config(WakePhraseConfig(enabled=False, model_path="stub-model", input_device="USB Mic"))

    assert controller.is_armed is False
    assert controller.config.input_device == "USB Mic"
    assert ensure_calls == []
    assert stop_calls == ["USB Mic"]
    assert states == ["Wake trigger is off. Use the button to re-arm it."]
