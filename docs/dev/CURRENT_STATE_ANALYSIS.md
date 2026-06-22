# Collective MindGraph Current-State Analysis

Date: 2026-06-22

## 1. Executive Summary

Collective MindGraph is currently a local-first Python desktop application with a local FastAPI transcription backend, SQLite persistence, transcript audit UI, structured extraction, a V2 graph persistence layer, human review screens, search/Ask Memory endpoints, and demo-oriented validation coverage.

It is not yet a fully production-validated organizational memory platform. The codebase contains meaningful implemented pieces, but also parallel implementations, prototype defaults, mock fallbacks, incomplete backend/UI contracts, and roadmap features that must not be claimed as finished.

Current maturity level: advanced MVP / demo-safe candidate with careful setup, not production-ready. The safest current positioning is: "local-first desktop MVP for transcript-to-source-traceable memory graph workflows, with deterministic fallback extraction and optional local AI."

Main technical strengths:

- Native PySide6 desktop shell with session navigation, transcript audit, review, graph tables, search, diagnostics, import/export, and voice/file ingest entry points in `src/collective_mindgraph_desktop/`.
- Local backend centered on FastAPI, Faster-Whisper ASR, Silero VAD, deterministic transcript cleanup, and JSON transcript persistence in `realtime_backend/app/`.
- Clear local-first intent through localhost/private-network URL guards and removal of cloud provider dependencies in active code paths.
- V2 graph schema and repositories for nodes, edges, source references, embeddings, and review metadata.
- Human review lifecycle for graph nodes: pending, approved, rejected/disabled, edited.
- Evidence-only Ask Memory and graph reasoning services exist and are testable with mocked graph evidence.

Main technical gaps:

- Diarization and real speaker separation are not production implemented or validated. Default config disables diarization and uses `UNRESOLVED_0` fallback labels.
- Graph persistence exists, but graph construction is partly desktop-side and partly backend-side. Boundaries are unclear.
- Semantic retrieval is implemented as infrastructure, but defaults to mock embeddings unless local model configuration is provided.
- Ask Memory UI and backend response schemas are mismatched in places.
- Local LLM extraction and LLM-assisted Ask Memory are optional and fragile, not stable baseline features.
- Production packaging, meeting-room validation, advanced graph analytics, and installer-level reliability are not proven from the codebase.

## 2. Implemented Features

