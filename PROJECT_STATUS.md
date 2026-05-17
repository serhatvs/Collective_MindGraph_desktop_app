# Project Status: Collective MindGraph MVP

## Current MVP Summary
Collective MindGraph is a local-first, privacy-focused system for capturing, transcribing, and extracting structured knowledge from technical Turkish conversations. The current MVP implementation provides a complete data loop from audio ingestion to traceable keyword-based memory exploration.

**Key Components:**
- **Local Transcription Pipeline**: Strictly offline processing via Faster-Whisper.
- **Dual-Transcript Model**: Simultaneous preservation of Raw ASR output and Cleaned (post-processed) text.
- **Turkish-Safe Extraction**: Heuristic extraction of tasks, decisions, and topics optimized for Turkish technical context.
- **Traceable Memory**: Hierarchical SQLite storage (graph-node persistence) with results linked to source sessions and segments.
- **Integrated Global Search**: A desktop interface for cross-session knowledge retrieval.

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
| **Global Search UI** | Implemented | Desktop search panel with source linking. |
| **Demo Automation** | Implemented | Readiness check and text-only seed scripts. |
| **Meeting Validation** | Pending | Infrastructure ready; pending manual recording. |
| **Semantic Retrieval** | Future TODO | Interface placeholders added (VectorStore). |
| **Full Graph Edge Reasoning** | Future TODO | Hierarchical tree only for now. |
| **Multi-hop Reasoning** | Future TODO | Not yet implemented. |

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
The project is local MVP demo ready and product-integration ready for local-first Turkish transcription and keyword-based memory exploration. It is not yet a production-validated meeting intelligence platform.
