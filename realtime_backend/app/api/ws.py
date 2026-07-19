"""WebSocket endpoint for incremental PCM audio transcription."""

from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..pipeline.transcript_formatter import build_streaming_transcript_event
from ..pipeline.transcription_glossary import parse_term_input

router = APIRouter()


@router.websocket("/transcribe/stream")
async def transcribe_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    service = websocket.app.state.streaming_service
    language = websocket.query_params.get("language")
    quality_mode = websocket.query_params.get("quality_mode")
    session_kwargs = {"language": language, "quality_mode": quality_mode}
    parsed_session_glossary = parse_term_input(websocket.query_params.get("session_glossary"))
    parsed_hotwords = parse_term_input(websocket.query_params.get("hotwords"))
    if parsed_session_glossary:
        session_kwargs["session_glossary_terms"] = parsed_session_glossary
    if parsed_hotwords:
        session_kwargs["user_hotwords"] = parsed_hotwords
    session = service.create_session(**session_kwargs)
    try:
        await websocket.send_json(
            {
                "event": "ready",
                "conversation_id": session.conversation_id,
                "audio_format": {
                    "encoding": "pcm_s16le",
                    "sample_rate": websocket.app.state.settings.sample_rate,
                    "channels": websocket.app.state.settings.channels,
                },
                "streaming": {
                    "partial_window_seconds": websocket.app.state.settings.stream_partial_window_seconds,
                    "overlap_seconds": websocket.app.state.settings.stream_overlap_seconds,
                },
            }
        )
        while True:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"] is not None:
                partial = await service.append_audio(session.conversation_id, message["bytes"])
                if partial is not None:
                    await websocket.send_json(build_streaming_transcript_event(partial, is_final=False))
                continue

            if "text" not in message or message["text"] is None:
                continue

            payload = json.loads(message["text"])
            event = payload.get("event")
            if event == "flush":
                partial = await service.flush_partial(session.conversation_id)
                await websocket.send_json(build_streaming_transcript_event(partial, is_final=False))
                continue
            if event == "finalize":
                partial = await service.finalize(session.conversation_id)
                await websocket.send_json(build_streaming_transcript_event(partial, is_final=True))
                return
            if event == "close":
                await websocket.close()
                return
    except WebSocketDisconnect:
        return
    finally:
        service.discard_session(session.conversation_id)
