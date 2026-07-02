# Memory Track Merge Readiness

Date: 2026-07-02

## Repo State

- Branch: `feature/transcript-to-memory-pipeline`
- Latest commit at audit start: `f0abe08 test: validate memory track end to end`
- Working tree at audit start: clean
- Recent Memory Track checkpoints present:
  - `b7aab23 fix: render desktop Ask Memory responses safely`
  - `7ca95dc fix: preserve explicit source trace metadata`
  - `64ac070 fix: map Ask Memory evidence to exact sources`
  - `166bf9a fix: expand backend hybrid memory search through graph`
  - `21d95e1 feat: wire extended extraction into memory graph`
  - `859fa5a feat: add memory review merge workflow`
  - `54ff161 fix: preserve memory graph state across export import`
  - `f0abe08 test: validate memory track end to end`

## Tests Run

```powershell
$env:PYTHONPATH='src;.'; $env:QT_QPA_PLATFORM='offscreen'; D:\Workspace\Collective-MindGraph-2\.venv-win\Scripts\python.exe -m pytest tests/test_memory_track_end_to_end.py tests/test_memory_export_import_roundtrip.py tests/test_knowledge_review_edit.py tests/test_extended_extraction_mapping.py tests/test_source_traceability.py tests/test_memory_ask_endpoint.py tests/test_backend_hybrid_memory_query.py tests/test_evidence_answer_service.py tests/test_desktop_ask_memory_response.py tests/test_ask_memory_evidence_validation.py -q
```

Result:

```text
38 passed, 1 warning in 8.52s
```

The warning was the existing `StarletteDeprecationWarning` from FastAPI/TestClient. Slow transcription/audio benchmarks were intentionally not run.

## Capability Status

