# Memory Track End-to-End Validation

Date: 2026-07-02

## Tested Scenario

A controlled Turkish technical meeting fixture was ingested through the desktop Memory Track service. The fixture included raw transcript text, cleaned transcript text, three timestamped segments, structured task/decision/topic extraction, and explicit metadata for entity, risk, open-question, and follow-up nodes.

The scenario validated this product loop:

```text
Transcript/session input
-> raw and cleaned transcript persistence
-> timestamped segments
-> structured extraction
-> TASK / DECISION / TOPIC / ENTITY / RISK / OPEN_QUESTION / FOLLOW_UP graph nodes
-> pending review suggestions
-> approve / edit / reject / disable / merge review actions
-> V2 graph persistence
-> source references with previews and timestamps
-> backend hybrid keyword + graph expansion search
-> evidence-only Ask Memory with per-evidence source metadata
-> export JSON
-> import into a fresh database/app service
-> post-import graph/search/Ask/source checks
```

## What Passed

- Session creation and transcript persistence were validated.
- Raw and cleaned transcript fields were retained in transcript analysis storage.
- Segment ids and timestamps survived ingestion and export/import.
- TASK, DECISION, TOPIC, ENTITY, RISK, OPEN_QUESTION, and FOLLOW_UP nodes were created from explicit extraction inputs.
- Extracted reviewable nodes started as pending.
- Source references carried explicit session id, segment id, preview text, and start/end timestamps.
- Review lifecycle actions were validated for approve, edit, reject, disable, and merge.
- Merge metadata survived: source node `review_status="merged"`, `merged_into_node_id`, target `merged_source_node_ids`, and merge edge persistence.
- Backend hybrid search excluded rejected, disabled, and merged source nodes while keeping approved/edited nodes available.
- Evidence-only Ask Memory returned evidence for a matching query and included exact per-evidence source metadata.
- Export/import preserved the tested Memory Track state and post-import query/Ask checks still worked.

## What Is Still Partial

- The test uses explicit structured extraction metadata. It does not validate production-quality extraction from arbitrary free text.
- Semantic/vector retrieval remains optional and configuration-dependent; this validation uses keyword plus graph expansion.
- The language/transcription profile metadata is present in the fixture metadata, but the current desktop transcript analysis model does not treat it as a first-class persisted field in this end-to-end path.
- The validation is deterministic and local; it is not a real meeting-room audio benchmark.

## What Is Not Claimed

- Diarization and speaker separation are not implemented or validated.
- Local LLM assistance is not required and is not claimed as always active.
- Retrieval and extraction are not claimed to be production-perfect.
- This does not validate ASR, Faster-Whisper, VAD, audio preprocessing, or transcription quality.

## Test Command

```powershell
$env:PYTHONPATH='src;.'; $env:QT_QPA_PLATFORM='offscreen'; D:\Workspace\Collective-MindGraph-2\.venv-win\Scripts\python.exe -m pytest tests/test_memory_track_end_to_end.py tests/test_memory_export_import_roundtrip.py tests/test_knowledge_review_edit.py tests/test_extended_extraction_mapping.py tests/test_source_traceability.py tests/test_memory_ask_endpoint.py tests/test_backend_hybrid_memory_query.py tests/test_evidence_answer_service.py -q
```

## Test Result

Full targeted validation passed:

```text
29 passed, 1 warning in 9.25s
```

The warning was the existing `StarletteDeprecationWarning` from FastAPI/TestClient.

## Current Safe Product Claim

Collective MindGraph currently supports a local-first Memory Track that can turn transcript/session data into reviewable, source-linked graph memory, query it through hybrid search and evidence-only Ask Memory, and preserve tested memory state across export/import. Local LLM remains optional, and diarization/speaker separation are not implemented.
