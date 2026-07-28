"""Typed Qt WebSocket and QAudioSource client for live PCM capture."""

from __future__ import annotations

import json
import urllib.parse
import wave
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QIODevice, QObject, QUrl, Signal
from PySide6.QtMultimedia import (
    QAudioFormat,
    QAudioSource,
    QMediaDevices,
)
from PySide6.QtWebSockets import QWebSocket

from .audio_capture import _audio_device_identifier
from .contracts import TranscriptionPreferences
from .runtime_paths import app_storage_dir


class LiveCaptureClient(QObject):
    partial_transcript = Signal(str)
    progress_changed = Signal(int, str)
    finalized = Signal(str)
    fallback_ready = Signal(str)
    error_occurred = Signal(str)
    recording_changed = Signal(bool)

    def __init__(self, base_url: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._base_url = base_url
        self._socket = QWebSocket(parent=self)
        self._socket.connected.connect(self._connected)
        self._socket.textMessageReceived.connect(self._message_received)
        self._socket.disconnected.connect(self._disconnected)
        self._socket.errorOccurred.connect(lambda _error: self._fail(self._socket.errorString()))
        self._audio: QAudioSource | None = None
        self._audio_device: QIODevice | None = None
        self._spool_handle: wave.Wave_write | None = None
        self._spool_path: Path | None = None
        self._final_received = False
        self._stop_requested = False

    @property
    def is_recording(self) -> bool:
        return self._audio is not None

    def start(
        self,
        meeting_id: int,
        *,
        device_id: str | None,
        preferences: TranscriptionPreferences,
    ) -> None:
        if self.is_recording:
            raise ValueError("Live audio capture is already running.")
        self._reset_state()
        self._prepare_spool()
        query = urllib.parse.urlencode(
            {
                key: value
                for key, value in {
                    "language": preferences.language,
                    "quality_mode": preferences.quality_mode,
                    "session_glossary": ",".join(preferences.glossary) or None,
                    "hotwords": ",".join(preferences.hotwords) or None,
                }.items()
                if value is not None
            }
        )
        parsed = urllib.parse.urlparse(self._base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        path = f"/api/v1/meetings/{meeting_id}/recordings/live"
        url = urllib.parse.urlunparse((scheme, parsed.netloc, path, "", query, ""))
        self._pending_device_id = device_id
        self.progress_changed.emit(0, "connecting")
        self._socket.open(QUrl(url))

    def stop(self) -> None:
        if not self.is_recording:
            raise ValueError("Live audio capture is not running.")
        self._stop_requested = True
        self._stop_audio()
        self.progress_changed.emit(90, "finalizing")
        self._socket.sendTextMessage('{"event":"finalize"}')

    def abort(self) -> None:
        self._stop_requested = True
        self._stop_audio()
        self._socket.close()

    def _connected(self) -> None:
        try:
            device = _select_device(self._pending_device_id)
            audio_format = QAudioFormat()
            audio_format.setSampleRate(16_000)
            audio_format.setChannelCount(1)
            audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            self._audio = QAudioSource(device, audio_format, self)
            self._audio_device = self._audio.start()
            self._audio_device.readyRead.connect(self._audio_ready)
            self.recording_changed.emit(True)
            self.progress_changed.emit(5, "capturing")
        except Exception as exc:
            self._fail(str(exc))

    def _audio_ready(self) -> None:
        if self._audio_device is None:
            return
        chunk = bytes(self._audio_device.readAll())
        if not chunk:
            return
        if self._spool_handle is not None:
            self._spool_handle.writeframesraw(chunk)
        self._socket.sendBinaryMessage(chunk)

    def _message_received(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self._fail("The live engine returned invalid JSON.")
            return
        event = str(payload.get("event") or "")
        if event == "ready":
            self.progress_changed.emit(10, "ready")
            return
        if event == "progress":
            self.progress_changed.emit(
                int(payload.get("progress") or 0),
                str(payload.get("stage") or ""),
            )
            return
        if event == "partial_transcript":
            self.partial_transcript.emit(str(payload.get("corrected_text_output") or ""))
            self.progress_changed.emit(65, "transcribing")
            return
        if event == "final_transcript":
            self._final_received = True
            self._close_spool(delete=True)
            self.progress_changed.emit(100, "completed")
            self.finalized.emit(str(payload.get("corrected_text_output") or ""))
            self._socket.close()

    def _disconnected(self) -> None:
        was_recording = self.is_recording
        self._stop_audio()
        if (was_recording or self._stop_requested) and not self._final_received:
            self._close_spool(delete=False)
            if self._spool_path is not None and self._spool_path.is_file():
                self.fallback_ready.emit(str(self._spool_path))
        elif not self._final_received:
            self._close_spool(delete=False)

    def _fail(self, detail: str) -> None:
        self.error_occurred.emit(detail or "Live audio capture failed.")
        if self._socket.isValid():
            self._socket.close()
        else:
            self._disconnected()

    def _stop_audio(self) -> None:
        if self._audio is not None:
            self._audio.stop()
            self._audio.deleteLater()
        self._audio = None
        self._audio_device = None
        self._close_spool(delete=False)
        self.recording_changed.emit(False)

    def _prepare_spool(self) -> None:
        spool_dir = app_storage_dir() / "temp" / "live-spool"
        spool_dir.mkdir(parents=True, exist_ok=True)
        self._spool_path = spool_dir / f"{uuid4()}.wav"
        self._spool_handle = wave.open(str(self._spool_path), "wb")
        self._spool_handle.setnchannels(1)
        self._spool_handle.setsampwidth(2)
        self._spool_handle.setframerate(16_000)

    def _close_spool(self, *, delete: bool) -> None:
        if self._spool_handle is not None:
            self._spool_handle.close()
            self._spool_handle = None
        if delete and self._spool_path is not None:
            self._spool_path.unlink(missing_ok=True)

    def _reset_state(self) -> None:
        self._final_received = False
        self._stop_requested = False
        self._pending_device_id: str | None = None
        self._spool_path = None


def _select_device(device_id: str | None):
    devices = QMediaDevices.audioInputs()
    if not devices:
        raise ValueError("No microphone input device is available.")
    if device_id:
        for device in devices:
            if _audio_device_identifier(device) == device_id:
                return device
        raise ValueError("Selected microphone input device is no longer available.")
    return QMediaDevices.defaultAudioInput()