| Feature | Classification | Evidence | Notes |
| --- | --- | --- | --- |
| Desktop / PySide6 UI | Implemented | `src/collective_mindgraph_desktop/ui/main_window.py`, `src/collective_mindgraph_desktop/app.py` | Main window has sidebar, voice panel, tabs for session memory, transcript audit, review suggestions, graph, reasoning trace, search, diagnostics. |
| Backend/API | Implemented | `realtime_backend/app/main.py`, `realtime_backend/app/api/routes.py`, `realtime_backend/app/api/ws.py` | FastAPI app exposes `/health`, `/transcribe/file`, `/transcript/{id}`, `/summary/{id}`, `/quality/{id}`, `/query`, `/reason`, `/memory/ask`, `/jobs`, and WebSocket routes. |
| Local STT / transcription flow | Implemented | `realtime_backend/app/pipeline/asr.py`, `realtime_backend/app/pipeline/orchestrator.py`, `realtime_backend/app/services/transcription_service.py` | Faster-Whisper provider exists with mock fallback under `auto`; pipeline normalizes audio, detects VAD regions, transcribes windows, merges segments, cleans text, and saves JSON transcript. |
| VAD | Implemented | `realtime_backend/app/pipeline/vad.py` | Silero VAD and fallback logic are present. |
| Raw vs cleaned transcript handling | Implemented | `realtime_backend/app/models.py`, `realtime_backend/app/pipeline/orchestrator.py`, `src/collective_mindgraph_desktop/ui/pages/transcript_page.py` | `TranscriptSegment.raw_text` and `corrected_text` are stored and displayed side by side. |
| Transcript correction / cleanup | Partially implemented | `realtime_backend/app/pipeline/llm_postprocess.py`, `realtime_backend/app/utils/turkish_cleanup.py` | Deterministic Turkish cleanup is baseline. Local LLM correction is optional and endpoint-dependent. |
| Extraction pipeline | Partially implemented | `realtime_backend/app/services/summary.py`, `realtime_backend/app/pipeline/extraction.py`, `src/collective_mindgraph_desktop/services.py` | Heuristic summary/task/decision/topic extraction is active in the transcription pipeline. `AIExtractionService` exists but is not clearly wired into `TranscriptionPipeline.process_audio_path`. |
| Heuristic fallback extraction | Implemented | `realtime_backend/app/services/summary.py`, `realtime_backend/app/pipeline/extraction.py` | Regex and deterministic fallback extraction populate topics, action items, decisions, and some metadata. |
| Memory graph persistence | Implemented, with boundary risk | `src/collective_mindgraph_desktop/database.py`, `src/collective_mindgraph_desktop/services.py`, `src/collective_mindgraph/infrastructure/database/graph_repository.py` | SQLite V2 tables and repository exist. Desktop ingest creates SESSION, SEGMENT, TASK, DECISION, TOPIC, ENTITY, RISK, OPEN_QUESTION, FOLLOW_UP nodes and edges. Backend also has a parallel repository. |
| Node/edge schema | Implemented | `src/collective_mindgraph/core/memory_graph.py`, `realtime_backend/app/services/memory_graph.py` | Node and edge enums cover session, segment, task, decision, topic, entity, risk, open question, follow-up, and relationship types. |
| Source references / traceability | Implemented, partial UX | `src/collective_mindgraph/core/source_reference.py`, `src/collective_mindgraph_desktop/services.py`, `src/collective_mindgraph_desktop/ui/pages/transcript_page.py` | Nodes can link to session and segment IDs. UI navigation exists, but some graph trace logic is heuristic and does not fully dereference source reference rows. |
| Human review lifecycle | Implemented | `src/collective_mindgraph_desktop/ui/pages/review_queue_page.py`, `src/collective_mindgraph_desktop/ui/pages/insights_page.py`, `src/collective_mindgraph_desktop/services.py` | Pending suggestions can be approved/rejected; nodes can be edited/disabled. Review metadata is persisted in V2 node JSON. |
| Search / hybrid retrieval | Partially implemented | `src/collective_mindgraph/services/hybrid_memory_query_service.py`, `realtime_backend/app/services/hybrid_memory_query_service.py`, `src/collective_mindgraph_desktop/ui/pages/memory_search_page.py` | Keyword and vector search are present. Desktop/core service does 1-hop graph expansion. Backend service contains a no-op graph expansion block. |
| Semantic retrieval / embeddings | Partially implemented | `src/collective_mindgraph/infrastructure/ai/local_embedding_provider.py`, `src/collective_mindgraph/infrastructure/database/vector_repository.py`, `models/embeddings/...` | Local SentenceTransformer provider and naive SQLite vector search exist. Defaults are mock unless configured. Production-scale vector retrieval is not proven. |
| Ask Memory / evidence-only answering | Partially implemented | `realtime_backend/app/services/evidence_answer_service.py`, `realtime_backend/app/api/routes.py`, `src/collective_mindgraph_desktop/ui/components/ask_memory_panel.py` | Evidence-only answering exists, but relies on simple intent parsing and graph reasoning. UI expects fields not defined in desktop `MemoryAskResponse`. |
| LLM-assisted Ask Memory | Stub/partial | `realtime_backend/app/services/llm_assisted_ask_service.py`, `tests/test_ask_memory_evidence_validation.py` | Implemented as optional local endpoint flow with hallucination guards. It is not a stable baseline and falls back to evidence-only when unavailable or invalid. |
| Export/import | Implemented, with reliability risk | `src/collective_mindgraph_desktop/services.py`, `src/collective_mindgraph_desktop/ui/main_window.py` | JSON export/import includes sessions, transcripts, legacy graph nodes, transcript analyses, and V2 graph data. Collision handling and full roundtrip reliability need more validation. |
| Jobs / diagnostics | Partially implemented | `realtime_backend/app/services/job_manager.py`, `src/collective_mindgraph_desktop/ui/jobs.py`, `src/collective_mindgraph_desktop/ui/pages/diagnostics_page.py` | Backend has persistent jobs table and `/jobs`. Desktop has in-memory registry. Diagnostics UI reports status, but some status text is static or inferred. |
| Offline/local-first safeguards | Implemented, with dependency caveats | `realtime_backend/app/utils/offline_safety.py`, `realtime_backend/app/config.py`, `realtime_backend/app/pipeline/local_llm_provider.py` | URL/model path validation blocks public cloud endpoints unless explicitly allowed. Hugging Face/pyannote dependencies still create setup and licensing risks. |
| Production installer/packaging | Partially implemented | `CollectiveMindGraph.spec`, `scripts/build_windows_exe.ps1` | PyInstaller build artifacts exist, but no proof of a production installer or validated packaged runtime is present. |