| Feature | Status | Evidence | Notes |
| --- | --- | --- | --- |
| raw transcript storage | IMPLEMENTED | `transcript_analyses.raw_text_output`, `tests/test_memory_track_end_to_end.py` | Validated through desktop ingestion and export/import. |
| cleaned transcript storage | IMPLEMENTED | `transcripts.text`, `transcript_analyses.corrected_text_output`, `tests/test_memory_track_end_to_end.py` | Cleaned transcript is the main session transcript text. |
| segment storage | IMPLEMENTED | `transcript_analyses.segments_json`, `tests/test_memory_track_end_to_end.py` | Stored as analysis segments. |
| timestamps | IMPLEMENTED | `v2_source_references.timestamp_start/end`, `tests/test_source_traceability.py` | Preserved through source refs and export/import. |
| TASK extraction/mapping | IMPLEMENTED | `CollectiveMindGraphService.ingest_transcription_result`, `tests/test_memory_track_end_to_end.py` | Explicit structured task inputs map to V2 TASK nodes. |
| DECISION extraction/mapping | IMPLEMENTED | `CollectiveMindGraphService.ingest_transcription_result`, `tests/test_memory_track_end_to_end.py` | Explicit structured decision inputs map to V2 DECISION nodes. |
| TOPIC extraction/mapping | IMPLEMENTED | `CollectiveMindGraphService.ingest_transcription_result`, `tests/test_memory_track_end_to_end.py` | Explicit topic inputs map to V2 TOPIC nodes. |
| ENTITY mapping | IMPLEMENTED | `CollectiveMindGraphService._create_extended_extraction_nodes`, `tests/test_extended_extraction_mapping.py` | Uses explicit metadata, not arbitrary-text production extraction. |
| RISK mapping | IMPLEMENTED | `CollectiveMindGraphService._create_extended_extraction_nodes`, `tests/test_extended_extraction_mapping.py` | Uses explicit metadata. |
| OPEN_QUESTION mapping | IMPLEMENTED | `CollectiveMindGraphService._create_extended_extraction_nodes`, `tests/test_extended_extraction_mapping.py` | Uses explicit metadata. |
| FOLLOW_UP mapping | IMPLEMENTED | `CollectiveMindGraphService._create_extended_extraction_nodes`, `tests/test_extended_extraction_mapping.py` | Uses explicit metadata. |
| pending suggestions | IMPLEMENTED | V2 node `review_status="pending"`, `tests/test_knowledge_review_edit.py` | New extracted nodes start pending. |
| approve/edit/reject/disable lifecycle | IMPLEMENTED | `CollectiveMindGraphService.update_node`, `tests/test_knowledge_review_edit.py` | Metadata lifecycle is persisted. |
| merge lifecycle | IMPLEMENTED | `CollectiveMindGraphService.merge_nodes`, `tests/test_knowledge_review_edit.py` | Records merged source, target metadata, and `NODE_MERGED_INTO` edge. |
| V2 graph nodes | IMPLEMENTED | `v2_graph_nodes`, `ProductionGraphRepository.create_node` | SQLite-backed graph node persistence. |
| V2 graph edges | IMPLEMENTED | `v2_graph_edges`, `ProductionGraphRepository.create_edge` | SQLite-backed graph edge persistence. |
| source references | IMPLEMENTED | `v2_source_references`, `SourceReference` | Explicit session/segment/source reference id support. |
| source previews | IMPLEMENTED | `SourceReference.text_preview`, `tests/test_source_traceability.py` | Prefers cleaned segment text, then raw/fallback text. |
| per-evidence source mapping | IMPLEMENTED | `EvidenceAnswerService.ask`, `tests/test_evidence_answer_service.py` | Evidence steps include source ref/session/segment/preview/timestamps. |
| hybrid keyword search | IMPLEMENTED | `realtime_backend/app/services/hybrid_memory_query_service.py`, `tests/test_backend_hybrid_memory_query.py` | Runtime backend path supports keyword search. |
| graph expansion search | IMPLEMENTED | `HybridMemoryQueryService._add_graph_hit`, `tests/test_backend_hybrid_memory_query.py` | Keyword/vector hits expand to neighbors. |
| semantic/vector search | OPTIONAL | `VectorRepository`, `SentenceTransformerEmbeddingProvider`, `DiagnosticsPage.set_app_summary` | Depends on local embedding configuration; mock/default does not prove real semantic quality. |
| evidence-only Ask Memory | IMPLEMENTED | `/memory/ask`, `EvidenceAnswerService`, `tests/test_memory_ask_endpoint.py` | Evidence-only path is tested. |
| LLM-assisted Ask Memory | OPTIONAL | `LLMAssistedAskService`, `tests/test_ask_memory_evidence_validation.py` | Falls back to evidence-only when unavailable; Local LLM is not always active. |
| hallucination guard | PARTIAL | `LLMAssistedAskService` sentence validation, `tests/test_ask_memory_evidence_validation.py` | Exists for LLM-assisted response validation, not a complete universal guardrail. |
| export/import roundtrip | IMPLEMENTED | `CollectiveMindGraphService.export_session/import_session`, `tests/test_memory_export_import_roundtrip.py` | Tested for Memory Track graph/source/review/merge state. |
| diagnostics | PARTIAL | `DiagnosticsPage` | Exposes Memory/LLM/semantic status, but not a complete production observability system. |
| desktop Ask Memory UI | IMPLEMENTED | `AskMemoryPanel`, `tests/test_desktop_ask_memory_response.py` | Parser/render smoke tests cover full/minimal payloads and source buttons. |
| Knowledge Graph source navigation | IMPLEMENTED | `KnowledgeGraphPage.source_trace_requested`, `tests/test_source_traceability.py` | Uses explicit metadata before fallback. |
| diarization | NOT_IMPLEMENTED | Diagnostics labels and claim boundary docs | Do not claim implemented. |
| speaker separation | NOT_IMPLEMENTED | No validated speaker-separation pipeline in Memory Track | Do not claim implemented. |
| production packaging/installer | PARTIAL | Existing PyInstaller support, no Memory Track installer validation in this audit | Packaging is not merge-blocking for the Memory Track branch, but not complete production readiness. |

## Safe Product Claim

Collective MindGraph currently supports a local-first Memory Track that can turn transcript/session data into reviewable, source-linked graph memory, query it through hybrid search and evidence-only Ask Memory, and preserve tested memory state across export/import. Local LLM remains optional, semantic retrieval depends on local embedding configuration, and diarization/speaker separation are not implemented.

## Forbidden Claims

- Do not claim diarization exists.
- Do not claim speaker separation exists.
- Do not claim arbitrary-text extraction is production-perfect.
- Do not claim Local LLM is always active.
- Do not claim semantic/vector search always works without configured embeddings.
- Do not claim production packaging is complete.

## Remaining Risks

- The integrated validation uses explicit structured extraction metadata; production extraction quality from arbitrary transcripts still needs separate validation.
- Real semantic retrieval depends on a local embedding model path/provider and was not proven by this merge-readiness run.
- LLM-assisted Ask Memory is optional and guarded, but live Local LLM availability and answer quality vary by local endpoint/model.
- Diagnostics are useful but not a complete operational observability story.
- Packaging/installer validation for this Memory Track slice remains partial.

## Readiness Verdict

Merge-ready for the tested Memory Track scope.

The branch has focused regression coverage for the recent Ask Memory, source traceability, hybrid graph search, extended extraction mapping, review merge workflow, export/import, and end-to-end Memory Track scenario. No additional cleanup patch is recommended before merging this Memory Track branch to main, assuming main has not diverged in conflicting areas.

## Recommended Next Action

Merge to main.

After merge, the next implementation milestone should be chosen separately. The most useful next product step is likely first-class persistence/display of transcription language/profile metadata in Memory Track views and reports, but that is not a merge blocker for the current branch.
