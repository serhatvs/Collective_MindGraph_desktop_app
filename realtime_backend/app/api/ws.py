"""WebSocket endpoint for incremental PCM audio transcription."""

from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..pipeline.transcript_formatter import format_transcript

router = APIRouter()


@router.websocket("/transcribe/stream")
async def transcribe_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    service = websocket.app.state.streaming_service
    language = websocket.query_params.get("language")
    session = service.create_session(language=language)
    await websocket.send_json(
        {
            "event": "ready",
            "conversation_id": session.conversation_id,
            "audio_format": {
                "encoding": "pcm_s16le",
                "sample_rate": websocket.app.state.settings.sample_rate,
                "channels": websocket.app.state.settings.channels,
            },
        }
    )

    try:
        while True:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"] is not None:
                partial = await service.append_audio(session.conversation_id, message["bytes"])
                if partial is not None:
                    await websocket.send_json(
                        {
                            "event": "partial_transcript",
                            "conversation_id": partial.conversation_id,
                            "segments": [segment.model_dump() for segment in partial.segments],
                            "text_output": format_transcript(partial),
                        }
                    )
                continue

            if "text" not in message or message["text"] is None:
                continue

            payload = json.loads(message["text"])
            event = payload.get("event")
            if event == "flush":
                partial = await service.flush_partial(session.conversation_id)
                await websocket.send_json(
                    {
                        "event": "partial_transcript",
                        "conversation_id": partial.conversation_id,
                        "segments": [segment.model_dump() for segment in partial.segments],
                        "text_output": format_transcript(partial),
                    }
                )
                continue
            if event == "finalize":
                partial = await service.finalize(session.conversation_id)
                await websocket.send_json(
                    {
                        "event": "final_transcript",
                        "conversation_id": partial.conversation_id,
                        "segments": [segment.model_dump() for segment in partial.segments],
                        "summary": partial.summary,
                        "topics": [topic.model_dump() for topic in partial.topics],
                        "action_items": partial.action_items,
                        "text_output": format_transcript(partial),
                    }
                )
                continue
            if event == "close":
                await websocket.close()
                return
    except WebSocketDisconnect:
        return