## 3. Roadmap / Not Implemented

Not implemented or not validated enough to claim:

- Diarization: code exists for optional pyannote integration in `realtime_backend/app/pipeline/diarization.py`, but default `CMG_RT_DIARIZATION_ENABLED=false` returns `SingleSpeakerFallbackDiarizer`. This is not real diarization.
- Real speaker separation: not implemented as a validated production feature. Fallback speaker is `UNRESOLVED_0`.
- Speaker attribution: partial only. Stable mapping exists in `realtime_backend/app/pipeline/speaker_mapper.py`, but real attribution depends on real diarization.
- Full visual graph canvas: not implemented. `KnowledgeGraphPage` is a table/list explorer, not a canvas.
- Production installer/packaging: partially scaffolded, not proven as stable distribution.
- Real meeting-room audio validation: not proven. Tests include clean/fixture paths and optional benchmarks, but no validated real meeting-room result should be claimed.
- Advanced multi-hop graph analytics: partial. `GraphReasoningService.find_paths` and topic-to-item traversal exist, but intent parsing is simple and analytics are not advanced.
- Fully stable Local LLM extraction: not implemented as stable baseline. It is optional endpoint-based behavior with fallback.
- Fully stable LLM-assisted Ask Memory: not implemented as stable baseline. It is guarded and fallback-oriented.
- Multi-user shared workspace / sync: roadmap only.
- Hardware device / microphone array / status display: roadmap or archived concept only.
- Production-grade vector index: not implemented. Current vector repository is naive SQLite JSON vectors.

## 4. Claim Boundary / Overclaim Risk

### Safe Technical Claims

- The project contains a native PySide6 desktop application for local memory sessions.
- The project contains a local FastAPI backend for file and streaming transcription workflows.
- The backend supports local Faster-Whisper ASR and Silero VAD when dependencies and models are available.
- The system preserves raw ASR and corrected transcript text separately.
- The system has deterministic heuristic extraction for tasks, decisions, and topics.
- The desktop ingest path persists V2 graph nodes and edges to SQLite.
- Extracted items can carry source session and segment references.
- The UI has a human review loop for pending graph nodes.
- The system includes keyword, graph, and optional vector retrieval infrastructure.
- Evidence-only Ask Memory exists as a graph-backed, template-style answering service.
- Cloud AI endpoints are not the default active path, and local/private endpoint validation exists.

### Risky Claims

- "Production-ready local-first organizational memory platform." The implementation is still MVP-level with test and runtime gaps.
- "Semantic retrieval is fully operational." Real embeddings require local model config; defaults are mock.
- "Hybrid retrieval includes graph reasoning everywhere." The core desktop service has graph expansion, but backend service has a no-op graph expansion branch.
- "Local LLM extraction is active." It depends on LM Studio/Ollama-compatible endpoint availability and structured JSON reliability.
- "Ask Memory is LLM-powered." LLM mode is optional and may fall back to evidence-only.
- "Export/import is production safe." It exists, but collision, schema migration, and full-fidelity import behavior need broader validation.
- "Offline safe under all configurations." There are safeguards, but `allow_remote_access` and `allow_remote_download` can explicitly weaken the boundary.

