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

# PRODUCTION_GAP_AUDIT.md

## Collective MindGraph: Production Architecture Gap Analysis

This document outlines the architectural gap between the current MVP (a local transcription tool with basic hierarchical extraction) and the target production system (a fully-fledged, local-first AI memory graph).

### 1. Current Implemented Systems
- **Native PySide6 Desktop UI**: Operational with tabbed navigation and basic local file ingest.
- **Local Transcription (STT)**: 100% offline Faster-Whisper integration.
- **Raw/Clean Transcript Separation**: Implemented at the database and UI levels.
- **Heuristic Extraction**: Regex/pattern-based extraction for Tasks, Decisions, and Topics (specifically for Turkish technical meetings).
- **Keyword Search**: Basic SQL text matching across extracted text.
- **Export**: JSON export of basic session context.
- **Local Backend**: FastAPI server handling STT and serving as the foundational API boundary.

### 2. Missing & Partial Systems (The Gap)
- **Local AI Layer**: **Partial**. We have basic HTTP wrappers for LLMs, but lack rigorous local endpoints, strict validation, structured JSON parsing, and programmatic fallback chains.
- **Semantic Memory Layer**: **Missing**. No local embedding models, vector store, or semantic retrieval implemented.
- **Real Memory Graph**: **Partial/Missing**. The current `GraphNode` table is purely hierarchical (parent/child). We lack true graph nodes (Entities, People, Documents) and relationship edges (e.g., `SEGMENT_CREATES_TASK`, `DECISION_RELATED_TO_TOPIC`).
- **AI Extraction Pipeline**: **Partial**. Currently relying entirely on heuristics. Missing the LLM-driven structured extraction loop with confidence scoring, deduplication, and heuristic fallback.
- **Query/Reasoning Layer**: **Partial**. Currently only keyword search. Missing vector search, graph traversal, hybrid ranking, and source-cited LLM answer generation.
- **Diarization**: **Missing**. Not implemented. Must investigate offline Pyannote model limits.
- **Data Architecture**: **Partial**. SQLite exists but needs massive schema migrations for vectors and graph edges.
- **Production Reliability**: **Missing**. No job queues (RQ/Celery/Asyncio tasks), limited retry logic, and basic logging.
- **Evaluation**: **Partial**. STT benchmarks exist, but lacking extraction, graph edge, and hybrid retrieval tests.

---

## Production Target Architecture & Implementation Plan

### Phase 1: Foundational Interfaces & Schema Planning (Current)
Establish the abstractions required to support the target architecture without coupling to specific cloud tools.
*   **Modules Added**: `src/collective_mindgraph/core/` (`ai_provider.py`, `memory_graph.py`, `source_reference.py`, `hybrid_query.py`).
*   **Actions**:
    *   Define `LocalLLMProvider` and `LocalEmbeddingProvider`.
    *   Define `GraphNode`, `GraphEdge`, `NodeType`, and `EdgeType`.
    *   Define `SourceReference` for strict traceability.
    *   Update Diagnostics UI to reflect real production status.

### Phase 2: Local AI & Semantic Storage (Completed)
Implement the engines that process text into meaning.
*   **Modules Built**:
    *   `src/collective_mindgraph/infrastructure/ai/local_llm_provider.py`
    *   `src/collective_mindgraph/infrastructure/database/vector_repository.py`
*   **Database Changes**:
    *   Added `v2_embeddings` table.
*   **Risks**: VRAM limits for running STT, LLM, and Embeddings concurrently on consumer hardware.

### Phase 3: Graph Construction & AI Extraction (Completed)
Replace the heuristic parser with the multi-stage AI pipeline.
*   **Modules Built**:
    *   `src/collective_mindgraph/services/ai_extraction_service.py`
    *   `src/collective_mindgraph/infrastructure/database/graph_repository.py`
*   **Database Changes**:
    *   Migrated `graph_nodes` to support arbitrary directed graphs (`v2_graph_nodes`, `v2_graph_edges`).
*   **Risks**: Deduplicating entities extracted across different chunks.

### Phase 4: Hybrid Query & Reasoning (Completed)
Combine Keyword, Vector, and Graph data to answer user queries.
*   **Modules Built**:
    *   `src/collective_mindgraph/services/hybrid_memory_query_service.py`
    *   `src/collective_mindgraph_desktop/ui/pages/memory_search_page.py` (Mode Selector)
    *   `realtime_backend/app/api/routes.py` (Upgraded `/query` endpoint)
*   **Actions**:
    *   Implemented Hybrid, Semantic, and Keyword query modes in the backend.
    *   Implemented Graph expansion (SEGMENT <-> TASK/DECISION/TOPIC).
    *   Integrated relevance scoring and match explanation.
*   **Risks**: Balancing query latency with answer quality.

