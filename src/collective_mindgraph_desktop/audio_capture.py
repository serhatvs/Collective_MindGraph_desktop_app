"""Qt audio capture adapter for microphone recording."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
from datetime import UTC, datetime
import math
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioInput, QMediaCaptureSession, QMediaDevices, QMediaFormat, QMediaRecorder

from .runtime_paths import default_recordings_dir


@dataclass(frozen=True, slots=True)
class AutoStopConfig:
    enabled: bool = True
    poll_interval_ms: int = 250
    min_speech_seconds: float = 0.35
    silence_seconds: float = 1.25
    silence_threshold: float = 0.012


@dataclass(frozen=True, slots=True)
class AudioInputDeviceInfo:
    device_id: str
    label: str
    is_default: bool = False


class SilenceWindowTracker:
    def __init__(self, config: AutoStopConfig | None = None) -> None:
        self._config = config or AutoStopConfig()
        self._speech_run_seconds = 0.0
        self._silence_run_seconds = 0.0
        self._heard_speech = False

    @property
    def heard_speech(self) -> bool:
        return self._heard_speech

    def reset(self) -> None:
        self._speech_run_seconds = 0.0
        self._silence_run_seconds = 0.0
        self._heard_speech = False

    def observe(self, rms_level: float, duration_seconds: float) -> bool:
        if duration_seconds <= 0:
            return False

        if rms_level >= self._config.silence_threshold:
            self._speech_run_seconds += duration_seconds
            self._silence_run_seconds = 0.0
            if self._speech_run_seconds >= self._config.min_speech_seconds:
                self._heard_speech = True
            return False

        self._speech_run_seconds = 0.0
        if not self._heard_speech:
            return False
        self._silence_run_seconds += duration_seconds
        return self._silence_run_seconds >= self._config.silence_seconds


class AudioCaptureController(QObject):
    recording_started = Signal(str)
    recording_stopped = Signal(str)
    recording_auto_stopped = Signal(str)
    capture_cleared = Signal()
    error_occurred = Signal(str)

    def __init__(
        self,
        recordings_dir: Path | None = None,
        auto_stop_config: AutoStopConfig | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._recordings_dir = (recordings_dir or self._default_recordings_dir()).resolve()
        self._recordings_dir.mkdir(parents=True, exist_ok=True)
        self._auto_stop_config = auto_stop_config or AutoStopConfig()
        self._silence_tracker = SilenceWindowTracker(self._auto_stop_config)

        self._capture_session = QMediaCaptureSession(self)
        self._audio_input = QAudioInput(self)
        if QMediaDevices.audioInputs():
            self._audio_input.setDevice(QMediaDevices.audioInputs()[0])
        self._capture_session.setAudioInput(self._audio_input)

        self._recorder = QMediaRecorder(self)
        self._capture_session.setRecorder(self._recorder)

        media_format = QMediaFormat()
        media_format.setFileFormat(QMediaFormat.FileFormat.Wave)
        media_format.setAudioCodec(QMediaFormat.AudioCodec.Wave)
        self._recorder.setMediaFormat(media_format)
        self._recorder.setAudioChannelCount(1)
        self._recorder.setAudioSampleRate(16000)
        self._recorder.setQuality(QMediaRecorder.Quality.NormalQuality)

        self._pending_output_path: Path | None = None
        self._current_output_path: Path | None = None
        self._discard_on_stop = False
        self._auto_stop_pending = False
        self._monitor_byte_offset = 0
        self._monitor_timer = QTimer(self)
        self._monitor_timer.setInterval(self._auto_stop_config.poll_interval_ms)
        self._monitor_timer.timeout.connect(self._poll_for_silence)

        self._recorder.actualLocationChanged.connect(self._handle_actual_location_changed)
        self._recorder.recorderStateChanged.connect(self._handle_recorder_state_changed)
        self._recorder.errorChanged.connect(self._handle_error_changed)

    @property
    def current_output_path(self) -> Path | None:
        return self._current_output_path

    @property
    def auto_stop_config(self) -> AutoStopConfig:
        return self._auto_stop_config

    def has_audio_input(self) -> bool:
        return bool(QMediaDevices.audioInputs())

    def set_auto_stop_config(self, config: AutoStopConfig) -> None:
        self._auto_stop_config = config
        self._silence_tracker = SilenceWindowTracker(config)
        self._monitor_timer.setInterval(config.poll_interval_ms)

    def available_audio_inputs(self) -> list[AudioInputDeviceInfo]:
        default_device_id = _audio_device_identifier(QMediaDevices.defaultAudioInput())
        return [
            AudioInputDeviceInfo(
                device_id=_audio_device_identifier(device),
                label=device.description(),
                is_default=_audio_device_identifier(device) == default_device_id,
            )
            for device in QMediaDevices.audioInputs()
        ]

    def selected_audio_input(self) -> AudioInputDeviceInfo | None:
        if not self.has_audio_input():
            return None
        current_device = self._audio_input.device()
        current_id = _audio_device_identifier(current_device)
        default_id = _audio_device_identifier(QMediaDevices.defaultAudioInput())
        return AudioInputDeviceInfo(
            device_id=current_id,
            label=current_device.description(),
            is_default=current_id == default_id,
        )

    def set_audio_input_by_id(self, device_id: str | None) -> AudioInputDeviceInfo | None:
        if not self.has_audio_input():
            raise ValueError("No microphone input device is available.")
        if self._recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState:
            raise ValueError("Cannot change microphone input while recording is active.")

        target_device = None
        if device_id:
            target_device = _find_audio_input(device_id)
            if target_device is None:
                raise ValueError("Selected microphone input device is no longer available.")
        else:
            target_device = QMediaDevices.defaultAudioInput()

        self._audio_input.setDevice(target_device)
        return self.selected_audio_input()

    def start_recording(self) -> Path:
        if not self.has_audio_input():
            raise ValueError("No microphone input device is available.")
        if self._recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState:
            raise ValueError("Audio capture is already running.")

        self.discard_current_capture()
        self._discard_on_stop = False
        self._auto_stop_pending = False
        self._pending_output_path = self._build_output_path()
        self._current_output_path = None
        self._monitor_byte_offset = 0
        self._silence_tracker.reset()
        self._recorder.setOutputLocation(QUrl.fromLocalFile(str(self._pending_output_path)))
        self._recorder.record()
        return self._pending_output_path

    def stop_recording(self) -> None:
        if self._recorder.recorderState() != QMediaRecorder.RecorderState.RecordingState:
            raise ValueError("Audio capture is not currently running.")
        self._recorder.stop()

    def clear_capture(self) -> None:
        if self._recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState:
            self._discard_on_stop = True
            self._recorder.stop()
            return
        self.discard_current_capture()
        self.capture_cleared.emit()

    def discard_current_capture(self) -> None:
        self._monitor_timer.stop()
        for path in {self._pending_output_path, self._current_output_path}:
            if path is not None and path.exists():
                path.unlink(missing_ok=True)
        self._pending_output_path = None
        self._current_output_path = None
        self._monitor_byte_offset = 0
        self._auto_stop_pending = False
        self._silence_tracker.reset()

    def _handle_actual_location_changed(self, location: QUrl) -> None:
        if location.isLocalFile():
            self._current_output_path = Path(location.toLocalFile())

    def _handle_recorder_state_changed(self, state: QMediaRecorder.RecorderState) -> None:
        if state == QMediaRecorder.RecorderState.RecordingState and self._pending_output_path is not None:
            if self._auto_stop_config.enabled:
                self._monitor_timer.start()
            self.recording_started.emit(str(self._pending_output_path))
            return

        if state != QMediaRecorder.RecorderState.StoppedState:
            return

        self._monitor_timer.stop()

        output_path = self._current_output_path or self._pending_output_path
        if self._discard_on_stop:
            if output_path is not None and output_path.exists():
                output_path.unlink(missing_ok=True)
            self._pending_output_path = None
            self._current_output_path = None
            self._discard_on_stop = False
            self.capture_cleared.emit()
            return

        self._pending_output_path = None
        if output_path is None or not output_path.exists():
            self._current_output_path = None
            self.error_occurred.emit("Audio capture stopped, but no recording file was created.")
            return
        self._current_output_path = output_path
        if self._auto_stop_pending:
            self._auto_stop_pending = False
            self.recording_auto_stopped.emit(str(output_path))
        self.recording_stopped.emit(str(output_path))

    def _handle_error_changed(self) -> None:
        if self._recorder.error() == QMediaRecorder.Error.NoError:
            return
        self.error_occurred.emit(self._recorder.errorString() or "Audio capture failed.")

    def _poll_for_silence(self) -> None:
        if not self._auto_stop_config.enabled:
            return
        if self._recorder.recorderState() != QMediaRecorder.RecorderState.RecordingState:
            return

        output_path = self._current_output_path or self._pending_output_path
        if output_path is None or not output_path.exists():
            return

        rms_level, duration_seconds, consumed_bytes = _read_incremental_pcm_level(
            output_path,
            byte_offset=self._monitor_byte_offset,
        )
        self._monitor_byte_offset += consumed_bytes
        if self._silence_tracker.observe(rms_level, duration_seconds):
            self._auto_stop_pending = True
            self._recorder.stop()

    def _build_output_path(self) -> Path:
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
        return self._recordings_dir / f"voice_command_{timestamp}.wav"

    @staticmethod
    def _default_recordings_dir() -> Path:
        return default_recordings_dir()


def _read_incremental_pcm_level(path: Path, byte_offset: int, header_size: int = 44) -> tuple[float, float, int]:
    raw_bytes = path.read_bytes()
    if len(raw_bytes) <= header_size or byte_offset >= len(raw_bytes) - header_size:
        return 0.0, 0.0, 0

    payload = raw_bytes[header_size + byte_offset :]
    even_length = len(payload) - (len(payload) % 2)
    if even_length <= 0:
        return 0.0, 0.0, 0

    chunk = payload[:even_length]
    samples = array("h")
    samples.frombytes(chunk)
    if not samples:
        return 0.0, 0.0, 0

    normalized_sum = 0.0
    for sample in samples:
        normalized = sample / 32768.0
        normalized_sum += normalized * normalized
    rms_level = math.sqrt(normalized_sum / len(samples))
    duration_seconds = len(samples) / 16000.0
    return rms_level, duration_seconds, even_length


def _find_audio_input(device_id: str) -> object | None:
    normalized_id = device_id.strip()
    for device in QMediaDevices.audioInputs():
        if _audio_device_identifier(device) == normalized_id:
            return device
    return None


def _audio_device_identifier(device) -> str:
    return bytes(device.id()).decode("utf-8", errors="ignore")
