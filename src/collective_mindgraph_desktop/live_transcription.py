"""Qt WebSocket client for near-real-time transcript streaming."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, QUrlQuery, Signal
from PySide6.QtWebSockets import QWebSocket

from .transcription import (
    RealtimeBackendTranscriptionConfig,
    RealtimeBackendTranscriptionService,
    StreamingTranscriptionUpdate,
    TranscriptionResult,
)


class LiveTranscriptStreamController(QObject):
    partial_received = Signal(object)
    finalized = Signal(object)
    failed = Signal(str)
    state_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._socket: QWebSocket | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(220)
        self._poll_timer.timeout.connect(self._poll_file_bytes)
        self._flush_timer = QTimer(self)
        self._flush_timer.timeout.connect(self._flush_partial)

        self._audio_path: Path | None = None
        self._config: RealtimeBackendTranscriptionConfig | None = None
        self._service: RealtimeBackendTranscriptionService | None = None
        self._byte_offset = 0
        self._frame_tail = b""
        self._ready = False
        self._pending_finalize = False
        self._finalize_sent = False
        self._cancelled = False
        self._had_partial = False

    @property
    def is_active(self) -> bool:
        return self._socket is not None

    def start(self, audio_path: str | Path, config: RealtimeBackendTranscriptionConfig) -> None:
        if self._socket is not None:
            raise ValueError("Live transcript stream is already active.")

        self._audio_path = Path(audio_path).expanduser().resolve()
        self._config = config
        self._service = RealtimeBackendTranscriptionService(config=config)
        self._byte_offset = 0
        self._frame_tail = b""
        self._ready = False
        self._pending_finalize = False
        self._finalize_sent = False
        self._cancelled = False
        self._had_partial = False
        self._flush_timer.setInterval(max(250, config.stream_flush_interval_ms))

        socket = QWebSocket()
        socket.connected.connect(self._handle_connected)
        socket.textMessageReceived.connect(self._handle_message)
        socket.errorOccurred.connect(self._handle_error)
        socket.disconnected.connect(self._handle_disconnected)
        self._socket = socket

        url = QUrl(config.websocket_stream_url())
        if config.language:
            query = QUrlQuery()
            query.addQueryItem("language", config.language)
            url.setQuery(query)

        self.state_changed.emit("Connecting live transcript stream to the local backend.")
        socket.open(url)

    def finalize(self) -> None:
        if self._socket is None:
            return
        self._pending_finalize = True
        self._poll_file_bytes()
        self._send_finalize_if_ready()

    def cancel(self) -> None:
        if self._socket is None:
            return
        self._cancelled = True
        self._stop_timers()
        self._safe_send_text({"event": "close"})
        self._socket.abort()
        self._cleanup_socket()
        self.state_changed.emit("Live transcript stream cancelled.")

    def _handle_connected(self) -> None:
        self.state_changed.emit("Live transcript connection opened.")

    def _handle_message(self, payload: str) -> None:
        try:
            message = json.loads(payload)
        except json.JSONDecodeError:
            self.failed.emit("Live transcript stream returned invalid JSON.")
            self.cancel()
            return
        if not isinstance(message, dict):
            return

        event = str(message.get("event") or "")
        if event == "ready":
            self._ready = True
            self._poll_timer.start()
            self._flush_timer.start()
            self.state_changed.emit("Live transcript stream is ready.")
            return
        if event == "partial_transcript":
            if self._service is None or self._audio_path is None:
                return
            update = self._service.stream_update_from_payload(message, self._audio_path)
            self._had_partial = True
            self.partial_received.emit(update)
            return
        if event == "final_transcript":
            if self._service is None or self._audio_path is None:
                return
            result = self._service.result_from_payload(message, self._audio_path)
            self.finalized.emit(result)
            self._cancelled = True
            self._stop_timers()
            if self._socket is not None:
                self._socket.close()
            return

    def _handle_error(self, _error) -> None:
        if self._socket is None or self._cancelled:
            return
        self.failed.emit(self._socket.errorString() or "Live transcript stream failed.")
        self.cancel()

    def _handle_disconnected(self) -> None:
        had_pending_finalize = self._pending_finalize or self._finalize_sent
        self._stop_timers()
        self._cleanup_socket()
        if self._cancelled:
            return
        if had_pending_finalize and self._had_partial:
            self.state_changed.emit("Live transcript stream closed after finalization.")
            return
        self.failed.emit("Live transcript stream disconnected before the final transcript arrived.")

    def _poll_file_bytes(self) -> None:
        if self._socket is None or not self._ready or self._audio_path is None:
            return
        if not self._audio_path.exists():
            return

        raw_bytes = self._audio_path.read_bytes()
        if len(raw_bytes) <= 44:
            return
        payload = raw_bytes[44 + self._byte_offset :]
        if not payload:
            self._send_finalize_if_ready()
            return

        self._byte_offset += len(payload)
        data = self._frame_tail + payload
        even_length = len(data) - (len(data) % 2)
        if even_length <= 0:
            self._frame_tail = data
            return

        self._frame_tail = data[even_length:]
        self._socket.sendBinaryMessage(data[:even_length])
        self._send_finalize_if_ready()

    def _flush_partial(self) -> None:
        if self._socket is None or not self._ready or self._pending_finalize:
            return
        self._safe_send_text({"event": "flush"})

    def _send_finalize_if_ready(self) -> None:
        if (
            self._socket is None
            or not self._ready
            or not self._pending_finalize
            or self._finalize_sent
            or self._frame_tail
        ):
            return
        self._finalize_sent = True
        self._stop_timers()
        self._safe_send_text({"event": "finalize"})
        self.state_changed.emit("Finalizing live transcript stream.")

    def _safe_send_text(self, payload: dict[str, object]) -> None:
        if self._socket is None:
            return
        self._socket.sendTextMessage(json.dumps(payload))

    def _stop_timers(self) -> None:
        self._poll_timer.stop()
        self._flush_timer.stop()

    def _cleanup_socket(self) -> None:
        if self._socket is not None:
            self._socket.deleteLater()
        self._socket = None

