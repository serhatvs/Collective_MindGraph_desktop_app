# PRODUCT_BASELINE_AUDIT.md

## Collective MindGraph MVP: Transcription-to-Memory Baseline

This document audits the current state of the Collective MindGraph MVP against the "transcription-to-memory" product vision. It distinguishes between core product loop capabilities, technical sub-components, and roadmap items.

### 1. Product Loop Audit

| Capability | Status | Evidence | Missing / TODO |
| :--- | :--- | :--- | :--- |
| **Session Creation** | Implemented | `CollectiveMindGraphService.create_session` | - |
| **Local File/Audio Input** | Partially | `transcribe_file.py` script exists; UI placeholder in `MainWindow` | Integrate manual file upload in desktop UI |
| **Live Voice Ingest** | Implemented | `VoiceCommandPanel` with Faster-Whisper | - |
| **Transcript Creation** | Implemented | `RealtimeBackendTranscriptionService` | - |
| **Raw/Clean Separation** | Implemented | `TranscriptSegment` (raw_text vs corrected_text) | - |
| **Transcript Review UI** | Implemented | `TranscriptPage` with side-by-side view | - |
| **Task Extraction** | Implemented | `summary.py` (heuristic patterns) | LLM-based verification (Roadmap) |
| **Decision Extraction** | Implemented | `summary.py` (heuristic patterns) | LLM-based verification (Roadmap) |
| **Topic Extraction** | Implemented | `summary.py` (heuristic patterns) | - |
| **Source Traceability** | Implemented | `source_segment_id` in extraction items | - |
| **Memory Storage** | Implemented | `GraphNodeRepository` (SQLite) | Arbitrary graph edges (Roadmap) |
| **Global Memory Search** | Implemented | `MemorySearchPage` (Keyword-based) | Semantic search (Roadmap) |
| **Source Navigation** | Implemented | Double-click result -> navigate to segment | - |
| **Demo Seed Data** | Implemented | `seed_demo_session.py` and `services.seed_demo_data` | - |
| **Diagnostics / Offline Status** | Implemented | `DiagnosticsPage` with safety guards | - |
| **Local File/Audio Input** | Implemented | `MainWindow._handle_manual_file_ingest` with background worker | - |
| **Export Session** | Implemented | `MainWindow._export_session` saves to JSON | - |
| **Diarization** | Roadmap | Disabled by default; `UNRESOLVED_` labels used | Production validation pending |
| **Semantic Search** | Roadmap | Placeholder `SemanticQueryService` interface | Vector store implementation |
| **Graph Reasoning** | Roadmap | - | Multi-hop relationship logic |

### 2. Product Loop Strength Assessment

| Strength | Implementation Status |
| :--- | :--- |
| **More than STT** | **High**: The system extracts tasks, decisions, and topics automatically. |
| **Structured Memory** | **Medium**: Data is stored as hiyerarşik graph nodes, but visualization is still list-based. |
| **Traceability** | **High**: Every extracted insight is linked back to a specific transcript segment. |
| **Offline Privacy** | **Maximum**: All processing is strictly local; cloud logic removed. |

### 3. Immediate Improvements Needed (Completed)

1. **UI Wording**: Move away from "Transcription" terminology toward "Memory" and "Knowledge" (DONE).
2. **Manual File Ingest**: Complete the UI-to-backend wiring for transcribing local WAV files (DONE).
3. **Insights Visibility**: Ensure the "Insights" and "Overview" pages feel like the primary value (DONE).
4. **Export Logic**: Wire the export button to allow users to take their "Knowledge" out of the app (DONE).

