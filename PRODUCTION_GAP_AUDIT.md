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
    *   `src/collective_mindgraph/pipeline/ai_extraction_service.py`
    *   `src/collective_mindgraph/infrastructure/database/graph_repository.py`
*   **Database Changes**:
    *   Migrated `graph_nodes` to support arbitrary directed graphs (`v2_graph_nodes`, `v2_graph_edges`).
*   **Risks**: Deduplicating entities extracted across different chunks.

### Phase 4: Hybrid Query & Reasoning (Completed)
Combine Keyword, Vector, and Graph data to answer user queries.
*   **Modules Built**:
    *   `src/collective_mindgraph/reasoning/hybrid_memory_query_service.py`
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
*   **Memory Graph**: ACTIVE. V2 graph node/edge persistence is fully active.
*   **Hybrid Query**: ACTIVE. Multi-modal query engine is serving Keyword and Graph results.

## Required Tests
To ensure production readiness, the following test categories will be built:
1.  **Pipeline E2E Test**: `test_transcript_to_memory_graph_pipeline.py`
2.  **AI Abstraction Test**: `test_local_llm_json_extraction.py` (using mock provider)
3.  **Semantic Test**: `test_embedding_vector_retrieval.py`
4.  **Graph Test**: `test_graph_edge_creation_and_traversal.py`
5.  **Reasoning Test**: `test_hybrid_retrieval_and_citation.py`
6.  **Security Test**: `test_no_cloud_network_safety.py`