### Claims That Must Not Be Made Yet

- Do not claim diarization is implemented as a product feature.
- Do not claim real speaker separation is implemented.
- Do not claim speaker attribution is accurate across real meetings.
- Do not claim production meeting-room audio accuracy.
- Do not claim overlapping-speaker handling is solved.
- Do not claim a full visual graph canvas.
- Do not claim advanced graph analytics beyond the implemented simple path/neighbor/topic traversal.
- Do not claim LLM extraction or LLM-assisted Ask Memory is fully stable.

Explicit boundary: diarization and real speaker separation must not be claimed as implemented unless a future code path proves that real offline diarization is enabled, validated, tested on real multi-speaker audio, and surfaced honestly in diagnostics.

## 5. Architecture Analysis

### Main Modules

- `src/collective_mindgraph_desktop/`: primary user-facing desktop app.
- `realtime_backend/`: local FastAPI backend for transcription, transcript storage, quality, search, reasoning, jobs, and Ask Memory endpoints.
- `src/collective_mindgraph/`: domain-oriented V2 core, infrastructure, and services.
- `docs/archive/`: archived companion and concept modules. These should not be treated as active runtime implementation.
- `models/embeddings/`: local embedding model files for SentenceTransformer-style use.

### Data Flow

Typical file ingest flow:

1. User selects audio in `MainWindow._handle_manual_file_ingest`.
2. `BackendTranscriptionWorker` calls `RealtimeBackendTranscriptionService.transcribe_file`.
3. Backend route `/transcribe/file` writes upload to temp storage.
4. `TranscriptionService.transcribe_file` calls `TranscriptionPipeline.process_audio_path`.
5. Pipeline normalizes audio, runs VAD, runs ASR, runs diarizer/fallback, merges segments, applies LLM/deterministic cleanup, builds summary/extraction via `ConversationSummaryService`.
6. Backend stores transcript JSON through `ConversationStore`.
7. Desktop receives `TranscriptionResult`.
8. `CollectiveMindGraphService.ingest_transcription_result` creates session/transcript rows, transcript analysis rows, legacy graph nodes, V2 graph nodes/edges, and snapshots.
9. UI renders transcript audit, review queue, graph tables, diagnostics, search, and Ask Memory panels.

### Storage Layer

- Desktop SQLite schema is in `src/collective_mindgraph_desktop/database.py`.
- Backend SQLite proxy schema is in `realtime_backend/app/database_proxy.py`.
- Backend transcript JSON store is in `realtime_backend/app/services/conversation_store.py`.
- V2 graph tables:
  - `v2_source_references`
  - `v2_graph_nodes`
  - `v2_graph_edges`
  - `v2_embeddings`
  - `v2_jobs` in backend job manager
- Legacy desktop tables:
  - `sessions`
  - `transcripts`
  - `graph_nodes`
  - `snapshots`
  - `transcript_analyses`

### UI Layer

- `MainWindow` coordinates high-level navigation and workflows.
- `TranscriptPage` shows raw vs corrected transcript.
- `ReviewQueuePage` shows pending extracted graph nodes.
- `InsightsPage` shows approved/edited memory.
- `KnowledgeGraphPage` shows graph nodes/edges as tables and related-node lists.
- `MemorySearchPage` sends query/reasoning requests to backend.
- `AskMemoryPanel` sends evidence-only or LLM-assisted Ask Memory requests.
- `DiagnosticsPage` displays local-first, model, graph, embedding, and Ask Memory status.

### API/Backend Layer

FastAPI routes in `realtime_backend/app/api/routes.py` expose local processing and retrieval endpoints. This backend is a processing/API boundary, not the primary frontend.

Important concern: backend and desktop each have graph/vector/search implementations. For example:

