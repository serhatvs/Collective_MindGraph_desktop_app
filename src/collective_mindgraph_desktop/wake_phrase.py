"""Optional VOSK-based wake phrase listener for hands-free voice capture."""

from __future__ import annotations

from dataclasses import dataclass, replace
import importlib.util
import json
from pathlib import Path
from queue import Empty, Full, Queue
import re
import threading
import time

from PySide6.QtCore import QObject, QThread, Signal, Slot

from .runtime_paths import wake_phrase_model_candidates


DEFAULT_WAKE_PHRASE = "command wake"
DEFAULT_SHUTDOWN_PHRASE = "command shut"


@dataclass(frozen=True, slots=True)
class WakePhraseConfig:
    enabled: bool = True
    wake_phrase: str = DEFAULT_WAKE_PHRASE
    shutdown_phrase: str = DEFAULT_SHUTDOWN_PHRASE
    sample_rate: int = 16000
    block_size: int = 8000
    cooldown_seconds: float = 2.0
    model_path: str | None = None
    input_device: int | str | None = None

    @classmethod
    def from_env(cls) -> "WakePhraseConfig":
        model_path = None
        for candidate in _default_model_candidates():
            if candidate.exists():
                model_path = str(candidate)
                break
        return cls(model_path=model_path)


class VoskWakePhraseController(QObject):
    wake_requested = Signal(str)
    shutdown_requested = Signal(str)
    state_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, config: WakePhraseConfig | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config or WakePhraseConfig.from_env()
        self._armed = self._config.enabled
        self._suspended = False
        self._worker_thread: QThread | None = None
        self._worker: _VoskWakePhraseWorker | None = None
        self._desired_running = False
        self._available, self._availability_message = _check_runtime_availability(self._config)

        self._refresh_runtime_state()

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
        if not self._available:
            return self._availability_message
        if not self._armed:
            return "Wake trigger is off. Use the button to re-arm it."
        if self._suspended:
            return "Wake trigger paused while the app is recording or transcribing."
        return (
            f"Wake trigger armed. Say '{self._config.wake_phrase}' to start and "
            f"'{self._config.shutdown_phrase}' to cancel the active voice turn."
        )

    def apply_config(self, config: WakePhraseConfig) -> None:
        self._config = config
        self._armed = config.enabled
        self._refresh_runtime_state()

    def arm(self) -> None:
        self._armed = True
        self._refresh_runtime_state()

    def disarm(self) -> None:
        self._armed = False
        self._refresh_runtime_state()

    def suspend(self) -> None:
        self._suspended = True
        self._refresh_runtime_state()

    def resume(self) -> None:
        self._suspended = False
        self._refresh_runtime_state()

    def toggle_armed(self) -> None:
        if self._armed:
            self.disarm()
            return
        self.arm()

    def set_input_device(self, input_device: int | str | None) -> None:
        if self._config.input_device == input_device:
            return
        self._config = replace(self._config, input_device=input_device)
        if self._worker_thread is not None:
            self._stop_worker()
            self.state_changed.emit(self.status_text())
            return
        self._refresh_runtime_state()

    def shutdown(self) -> None:
        self._desired_running = False
        self._stop_worker()

    def _refresh_runtime_state(self) -> None:
        self._desired_running = self._available and self._armed and not self._suspended
        if self._desired_running:
            self._ensure_worker()
        else:
            self._stop_worker()
        self.state_changed.emit(self.status_text())

    def _ensure_worker(self) -> None:
        if self._worker_thread is not None or not self._available:
            return
        self._worker_thread = QThread(self)
        self._worker = _VoskWakePhraseWorker(self._config)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.detected.connect(self._handle_detected_phrase)
        self._worker.failed.connect(self._handle_worker_failure)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.finished.connect(self._cleanup_worker)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.start()

    def _stop_worker(self) -> None:
        if self._worker is not None:
            self._worker.stop()

    @Slot(str, str)
    def _handle_detected_phrase(self, phrase_type: str, recognized_text: str) -> None:
        if phrase_type == "shutdown":
            self.shutdown_requested.emit(recognized_text)
            return
        self.wake_requested.emit(recognized_text)

    @Slot(str)
    def _handle_worker_failure(self, message: str) -> None:
        self._available = False
        self._availability_message = message
        self._desired_running = False
        self._armed = False
        self.error_occurred.emit(message)
        self.state_changed.emit(self.status_text())

    @Slot()
    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
        self._worker = None
        self._worker_thread = None
        if self._desired_running:
            self._ensure_worker()


