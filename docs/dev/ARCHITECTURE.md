# Collective MindGraph Architecture

Collective MindGraph is a local-first, privacy-focused organizational memory system. This document outlines the stable production architecture and the core domain structure.

## 1. Core Philosophy

- **Local-First**: All audio processing, transcription, and intelligence extraction happen on the user's hardware.
- **Privacy-Safe**: No cloud dependencies. Mandatory URL validation guards prevent data egress.
- **Fallback-First**: Core features (Graph, Search, Reasoning) work with deterministic heuristics and graph traversal, with optional LLM enrichment.

## 2. Stable Production Structure

The production codebase is organized into a clean domain structure focused on the stable product loop.

```text
src/collective_mindgraph/
  core/                  # Domain entities and logic
    memory_graph.py      # Knowledge graph node/edge definitions
    graph_reasoning.py   # Multi-hop evidence traversal
    hybrid_query.py      # Combined keyword/graph search interface
    ai_provider.py       # Local LLM/Embedding protocols
    source_reference.py  # Temporal traceability
    shared/              # Shared typed identifiers and events
  infrastructure/        # Concrete technical implementations
    ai/                  # Local model providers (Faster-Whisper, Llama 3.1)
    database/            # Persistence (SQLite, Vector Store)
  services/              # Application services and use cases
    ai_extraction_service.py      # Pipeline for summary/task/decision extraction
    hybrid_memory_query_service.py # Orchestrator for complex search/QA
```

## 3. Product Workflows

### 3.1 Transcription & Extraction
1.  **Audio Ingest**: Handled by `realtime_backend` via Faster-Whisper.
2.  **TranscriptionResult**: Maps raw ASR segments to cleaned technical text.
3.  **Extraction**: `AIExtractionService` uses local LLMs (or heuristic fallbacks) to identify Tasks, Decisions, and Topics.
4.  **Persistence**: `ProductionGraphRepository` stores the results in a hierarchical SQLite structure.

### 3.2 Memory Retrieval (Hybrid Query)
- **Keyword Search**: Standard SQL FTS5 over transcripts and insights.
- **Vector Search**: Semantic similarity using local `sentence-transformers`.
- **Graph Reasoning**: `GraphReasoningService` follows edges (Session -> Segment -> Insight) to provide auditable evidence chains.

### 3.3 Ask Memory
- **Evidence-Only**: Directly retrieves graph nodes and formats them using templates.
- **LLM-Assisted**: Uses retrieved graph context to synthesize a natural language answer with hallucination guards.

## 4. Archive (Concept Modules)

The historical "V2 Architecture" scaffold (based on the initial patent/concept spreadsheet) has been moved to `docs/archive/concept_modules/`. This includes conceptual placeholders for:
- Collaboration Tool
- Enterprise Software
- Knowledge Management Tool
- Meeting Assistant (Conceptual)
- Productivity Tool
- Smart Assistant (Conceptual)

These modules represent the long-term vision but are not currently part of the active, validated production runtime.

