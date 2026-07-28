"""Run a dependency-light product-loop simulation against the local engine."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from collective_mindgraph.engine.main import create_app
from collective_mindgraph.engine.settings import EngineSettings


def run_simulation() -> dict[str, object]:
    with TemporaryDirectory(prefix="mindgraph-validation-") as directory:
        root = Path(directory)
        settings = EngineSettings(
            data_dir=root / "data",
            temp_dir=root / "temp",
            database_path=root / "collective_mindgraph.sqlite3",
            asr_provider="mock",
            vad_provider="energy",
            diarizer_provider="fallback",
            llm_provider="disabled",
            embedding_provider="mock",
        )
        with TestClient(create_app(settings)) as client:
            meeting = client.post(
                "/api/v1/meetings",
                json={"title": "Architecture validation"},
            )
            meeting.raise_for_status()
            dashboard = client.get("/api/v1/dashboard")
            dashboard.raise_for_status()
            export = client.get("/api/v1/export")
            export.raise_for_status()
            return {
                "meeting_id": meeting.json()["id"],
                "dashboard": dashboard.json(),
                "format_version": export.json()["format_version"],
            }


def main() -> int:
    result = run_simulation()
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