### Phase 5: Production AI Pipeline (Completed)
Build robust processing loop for long-form organizational memory.
*   **Modules Built**:
    *   `realtime_backend/app/pipeline/extraction.py` (`AIExtractionService`)
    *   `realtime_backend/app/pipeline/orchestrator.py` (Integrated loop)
*   **Actions**:
    *   Implemented structured JSON extraction using local LLMs.
    *   Added heuristic fallback for reliability.
    *   Integrated graph node and edge creation during the main transcription flow.

### Phase 6: Graph Usability & Job Management (Completed)
Enhance graph traversal, auditing, and background task tracking.
*   **Modules Built**:
    *   `src/collective_mindgraph/infrastructure/database/graph_repository.py` (Traversal API)
    *   `src/collective_mindgraph_desktop/ui/jobs.py` (Job Registry)
    *   `src/collective_mindgraph_desktop/ui/pages/knowledge_graph_page.py` (Interactive Explorer)
*   **Actions**:
    *   Implemented Node/Edge traversal (neighbors, subgraph).
    *   Added Knowledge Graph tab with filtering and detail views.
    *   Integrated background job tracking for transcription and extraction.
    *   Added Export/Import for full session and graph context.
    *   Supported user review/edit persistence with metadata tracking.

### Phase 7: Graph Reasoning & Evidence (Completed)
Implement multi-hop structural reasoning without LLM dependency.
*   **Modules Built**:
    *   `src/collective_mindgraph/core/graph_reasoning.py` (`GraphReasoningService`)
    *   `realtime_backend/app/api/routes.py` (New `/reason` endpoint)
    *   `src/collective_mindgraph_desktop/ui/pages/reasoning_trace_page.py` (Evidence View)
*   **Actions**:
    *   Implemented multi-hop pathfinding and neighbor explanation.
    *   Added intent-based query parsing (e.g., finding tasks related to a topic).
    *   Exposed explicit evidence chains (Session -> Segment -> Task) in the UI.
    *   Integrated review status into reasoning (pending/rejected filtering).

### Phase 8: Local AI & Real Embeddings (Infrastructure Ready)
Establish real semantic processing.
*   **Modules Built**:
    *   `src/collective_mindgraph/infrastructure/ai/local_embedding_provider.py` (SentenceTransformers support)
*   **Actions**:
    *   Wired `VectorRepository` to automatically embed nodes during session ingest.
    *   Implemented cosine similarity search in SQLite.
*   **Remaining**: Final validation of local embedding model performance on Turkish technical text.

### Phase 9: Production Reliability & Diarization
Stabilize the system for long-term organizational use.
*   **Modules to Build**:
    *   `src/collective_mindgraph/jobs/queue.py`
    *   `src/collective_mindgraph/audio/offline_diarization.py` (if feasible).
*   **Risks**: Pyannote license/offline restrictions and CPU performance for background queues.


## Honest Production Status (Current Deployment)
*   **Local LLM**: ACTIVE. Local LLM provider (LM Studio) is verified and used for extraction and auditable assisted-ask.
*   **Ask Memory**: ACTIVE. Evidence-grounded with automated hallucination rejection and coverage scoring.
*   **Semantic Retrieval**: MOCK_ONLY. Infrastructure exists, but production semantic retrieval requires configuring a real local embedding model.
*   **Memory Graph**: ACTIVE. V2 graph node/edge persistence is fully active. Native schema expansion added for ENTITY, RISK, OPEN_QUESTION, and FOLLOW_UP nodes with corresponding edges.
*   **Hybrid Query**: ACTIVE. Multi-modal query engine is serving Keyword and Graph results.

## Required Tests
To ensure production readiness, the following test categories will be built:
1.  **Pipeline E2E Test**: `test_transcript_to_memory_graph_pipeline.py`
2.  **AI Abstraction Test**: `test_local_llm_json_extraction.py` (using mock provider)
3.  **Semantic Test**: `test_embedding_vector_retrieval.py`
4.  **Graph Test**: `test_graph_edge_creation_and_traversal.py`
5.  **Reasoning Test**: `test_hybrid_retrieval_and_citation.py`
6.  **Security Test**: `test_no_cloud_network_safety.py`
# Project Status: Collective MindGraph MVP

## Current MVP Summary
Collective MindGraph is a local-first, privacy-focused system for capturing, transcribing, and extracting structured knowledge from technical Turkish conversations. The current MVP implementation provides a complete data loop from audio ingestion to traceable keyword-based memory exploration.

**Key Components:**
- **Local Transcription Pipeline**: Strictly offline processing via Faster-Whisper.
- **Dual-Transcript Model**: Simultaneous preservation of Raw ASR output and Cleaned (post-processed) text.
- **Turkish-Safe Extraction**: Heuristic extraction of tasks, decisions, and topics optimized for Turkish technical context.
- **Traceable Memory**: Hierarchical SQLite storage (graph-node persistence) with results linked to source sessions and segments.
- **Integrated Global Search**: A desktop interface for cross-session knowledge retrieval.