class _VoskWakePhraseWorker(QObject):
    detected = Signal(str, str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, config: WakePhraseConfig) -> None:
        super().__init__()
        self._config = config
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    @Slot()
    def run(self) -> None:
        try:
            from vosk import KaldiRecognizer, Model, SetLogLevel
            import sounddevice as sd
        except ImportError:
            self.failed.emit("VOSK wake trigger is unavailable. Install `vosk` and `sounddevice`.")
            self.finished.emit()
            return

        model_path = _resolve_model_path(self._config)
        if model_path is None:
            self.failed.emit(
                "No VOSK English model was found. Put one under `wake_phrase_models/` or set "
                "`CMG_WAKE_PHRASE_MODEL_PATH`."
            )
            self.finished.emit()
            return

        try:
            SetLogLevel(-1)
            model = Model(str(model_path))
            recognizer = KaldiRecognizer(
                model,
                self._config.sample_rate,
                json.dumps(_recognizer_grammar(self._config)),
            )
            audio_queue: Queue[bytes] = Queue(maxsize=24)
            last_detection_type: str | None = None
            last_detection_at = 0.0

            def callback(indata, _frames, _time_info, _status) -> None:
                if self._stop_event.is_set():
                    return
                try:
                    audio_queue.put_nowait(bytes(indata))
                except Full:
                    try:
                        audio_queue.get_nowait()
                    except Empty:
                        pass
                    try:
                        audio_queue.put_nowait(bytes(indata))
                    except Full:
                        return

            stream_kwargs: dict[str, object] = {
                "samplerate": self._config.sample_rate,
                "blocksize": self._config.block_size,
                "dtype": "int16",
                "channels": 1,
                "callback": callback,
            }
            resolved_input_device = _resolve_stream_input_device(sd, self._config.input_device)
            if resolved_input_device is not None:
                stream_kwargs["device"] = resolved_input_device

            with sd.RawInputStream(**stream_kwargs):
                while not self._stop_event.is_set():
                    try:
                        chunk = audio_queue.get(timeout=0.25)
                    except Empty:
                        continue

                    texts: list[str] = []
                    if recognizer.AcceptWaveform(chunk):
                        texts.append(_extract_vosk_text(recognizer.Result()))
                    else:
                        texts.append(_extract_vosk_text(recognizer.PartialResult()))

                    for text in texts:
                        phrase_type = detect_control_phrase(
                            text=text,
                            wake_phrase=self._config.wake_phrase,
                            shutdown_phrase=self._config.shutdown_phrase,
                        )
                        if phrase_type is None:
                            continue
                        now = time.monotonic()
                        if (
                            phrase_type == last_detection_type
                            and (now - last_detection_at) < self._config.cooldown_seconds
                        ):
                            continue
                        last_detection_type = phrase_type
                        last_detection_at = now
                        self.detected.emit(phrase_type, normalize_command_text(text))
        except Exception as exc:
            self.failed.emit(f"VOSK wake trigger failed: {exc}")
        finally:
            self.finished.emit()


def normalize_command_text(text: str) -> str:
    collapsed = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return " ".join(collapsed.split())


def detect_control_phrase(text: str, wake_phrase: str, shutdown_phrase: str) -> str | None:
    normalized_text = normalize_command_text(text)
    if not normalized_text:
        return None

    if _matches_phrase(normalized_text, wake_phrase):
        return "wake"
    if _matches_phrase(normalized_text, shutdown_phrase):
        return "shutdown"
    return None


def phrase_variants(phrase: str) -> list[str]:
    normalized = normalize_command_text(phrase)
    if not normalized:
        return []

    pending = [tuple(normalized.split())]
    variants: set[str] = set()

    while pending:
        tokens = pending.pop()
        rendered = " ".join(tokens).strip()
        if not rendered or rendered in variants:
            continue
        variants.add(rendered)

        if tokens and tokens[0] == "i" and len(tokens) > 1:
            pending.append(tokens[1:])
        if len(tokens) >= 2:
            merged_tail = _merge_compound_tail(tokens)
            if merged_tail is not None:
                pending.append(merged_tail)
        split_tail = _split_compound_tail(tokens)
        if split_tail is not None:
            pending.append(split_tail)
        if len(tokens) >= 3 and tokens[-1] in {"up", "down"}:
            pending.append(tokens[:-1])

    return sorted(variants, key=lambda item: (len(item.split()), item))


