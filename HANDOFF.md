# Project Handoff: Collective MindGraph

## Status and Claim Boundary
**The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It does not currently include validated diarization or production meeting-room speaker separation.**

## Overview
Collective MindGraph is a local-first, privacy-focused desktop application for capturing, transcribing, and extracting knowledge from technical Turkish meetings. It has transitioned from a cloud-dependent architecture to a strictly offline-capable system.

## Current Implementation Status

| Feature | Status | Notes |
| :--- | :--- | :--- |
| **Local Transcription Pipeline** | Implemented | Uses `faster-whisper` and `silero-vad`. |
| **Raw/Clean Transcript Separation** | Implemented | Preserves original ASR and cleaned text. |
| **Turkish ASR Regression Benchmark** | Implemented | 91% keyword overlap on Common Voice. |
| **Heuristic Structured Extraction** | Implemented | Extracts tasks, decisions, and topics. |
| **Local LLM Extraction** | **ACTIVE** | Structured JSON extraction via LM Studio (meta-llama-3.1). |
| **Hybrid Memory Query** | Implemented | Combined Keyword, Vector, and Graph search active. |
| **Ask Memory** | **ACTIVE** | Auditable layers with hallucination rejection and coverage scoring. |
| **Graph Edge Reasoning** | Implemented | Multi-hop structural reasoning (neighbors, paths) active. |
| **Desktop Global Search UI** | Implemented | Integrated search and "Ask Your Memory" panel. |

## How to Run the Local Demo
Follow the steps in [DEMO_FLOW.md](DEMO_FLOW.md) for a guided walkthrough.

## Interface Definitions
- **User-facing Frontend**: Rebuilt Native PySide6 Desktop Application in `src/collective_mindgraph_desktop/`.
  - **Structure**: Uses a modular `ui/pages/` and `ui/components/` architecture.
- **Backend API**: Local FastAPI service at `http://127.0.0.1:8081`.
- **Optional Developer Docs**: API documentation at `http://127.0.0.1:8081/docs` (Use for debugging only).

## Architecture
- **Desktop UI**: PySide6 application. Features a 3-area layout (Sidebar, Tabbed Content, Header Controls).
- **Backend Service**: FastAPI service. This is a background processing service.
- **Persistence**: SQLite (Desktop) and File-based (Backend).
- **Core Pipeline**:
  1. `audio_process.py`: FFmpeg normalization.
  2. `vad.py`: Voice Activity Detection.
  3. `asr.py`: Speech-to-Text via Faster-Whisper.
  4. `diarization.py`: (Roadmap) Speaker identification.
  5. `llm_postprocess.py`: Cleanup and structured extraction.

## Important Scripts
- `scripts/dev_backend.sh`: Start the backend.
- `scripts/dev_desktop.sh`: Start the desktop app.
- `scripts/check_demo_readiness.sh`: Verify environment.
- `realtime_backend/scripts/seed_demo_session.py`: Seed data without audio.
- `realtime_backend/scripts/benchmark_common_voice_tr.py`: Run ASR benchmark.

## Known Limitations
- **Meeting-room accuracy**: Production-level accuracy is not claimed yet; pending project-specific validation.
- **Search**: Hybrid query active; semantic retrieval requires real local model configuration (currently using infrastructure placeholders).

## Pending TODOs
- [ ] Record project-specific Turkish meeting WAV and run `test_project_turkish_meeting_asr_quality.py`.
- [ ] Finalize local embedding model validation for production semantic retrieval.
- [ ] Implement and validate Diarization / automatic speaker separation.
