"""Qt audio capture adapter for microphone recording."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioInput, QMediaCaptureSession, QMediaDevices, QMediaFormat, QMediaRecorder


class AudioCaptureController(QObject):
    recording_started = Signal(str)
    recording_stopped = Signal(str)
    capture_cleared = Signal()
    error_occurred = Signal(str)

    def __init__(self, recordings_dir: Path | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._recordings_dir = (recordings_dir or self._default_recordings_dir()).resolve()
        self._recordings_dir.mkdir(parents=True, exist_ok=True)

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

        self._recorder.actualLocationChanged.connect(self._handle_actual_location_changed)
        self._recorder.recorderStateChanged.connect(self._handle_recorder_state_changed)
        self._recorder.errorChanged.connect(self._handle_error_changed)

    @property
    def current_output_path(self) -> Path | None:
        return self._current_output_path

    def has_audio_input(self) -> bool:
        return bool(QMediaDevices.audioInputs())

    def start_recording(self) -> Path:
        if not self.has_audio_input():
            raise ValueError("No microphone input device is available.")
        if self._recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState:
            raise ValueError("Audio capture is already running.")

        self.discard_current_capture()
        self._discard_on_stop = False
        self._pending_output_path = self._build_output_path()
        self._current_output_path = None
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
        for path in {self._pending_output_path, self._current_output_path}:
            if path is not None and path.exists():
                path.unlink(missing_ok=True)
        self._pending_output_path = None
        self._current_output_path = None

    def _handle_actual_location_changed(self, location: QUrl) -> None:
        if location.isLocalFile():
            self._current_output_path = Path(location.toLocalFile())

    def _handle_recorder_state_changed(self, state: QMediaRecorder.RecorderState) -> None:
        if state == QMediaRecorder.RecorderState.RecordingState and self._pending_output_path is not None:
            self.recording_started.emit(str(self._pending_output_path))
            return

        if state != QMediaRecorder.RecorderState.StoppedState:
            return

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
        self.recording_stopped.emit(str(output_path))

    def _handle_error_changed(self) -> None:
        if self._recorder.error() == QMediaRecorder.Error.NoError:
            return
        self.error_occurred.emit(self._recorder.errorString() or "Audio capture failed.")

    def _build_output_path(self) -> Path:
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
        return self._recordings_dir / f"voice_command_{timestamp}.wav"

    @staticmethod
    def _default_recordings_dir() -> Path:
        return Path.cwd() / "recordings"