- Desktop/core graph repository: `src/collective_mindgraph/infrastructure/database/graph_repository.py`
- Backend graph repository: `realtime_backend/app/services/graph_repository.py`
- Desktop/core hybrid service: `src/collective_mindgraph/services/hybrid_memory_query_service.py`
- Backend hybrid service: `realtime_backend/app/services/hybrid_memory_query_service.py`

This duplication increases drift risk.

### AI/ML Components

- ASR: `FasterWhisperASR` in `realtime_backend/app/pipeline/asr.py`.
- VAD: Silero and fallback providers in `realtime_backend/app/pipeline/vad.py`.
- Diarization: optional pyannote wrapper plus fallback in `realtime_backend/app/pipeline/diarization.py`.
- LLM cleanup: `realtime_backend/app/pipeline/llm_postprocess.py`.
- LLM extraction: `realtime_backend/app/pipeline/extraction.py`, not clearly wired into the default transcription pipeline.
- Local LLM endpoint provider: `realtime_backend/app/pipeline/local_llm_provider.py` and `src/collective_mindgraph/infrastructure/ai/local_llm_provider.py`.
- Embeddings: `SentenceTransformerEmbeddingProvider` and `MockLocalEmbeddingProvider`.

### Local-First/Privacy Components

- Endpoint validation in `realtime_backend/app/utils/offline_safety.py`.
- Local/private endpoint checks in local LLM provider constructors.
- Default backend settings disable diarization and remote access/downloads.
- Diagnostics page explicitly communicates removed cloud providers and local model verification.

### External Dependency Risks

- `faster-whisper`, `pyannote.audio`, `silero-vad`, `torch`, `sentence-transformers`, and `huggingface-hub` are heavy dependencies with GPU/CPU, license, version, and offline model availability concerns.
- `pyproject.toml` desktop dependencies list `vosk`, while backend requirements list Faster-Whisper, pyannote, Silero, etc. Dependency ownership is split.
- `realtime_backend/.venv/pyvenv.cfg` points to `/usr/bin/python3.14`, which is not directly executable from the current Windows PowerShell environment.

## 6. Product Vision Alignment

Intended vision:

"Collective MindGraph is a local-first organizational memory system that transforms conversations or text into source-traceable graph-based memory, supports human review, hybrid retrieval, graph reasoning, and evidence-based Ask Memory. Local LLM is optional; diarization is roadmap."

### Strong Alignment Areas

- Local-first architecture and active local/private endpoint safeguards.
- Conversation/audio to transcript pipeline.
- Raw and corrected transcript preservation.
- Source-traceable memory graph persistence.
- Human review lifecycle.
- Evidence-only answering design.
- Optional local LLM posture.
- Diarization treated as roadmap in current docs and defaults.

### Partial Alignment Areas

- Hybrid retrieval exists but is uneven across duplicate services.
- Semantic retrieval exists, but default behavior is mock unless configured.
- Graph reasoning exists, but intent parsing and traversal are simple.
- Source traceability is present in data, but UI navigation is not fully robust.
- Export/import exists, but needs more reliability testing.
- Diagnostics are useful, but some status labels are static or inferred.

### Missing Areas

- Production-validated diarization and speaker attribution.
- Full visual graph canvas.
- Production packaging and installer validation.
- Real-world meeting-room audio validation.
- Advanced multi-hop analytics.
- Stable local LLM extraction as a supported baseline.
- Stable LLM-assisted Ask Memory as a supported baseline.

## 7. Technical Debt / Risks