## Interface Definitions (Frontend vs. Backend)
- **Primary Frontend**: The native **PySide6 desktop application** (`src/collective_mindgraph_desktop/`). This is the only user-facing interface.
- **Backend Service**: A local FastAPI background service (`realtime_backend/`) running on `127.0.0.1:8081`. It provides processing but is not the UI.
- **Developer Debugging**: The `/docs` endpoint at `127.0.0.1:8081/docs` is for API inspection only and is NOT the project frontend.

## Current Runtime Flow
The system processes information through the following stages:

1. **Input**: Audio capture (microphone/WebSocket) or local file upload.
2. **Preprocessing**: Mandatory FFmpeg normalization (16kHz, mono PCM).
3. **ASR**: Faster-Whisper local inference (configured for Turkish technical glossary).
4. **Raw Output**: Exact ASR transcript is captured and preserved.
5. **Cleanup**: Deterministic Turkish-safe cleanup (filler removal, punctuation, casing).
6. **Extraction**: Heuristic identification of tasks, decisions, and topics from cleaned text.
7. **Persistence**: Structured items and transcripts stored in hierarchical SQLite nodes.
8. **Query**: Keyword-based lookup via `KeywordMemoryQueryService`.
9. **UI**: Display in Global Search with double-click navigation to source segments.

## Implementation Matrix

| Feature | Status | Notes |
| :--- | :--- | :--- |
| **Local ASR Pipeline** | Implemented | 100% offline; Faster-Whisper based. |
| **Offline Safety Guards** | Implemented | Prevents silent internet calls; URL validation. |
| **Raw/Clean Separation** | Implemented | Distinct storage and UI columns. |
| **Turkish Benchmark** | Implemented | Regression suite using Common Voice data. |
| **Heuristic Extraction** | Implemented | Technical Turkish task/decision patterns. |
| **Keyword Query Service** | Implemented | Cross-session traceable lookup with scoring. |
| Global Search UI | Implemented | Desktop search panel with source linking. |
| **Local LLM Extraction** | **ACTIVE** | LM Studio integration (meta-llama-3.1-8b-instruct) verified. |
| **Native Schema Expansion** | **Implemented** | Native graph support for ENTITY, RISK, OPEN_QUESTION, FOLLOW_UP. |
| **Demo Automation** | Implemented | Readiness check and text-only seed scripts. |
| **Meeting Validation** | Pending | Infrastructure ready; pending manual recording. |
| **Semantic Retrieval** | Implemented | Local embedding provider with SQLite Vector store active. |
| **Diarization** | **Roadmap** | Automatic speaker separation is NOT implemented or validated. |
| **Knowledge Review/Edit** | **Implemented** | Double-click to edit extracted items with graph persistence. |
| **Export/Import** | **Implemented** | Full V2 Graph context (nodes/edges/refs) roundtrip supported. |
| **Job Management** | **Implemented** | Background task registry with progress tracking in status bar. |
| **Graph Reasoning** | Implemented | Multi-hop structural reasoning (neighbors, paths) without LLM dependency. |
| **Ask Memory** | **ACTIVE** | Auditable layers (Evidence-only/LLM) with coverage scoring and term validation. |
| **Reasoning Trace** | Implemented | UI evidence chains showing Session -> Segment -> Insight paths. |
| **Hallucination Guard** | **ACTIVE** | Automated rejection of unsupported LLM claims with technical term detection. |

## Validation Status
- **Common Voice Turkish**: Active Clean-speech benchmark.
- **Metrics**: Current performance is measured by `keyword_overlap_quality_score` (~91% on clean speech). This is an approximation of accuracy, not a final scientific benchmark.
- **Meeting-room accuracy**: Production-level meeting room accuracy is not claimed yet; pending project-specific manual audio validation.

## Demo Commands
To start the integrated system locally:
```bash
# 1. Verify environment
./scripts/check_demo_readiness.sh

# 2. Seed data (No audio required)
PYTHONPATH=. python realtime_backend/scripts/seed_demo_session.py

# 3. Start Backend
./scripts/dev_backend.sh

# 4. Start Desktop App
./scripts/dev_desktop.sh
```

## Demo Search Queries
Test the memory retrieval with these terms:
- `FastAPI endpoint` (returns Task)
- `raw transcript` (returns Decision)
- `VAD ayarları` (returns Task/Topic)
- `kararlar` (returns Decision)
- `Collective MindGraph` (returns Topic/Session)

## Honest Claim Boundary
The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It does not currently include validated diarization or production meeting-room speaker separation.
