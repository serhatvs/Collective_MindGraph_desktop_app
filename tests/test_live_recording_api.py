from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from collective_mindgraph.engine.main import create_app
from test_engine_v1_api import _settings


def test_meeting_live_websocket_emits_progress_and_persists_final_transcript(
    tmp_path,
):
    with TestClient(create_app(_settings(tmp_path))) as client:
        meeting_id = client.post(
            "/api/v1/meetings",
            json={"title": "Live meeting"},
        ).json()["id"]
        events: list[dict[str, object]] = []
        with client.websocket_connect(f"/api/v1/meetings/{meeting_id}/recordings/live") as socket:
            events.append(socket.receive_json())
            events.append(socket.receive_json())
            socket.send_bytes(b"\x10\x00" * 4_800)
            socket.send_json({"event": "finalize"})
            while True:
                event = socket.receive_json()
                events.append(event)
                if event.get("event") == "final_transcript":
                    break

        assert events[0]["event"] == "ready"
        assert any(event.get("event") == "progress" for event in events)
        final = events[-1]
        assert final["is_final"] is True
        transcript = client.get(f"/api/v1/meetings/{meeting_id}/transcript")
        assert transcript.status_code == 200
        assert transcript.json()["meeting_id"] == meeting_id


def test_live_websocket_rejects_unknown_meeting(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect("/api/v1/meetings/999/recordings/live"):
                pass
        assert error.value.code == 4404