- Code quality risk: duplicate modules exist under `src/collective_mindgraph/` and `realtime_backend/app/services/`, creating drift.
- Boundary risk: backend transcribes and stores JSON, while desktop creates much of the V2 graph. The API/backend layer is not the only source of memory graph truth.
- Dead/legacy risk: `docs/archive/` and `tests/README.md` describe older Docker/MQTT/OpenAI-era architecture. This can confuse claims and onboarding.
- Mock/stub risk: ASR can fall back to mock, embeddings default to mock in several paths, graph expansion is no-op in backend hybrid query, and `_rebuild_snapshots` in `MainWindow` is pass.
- UI/backend mismatch: `AskMemoryPanel._handle_finished` reads fields like `evidence_coverage_score`, `mode_used`, `answer_validation_status`, `rejected_terms`, and `used_sources`, but desktop `MemoryAskResponse` in `src/collective_mindgraph_desktop/transcription.py` does not define them.
- Fragile tests: many tests use mocks or optional skips. Real ASR/embedding/LLM tests depend on environment variables and local models.
- LLM instability: structured JSON extraction depends on endpoint availability and model behavior. Fallback is necessary and should remain.
- Dependency/version risk: pyannote, torch, faster-whisper, CUDA, and sentence-transformers can break across environments. Backend venv is not Windows-native in this checkout.
- Privacy/security gaps: `allow_remote_access` and `allow_remote_download` are escape hatches. Claims should say local-first by default, not impossible to configure remotely.
- Export/import reliability gaps: V2 import reuses node IDs and source reference IDs with new session IDs. Cross-database import works in tests, but same-database collision and migration behavior need more validation.
- Encoding/text quality risk: several strings in docs/tests/UI appear mojibaked, especially Turkish characters and UI symbols. This can affect demos and search.
- Packaging risk: PyInstaller spec exists but packaged backend/model/runtime behavior is not validated in this analysis.

## 8. Test Coverage / Validation

### What Is Tested

- Desktop database and repositories: `tests/test_database.py`, `tests/test_services.py`.
- Desktop product loop with mocked transcription result: `tests/test_collective_mindgraph_product_loop.py`.
- Backend transcription routes and pipeline pieces: `realtime_backend/tests/test_api_routes.py`, `realtime_backend/tests/test_orchestrator.py`, `realtime_backend/tests/test_asr.py`, `realtime_backend/tests/test_vad.py`.
- Turkish cleanup and extraction heuristics: `realtime_backend/tests/test_turkish_support.py`, `realtime_backend/tests/test_structured_extraction.py`, `realtime_backend/tests/test_turkish_structured_extraction_matrix.py`.
- Graph persistence and reasoning: `tests/test_production_graph_persistence.py`, `tests/test_graph_reasoning.py`, `tests/test_memory_reason_endpoint.py`.
- Hybrid/vector retrieval scaffolds: `tests/test_hybrid_memory_query.py`, `tests/test_vector_retrieval.py`, `tests/test_real_local_semantic_retrieval_optional.py`.
- Ask Memory evidence validation: `tests/test_evidence_answer_service.py`, `tests/test_ask_memory_evidence_validation.py`, `tests/test_llm_assisted_ask_memory_optional.py`.
- Offline safety: `realtime_backend/tests/test_offline_safety.py`.
- Diarization utilities, not real diarization: `realtime_backend/tests/test_diarization.py`.
- Export/import and review metadata: `tests/test_knowledge_review_edit.py`, `tests/test_full_scale_simulation_regression.py`.

### What Is Not Adequately Tested

- Real multi-speaker diarization on real meeting audio.
- Speaker attribution accuracy.
- Real meeting-room audio quality.
- Packaged Windows executable runtime with bundled backend and models.
- Full UI/backend Ask Memory contract.
- End-to-end semantic retrieval with a configured local model in ordinary CI.
- End-to-end LLM extraction with a real local model in ordinary CI.
- Same-database import collision behavior.
- Long-session performance and vector search scale.
- Privacy guarantees under all configuration combinations.

### Meaningful Tests

- Product loop tests that create sessions, ingest a `TranscriptionResult`, persist analyses, and verify graph/queryability.
- Graph repository tests for nodes, edges, source references, and deletion.
- Review lifecycle tests for pending/approved/rejected/disabled behavior.
- Offline safety tests for public endpoint rejection.
- Optional real semantic retrieval test when `CMG_EMBEDDING_MODEL_PATH` is configured.

### Smoke/Demo-Only Tests

