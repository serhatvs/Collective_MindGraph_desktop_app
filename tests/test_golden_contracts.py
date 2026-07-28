from __future__ import annotations

import json
import wave
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from collective_mindgraph.engine.main import create_app
from collective_mindgraph.engine.settings import EngineSettings

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "fixtures" / "golden"


def _settings(tmp_path: Path) -> EngineSettings:
    return EngineSettings(
        data_dir=tmp_path / "data",
        temp_dir=tmp_path / "temp",
        database_path=tmp_path / "collective_mindgraph.sqlite3",
        asr_provider="mock",
        vad_provider="energy",
        diarizer_provider="fallback",
        embedding_provider="disabled",
        llm_provider="disabled",
    )


def _wav_bytes() -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16_000)
        recording.writeframes(b"\x00\x00" * 1_600)
    return output.getvalue()


def _fixture(name: str):
    return json.loads((GOLDEN / name).read_text(encoding="utf-8"))


def test_openapi_surface_matches_golden_fixture(tmp_path: Path):
    schema = create_app(_settings(tmp_path)).openapi()
    actual = {
        path: sorted(
            method for method in item if method in {"get", "post", "put", "patch", "delete"}
        )
        for path, item in sorted(schema["paths"].items())
    }
    assert actual == _fixture("openapi_surface.json")


def test_legacy_http_payload_shapes_match_golden_fixture(tmp_path: Path):
    golden = _fixture("legacy_transport_contracts.json")
    with TestClient(create_app(_settings(tmp_path))) as client:
        health = client.get("/health")
        transcript = client.post(
            "/transcribe/file",
            files={"upload": ("sample.wav", _wav_bytes(), "audio/wav")},
        )
    assert health.status_code == 200
    assert transcript.status_code == 200
    payload = transcript.json()
    assert sorted(health.json()) == golden["health_keys"]
    assert sorted(payload) == golden["transcribe_file_keys"]
    assert sorted(payload["transcript"]) == golden["transcript_keys"]
    assert sorted(payload["transcript"]["segments"][0]) == golden["segment_keys"]


def test_canonical_export_shape_matches_golden_fixture(tmp_path: Path):
    golden = _fixture("canonical_export_contract.json")
    with TestClient(create_app(_settings(tmp_path))) as client:
        response = client.get("/api/v1/export")
    assert response.status_code == 200
    payload = response.json()
    assert payload["format"] == golden["format"]
    assert payload["format_version"] == golden["format_version"]
    assert sorted(payload) == golden["top_level_keys"]
    assert sorted(payload["tables"]) == golden["table_keys"]
