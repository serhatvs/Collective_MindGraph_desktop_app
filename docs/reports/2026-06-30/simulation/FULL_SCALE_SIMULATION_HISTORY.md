# FULL SCALE SIMULATION HISTORY

## Chronological Audit Log
1. **Simulated Transcript Created**: Generated 10+ minute equivalent Turkish technical meeting.
2. **Session Ingested**: ID `5`.
3. **Extraction Run**: `AIExtractionService` invoked with mode `heuristic_fallback`.
4. **Graph Persisted**: `TranscriptionResult` mapped and saved via `ingest_transcription_result`. Custom logic added for Risks and Open Questions.
5. **Review Actions Applied**:
   - 12 items approved.
   - 2 items edited.
   - 2 items rejected.
   - 1 item merged.
   - 2 items disabled.
   - Remaining left pending.
6. **Reasoning Queries Run**: 5 intent-based graph traversals tested.
7. **Ask Memory Tested**: 5 complex multi-hop questions run through both `evidence_only` and `llm_assisted` pipelines. Hallucination guard behaved as expected.
8. **Search Tested**: Hybrid query executed for 7 keywords involving Vector and Text matches.
9. **Export Generated**: JSON payload dumped to `D:\Workspace\Collective-MindGraph-2\docs\reports\2026-06-30\simulation\export_simulation.json`.
10. **Final Findings**: All systems stable. Some edge schema mapping improvements identified.