def _matches_phrase(normalized_text: str, phrase: str) -> bool:
    for variant in phrase_variants(phrase):
        if variant in normalized_text:
            return True
        if _ordered_suffix_match(normalized_text.split(), variant.split()):
            return True
    return False


def _ordered_suffix_match(text_tokens: list[str], phrase_tokens: list[str]) -> bool:
    if not text_tokens or not phrase_tokens:
        return False
    if len(text_tokens) < len(phrase_tokens):
        return False
    return text_tokens[-len(phrase_tokens) :] == phrase_tokens


def _recognizer_grammar(config: WakePhraseConfig) -> list[str]:
    phrases = set(phrase_variants(config.wake_phrase))
    phrases.update(phrase_variants(config.shutdown_phrase))
    phrases.add("[unk]")
    return sorted(phrases)


def _merge_compound_tail(tokens: tuple[str, ...]) -> tuple[str, ...] | None:
    if len(tokens) < 2:
        return None
    if tokens[-2:] == ("wake", "up") or tokens[-2:] == ("shut", "down"):
        return tokens[:-2] + ("".join(tokens[-2:]),)
    return None


def _split_compound_tail(tokens: tuple[str, ...]) -> tuple[str, ...] | None:
    if not tokens:
        return None
    if tokens[-1] == "wakeup":
        return tokens[:-1] + ("wake", "up")
    if tokens[-1] == "shutdown":
        return tokens[:-1] + ("shut", "down")
    return None


def _extract_vosk_text(payload: str) -> str:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return ""
    text = data.get("text") or data.get("partial") or ""
    return str(text).strip()


def _check_runtime_availability(config: WakePhraseConfig) -> tuple[bool, str]:
    if importlib.util.find_spec("vosk") is None:
        return False, "Wake trigger unavailable: install `vosk`."
    if importlib.util.find_spec("sounddevice") is None:
        return False, "Wake trigger unavailable: install `sounddevice`."
    if _resolve_model_path(config) is None:
        return (
            False,
            "Wake trigger unavailable: no VOSK English model found. Use `wake_phrase_models/` or "
            "`CMG_WAKE_PHRASE_MODEL_PATH`.",
        )
    return True, ""


def describe_stream_input_device(selector: int | str | None) -> str:
    if selector is None:
        return "System default"

    try:
        import sounddevice as sd
    except ImportError:
        return "Unavailable (`sounddevice` missing)"

    resolved_index = _resolve_stream_input_device(sd, selector)
    if resolved_index is None:
        return f"Unmatched ({selector})"

    try:
        device = sd.query_devices(resolved_index)
    except Exception:
        return f"Input #{resolved_index}"
    name = str(device.get("name") or "").strip()
    return name or f"Input #{resolved_index}"


def _resolve_stream_input_device(sounddevice_module, selector: int | str | None) -> int | None:
    if selector is None or isinstance(selector, int):
        return selector

    normalized_selector = normalize_command_text(selector)
    if not normalized_selector:
        return None

    candidates: list[tuple[int, str]] = []
    for index, device in enumerate(sounddevice_module.query_devices()):
        if int(device.get("max_input_channels", 0)) <= 0:
            continue
        normalized_name = normalize_command_text(str(device.get("name") or ""))
        if not normalized_name:
            continue
        if normalized_name == normalized_selector:
            return index
        candidates.append((index, normalized_name))

    for index, normalized_name in candidates:
        if normalized_selector in normalized_name or normalized_name in normalized_selector:
            return index

    selector_tokens = set(normalized_selector.split())
    best_index: int | None = None
    best_score = 0
    for index, normalized_name in candidates:
        score = len(selector_tokens & set(normalized_name.split()))
        if score >= 2 and score > best_score:
            best_score = score
            best_index = index
    return best_index


def _resolve_model_path(config: WakePhraseConfig) -> Path | None:
    if config.model_path:
        candidate = Path(config.model_path).expanduser().resolve()
        if candidate.exists():
            return candidate
    for candidate in _default_model_candidates():
        if candidate.exists():
            return candidate.resolve()
    return None


def _default_model_candidates() -> list[Path]:
    env_path = _read_env_path("CMG_WAKE_PHRASE_MODEL_PATH")
    candidates = []
    if env_path is not None:
        candidates.append(env_path)
    candidates.extend(wake_phrase_model_candidates())
    return candidates


def _read_env_path(name: str) -> Path | None:
    import os

    value = (os.getenv(name) or "").strip()
    if not value:
        return None
    return Path(value).expanduser()
