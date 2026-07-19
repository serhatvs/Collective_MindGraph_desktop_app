from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import WebSocketDisconnect

from app.api.ws import transcribe_stream
from app.models import ConversationTranscript


class StubStreamingService:
    def __init__(self, transcript: ConversationTranscript) -> None:
        self.transcript = transcript
        self.discarded_ids: list[str] = []
        self.finalized_ids: list[str] = []

    def create_session(self, **_kwargs):
        return SimpleNamespace(conversation_id=self.transcript.conversation_id)

    async def append_audio(self, _conversation_id: str, _chunk: bytes):
        return None

    async def flush_partial(self, _conversation_id: str) -> ConversationTranscript:
        return self.transcript

    async def finalize(self, conversation_id: str) -> ConversationTranscript:
        self.finalized_ids.append(conversation_id)
        return self.transcript

    def discard_session(self, conversation_id: str) -> None:
        self.discarded_ids.append(conversation_id)


class StubWebSocket:
    def __init__(self, service: StubStreamingService, incoming: list[dict[str, object] | BaseException]) -> None:
        self.app = SimpleNamespace(
            state=SimpleNamespace(
                streaming_service=service,
                settings=SimpleNamespace(
                    sample_rate=16_000,
                    channels=1,
                    stream_partial_window_seconds=8.0,
                    stream_overlap_seconds=1.5,
                ),
            )
        )
        self.query_params: dict[str, str] = {}
        self.incoming = list(incoming)
        self.sent: list[dict[str, object]] = []
        self.accepted = False
        self.closed = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent.append(payload)

    async def receive(self) -> dict[str, object]:
        if not self.incoming:
            raise AssertionError("The endpoint waited for another message after completion.")
        message = self.incoming.pop(0)
        if isinstance(message, BaseException):
            raise message
        return message

    async def close(self) -> None:
        self.closed = True


def build_websocket(incoming: list[dict[str, object] | BaseException]):
    transcript = ConversationTranscript(conversation_id="conv_ws", source="stream")
    service = StubStreamingService(transcript)
    return StubWebSocket(service, incoming), service


@pytest.mark.asyncio
async def test_websocket_discards_session_after_finalize_and_returns():
    websocket, service = build_websocket(
        [{"text": json.dumps({"event": "finalize"})}],
    )

    await transcribe_stream(websocket)

    assert websocket.accepted is True
    assert service.finalized_ids == ["conv_ws"]
    assert service.discarded_ids == ["conv_ws"]
    assert [payload["event"] for payload in websocket.sent] == ["ready", "final_transcript"]


@pytest.mark.asyncio
async def test_websocket_discards_session_after_disconnect():
    websocket, service = build_websocket([WebSocketDisconnect(code=1000)])

    await transcribe_stream(websocket)

    assert service.discarded_ids == ["conv_ws"]


@pytest.mark.asyncio
async def test_websocket_discards_session_when_message_handling_raises():
    websocket, service = build_websocket([{"text": "{"}])

    with pytest.raises(json.JSONDecodeError):
        await transcribe_stream(websocket)

    assert service.discarded_ids == ["conv_ws"]
