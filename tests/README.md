# Collective MindGraph

Docker-first monorepo for a distributed multi-agent reasoning demo built around MQTT events, Postgres state, and isolated Python agent containers.

## Current App Form

- The current user-facing application is a local web dashboard served by FastAPI.
- The canonical operator experience is: start the Docker stack, then open `http://localhost:8000` in a browser.
- This repository does not ship a packaged native desktop executable such as a Windows `.exe`.

## Stack

- Mosquitto for the event bus
- Postgres for sessions, transcripts, graph nodes, and snapshots
- Python 3.11 agents and mocks
- FastAPI dashboard with Jinja templates

## Services

- `session-controller-agent`
- `frame-aggregator-agent`
- `stt-agent`
- `llm-tree-orchestrator-agent`
- `consistency-agent`
- `graph-writer-agent`
- `snapshot-agent`
- `dashboard`
- `mock-llm`
- `mock-stt`

## Quick Start

1. Copy `.env.example` to `.env` if you want to override defaults.
2. Start Docker Desktop or another Docker daemon.
3. Run the canonical local demo flow:

```powershell
.\scripts\run_demo.ps1
```

This command resets demo state, starts the stack, runs the transcript, segment, and frame simulators, verifies the expected sessions, and leaves the stack running for inspection.

4. Open the dashboard:

`http://localhost:8000`

Important:

- This opens a browser-based local dashboard.

To stop and clear local demo state:

```powershell
.\scripts\reset_demo.ps1
```

## Manual Startup

If you need manual control instead of the canonical demo runner:

```powershell
docker compose up --build
```

## Simulator Flows

Run each simulator as a one-shot container:

```powershell
docker compose --profile sim run --rm transcript-fixture-publisher
docker compose --profile sim run --rm segment-fixture-publisher
docker compose --profile sim run --rm edge-frame-sim
```

Ana server ile ESP arasindaki baglantiyi birlikte simule etmek icin:

```powershell
.\scripts\run_jarvis_sim.ps1
```

Bu komut Docker stack'ini Jarvis ana server olarak kaldirir ve `edge-frame-sim` ile ESP -> MQTT -> STT zincirini tetikler.

## ESP-S3 STT Path

For real ESP-S3 audio instead of the deterministic mock STT, set `STT_BACKEND=openai_audio_transcriptions` and provide `OPENAI_API_KEY`.
The `stt-agent` now accepts raw mono PCM16 frames and segments when the edge device publishes `encoding=pcm_s16le_16khz_mono`, `sample_rate_hz=16000`, `channels=1`, and `sample_width_bytes=2`.
Those fields are preserved through `audio/frame -> audio.segment.created` and converted to WAV before transcription.

Firmware entrypoint for the edge publisher lives in `firmware/esp_s3_audio_frame_publisher`.

## Tests

Contract tests:

```powershell
python -m pytest tests/contract agents/session_controller/tests dashboard/tests -q
```

Docker-backed integration tests:

```powershell
$env:RUN_DOCKER_TESTS="1"
python -m pytest tests/integration -q
```

## Docs

- `docs/architecture.md`
- `docs/event-contracts.md`
- `docs/graph-rules.md`
- `docs/demo-runbook.md`
- `docs/troubleshooting.md`
- `docs/milestones.md`
- `firmware/esp_s3_audio_frame_publisher/README.md`
