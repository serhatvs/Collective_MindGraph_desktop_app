"""Versioned live-capture WebSocket."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket

from collective_mindgraph.domain import MeetingId

from ..ws import transcribe_stream

router = APIRouter()


@router.websocket("/api/v1/meetings/{meeting_id}/recordings/live")
async def live_recording(websocket: WebSocket, meeting_id: int) -> None:
    context = websocket.app.state.engine_context
    selected_meeting = MeetingId(meeting_id)
    async with context.recording_jobs.meeting_lock(selected_meeting):
        if context.get_meeting(selected_meeting) is None:
            await websocket.close(code=4404, reason="Meeting not found.")
            return
        context.recording_jobs.begin_live_capture(selected_meeting)
    try:
        await transcribe_stream(websocket, meeting_id=selected_meeting)
    finally:
        context.recording_jobs.end_live_capture(selected_meeting)