- Tests using mock ASR/LLM/embedding providers.
- Full-scale simulation tests based on generated demo text and exported JSON.
- UI existence tests that verify tab names and widget wiring but not full user workflows.
- Optional LLM tests that skip or mock model behavior.

### Verification Performed During This Analysis

- `python -m py_compile` succeeded for selected active modules:
  - `realtime_backend/app/services/graph_repository.py`
  - `realtime_backend/app/services/vector_repository.py`
  - `realtime_backend/app/api/routes.py`
  - `src/collective_mindgraph/infrastructure/database/graph_repository.py`
  - `src/collective_mindgraph_desktop/services.py`
- Targeted `pytest` could not be run with the available system Python because `pytest` is not installed.
- The repo-local `.venv` is POSIX-style and points to `/usr/bin/python3.14`, so it could not be executed from the current Windows PowerShell environment.

### Recommended Next Tests

Critical:

- Contract test for `/memory/ask` JSON to desktop `MemoryAskResponse` to catch missing fields.
- End-to-end file ingest test from backend response to desktop graph persistence.
- Diarization-disabled test proving UI/docs do not claim real speaker separation.
- Demo readiness test that fails if diagnostics overclaim mock embeddings or LLM status.

High priority:

- Same-database export/import collision tests.
- Real local embedding test using bundled model path.
- Query tests comparing backend and core hybrid query behavior.
- Review lifecycle test from UI action to search exclusion.
- Long transcript chunking and source-reference integrity tests.

Medium priority:

- Packaging smoke test for PyInstaller output.
- Offline network guard tests for every provider path.
- Turkish encoding regression tests.
- Graph source navigation UI test.

Low priority:

- Advanced analytics benchmark tests after graph traversal behavior is expanded.
- Stress tests for large vector tables.
- Visual graph canvas tests after a canvas exists.

## 9. Recommended Next Steps

### Critical

- Fix Ask Memory desktop response schema mismatch or reduce UI assumptions.
- Make diarization claim boundary explicit in UI, docs, demo script, and pitch materials.
- Decide one source of truth for graph/search services: backend-owned, desktop-owned, or shared core library.
- Add a demo-safe readiness check that reports mock ASR, mock embeddings, disabled LLM, and disabled diarization plainly.
- Keep heuristic fallback extraction as the default safe path.

### High Priority

- Wire or remove `AIExtractionService` ambiguity. If local LLM extraction is product-supported, integrate it explicitly and test fallback behavior.
- Align backend and `src/collective_mindgraph` hybrid query implementations.
- Validate source references from graph node to transcript row in UI navigation.
- Add real local embedding configuration docs and smoke tests against `models/embeddings/...`.
- Strengthen export/import with ID remapping, collision handling, schema versioning, and roundtrip tests.
- Clean or quarantine mojibaked Turkish strings before demos.

### Medium Priority

- Build a real visual graph canvas only after graph semantics are stable.
- Add packaged Windows runtime validation.
- Expand reasoning beyond simple intent parsing and 1-2 hop traversal.
- Add job tracking to the actual ingest/extraction lifecycle, not just registries.
- Create a real meeting-room audio validation protocol and benchmark report.

### Low Priority

- Revisit archived concept modules only after the active MVP is stable.
- Add semantic reranking after semantic retrieval is non-mock by default in a configured demo.
- Add multi-user/shared workspace ideas after local single-user persistence is hardened.

## 10. Final Status Table

