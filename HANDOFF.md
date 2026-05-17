# Project Handoff: Collective MindGraph

## Overview
Collective MindGraph is a local-first, privacy-focused desktop application for capturing, transcribing, and extracting knowledge from technical Turkish meetings. It has transitioned from a cloud-dependent architecture to a strictly offline-capable system.

## Current Implementation Status

| Feature | Status | Notes |
| :--- | :--- | :--- |
| **Local Transcription Pipeline** | Implemented | Uses `faster-whisper` and `silero-vad`. |
| **Raw/Clean Transcript Separation** | Implemented | Preserves original ASR and cleaned text. |
| **Turkish ASR Regression Benchmark** | Implemented | 91% keyword overlap on Common Voice. |
| **Heuristic Structured Extraction** | Implemented | Extracts tasks, decisions, and topics. |
| **Keyword Memory Query** | Implemented | Local cross-session search with source linking. |
| **Desktop Global Search UI** | Implemented | Integrated search with source navigation. |
| **Offline Safety Guards** | Implemented | Prevents silent internet access. |
| **Basic Graph Persistence** | Implemented | Hierarchical SQLite-based storage. |
| **Project Meeting Validation** | Pending | Infrastructure ready; pending manual audio. |
| **Semantic/Vector Search** | Future TODO | Interface placeholders added. |
| **Full Graph Edge Reasoning** | Future TODO | Hierarchical tree only for now. |

## How to Run the Local Demo
Follow the steps in [DEMO_FLOW.md](DEMO_FLOW.md) for a guided walkthrough.

## Architecture
- **Desktop UI**: PySide6 application in `src/collective_mindgraph_desktop`.
- **Backend Service**: FastAPI service in `realtime_backend` for audio processing and analysis.
- **Persistence**: SQLite (Desktop) and File-based (Backend).
- **Core Pipeline**:
  1. `audio_process.py`: FFmpeg normalization.
  2. `vad.py`: Voice Activity Detection.
  3. `asr.py`: Speech-to-Text via Faster-Whisper.
  4. `diarization.py`: Speaker identification.
  5. `llm_postprocess.py`: Cleanup and structured extraction.

## Important Scripts
- `scripts/dev_backend.sh`: Start the backend.
- `scripts/dev_desktop.sh`: Start the desktop app.
- `scripts/check_demo_readiness.sh`: Verify environment.
- `realtime_backend/scripts/seed_demo_session.py`: Seed data without audio.
- `realtime_backend/scripts/benchmark_common_voice_tr.py`: Run ASR benchmark.

## Known Limitations
- **Meeting-room accuracy**: Production-level accuracy is not claimed yet; pending project-specific validation.
- **Graph Complexity**: Currently supports hierarchical (tree) relationships, not arbitrary edges.
- **Search**: Strictly keyword-based; no semantic similarity yet.

## Pending TODOs
- [ ] Record project-specific Turkish meeting WAV and run `test_project_turkish_meeting_asr_quality.py`.
- [ ] Implement `SemanticQueryService` using vector embeddings.
- [ ] Stabilize diarization for sessions with 3+ overlapping speakers.