| Feature | Current Status | Evidence in Code | Risk Level | Recommendation |
| --- | --- | --- | --- | --- |
| Desktop PySide6 app | Implemented | `src/collective_mindgraph_desktop/ui/main_window.py` | Medium | Keep as primary frontend; improve contract tests. |
| Local FastAPI backend | Implemented | `realtime_backend/app/main.py`, `realtime_backend/app/api/routes.py` | Medium | Clarify backend ownership of graph/search responsibilities. |
| File transcription | Implemented | `/transcribe/file`, `TranscriptionService` | Medium | Validate with real audio and packaged runtime. |
| Streaming transcription | Partially implemented | `realtime_backend/app/api/ws.py`, `StreamingTranscriptionService` | Medium | Add end-to-end UI streaming tests. |
| Faster-Whisper ASR | Implemented when dependency/model available | `realtime_backend/app/pipeline/asr.py` | Medium | Report provider/fallback status clearly. |
| VAD | Implemented | `realtime_backend/app/pipeline/vad.py` | Low/Medium | Keep fallback explicit. |
| Diarization | Roadmap only as product claim | `realtime_backend/app/pipeline/diarization.py`, default disabled in `config.py` | High | Do not claim real speaker separation. |
| Speaker attribution | Partial/fallback | `speaker_mapper.py`, fallback `UNRESOLVED_0` | High | Only claim unresolved speaker labels unless validated. |
| Raw vs cleaned transcripts | Implemented | `TranscriptSegment`, `TranscriptPage` | Low | Keep audit UI prominent. |
| Heuristic extraction | Implemented | `ConversationSummaryService` | Medium | Keep as stable fallback; improve pattern tests. |
| Local LLM extraction | Partially implemented | `AIExtractionService`, `LocalLLMEndpointProvider` | High | Treat as optional until wired and validated. |
| Graph persistence | Implemented | `v2_graph_nodes`, `v2_graph_edges`, `ProductionGraphRepository` | Medium | Remove duplicate service drift. |
| Node/edge schema | Implemented | `core/memory_graph.py` | Medium | Version schema before export/import grows. |
| Source traceability | Implemented, partial UX | `SourceReference`, graph source refs, transcript page navigation | Medium | Add source-reference dereference tests. |
| Human review | Implemented | `ReviewQueuePage`, `update_node`, `InsightsPage` | Medium | Test full UI to search exclusion. |
| Keyword search | Implemented | Hybrid query services, SQL LIKE | Medium | Consider FTS and ranking. |
| Hybrid retrieval | Partially implemented | Core service has graph expansion; backend service has no-op graph expansion | High | Align implementations. |
| Semantic retrieval | Partially implemented | `SentenceTransformerEmbeddingProvider`, `VectorRepository` | High | Configure real model or label mock. |
| Evidence-only Ask Memory | Partially implemented | `EvidenceAnswerService`, `/memory/ask` | Medium/High | Fix desktop schema mismatch. |
| LLM-assisted Ask Memory | Stub/partial | `LLMAssistedAskService` | High | Keep optional and guarded. |
| Export/import | Implemented, needs hardening | `export_session`, `import_session` | Medium/High | Add schema version and collision-safe remapping. |
| Jobs | Partially implemented | Backend `JobManager`, desktop `JobRegistry` | Medium | Wire into actual background processing. |
| Diagnostics | Partially implemented | `DiagnosticsPage` | Medium | Make all statuses live, not static. |
| Offline safeguards | Implemented, configurable | `offline_safety.py`, LLM provider checks | Medium | Test every provider path; document escape hatches. |
| Full graph canvas | Roadmap only | `KnowledgeGraphPage` tables only | Low/Medium | Do not claim until built. |
| Production packaging | Partially implemented | `CollectiveMindGraph.spec`, `build_windows_exe.ps1` | High | Validate installer/runtime on clean Windows machine. |
| Real meeting validation | Roadmap only | Optional/fixture tests only | High | Create benchmark protocol before claims. |

## Bottom Line

Collective MindGraph has a credible local-first MVP foundation: desktop UI, local transcription pipeline, raw/clean transcript audit, deterministic extraction, graph persistence, review, source references, search, and evidence-oriented answering. The honest current claim is not "finished conversational intelligence platform"; it is "advanced local MVP with source-traceable transcript-to-memory graph workflows, deterministic fallback intelligence, and optional local AI paths."

The highest-risk overclaim areas are diarization, real speaker separation, semantic retrieval defaults, LLM stability, and production readiness. Those should remain explicitly bounded until validated by code, tests, and real-world audio runs.
