# Integration Test Hardening Report

## Branch

`fix/integration-test-hardening`

## What Was Tested

- Full local test suite with `PYTHONPATH=src;.` and `QT_QPA_PLATFORM=offscreen`.
- Manual offscreen desktop smoke: opened the app, loaded a temporary session, checked Diagnostics, rendered memory search, rendered Ask Memory evidence, and confirmed diarization displays `NOT IMPLEMENTED / ROADMAP`.
- Transcript-to-memory product loop through `tests/test_memory_track_end_to_end.py`.
- Hybrid memory query, backend Ask Memory endpoints, evidence-only answer service, source traceability, graph persistence, review lifecycle, export/import, and desktop Ask Memory parsing.
- PySide6 desktop smoke coverage for session list, main window ingest, global search, knowledge graph, memory search modes, and diagnostics.

## Baseline Failures

- Initial requested command failed because `pytest` was not installed in the active Python environment.
- After installing dev/runtime test dependencies, collection exposed a real syntax error in `src/collective_mindgraph/services/hybrid_memory_query_service.py`.
- Full suite then failed because `pytest-qt` was missing, so `qtbot` UI tests could not run.
- `tests/test_main_window_live_ingest.py` failed because `MainWindow` assumed every voice panel implementation exposes `backend_health_updated`; lightweight/offscreen smoke panels did not.

## Fixes Made

- Fixed the hybrid query vector-hit branch indentation so the core query service imports and executes.
- Added missing test/dev dependencies to `pyproject.toml` for backend endpoint tests and Qt UI smoke tests.
- Made `MainWindow` connect backend health diagnostics only when the voice panel exposes that signal, preserving real `VoiceCommandPanel` behavior while allowing lightweight smoke panels.
- Updated Diagnostics wording/statuses to distinguish:
  - `ACTIVE`
  - `DISABLED`
  - `OPTIONAL`
  - `ROADMAP`
  - `NOT IMPLEMENTED`
- Kept diarization explicitly reported as `NOT IMPLEMENTED / ROADMAP`.
- Kept semantic/vector search disabled unless a real local embedding provider is active.
- Kept Local LLM optional/disabled unless session metadata shows local LLM extraction.

## Tests Added Or Updated

- Added `tests/test_diagnostics_status_taxonomy.py` to lock Diagnostics status wording and prevent accidental diarization or semantic-search overclaims.
- Existing regression tests now cover the hybrid query syntax path and main-window offscreen ingest smoke flow.

## Final Test Results

Command:

```powershell
$env:PYTHONPATH='src;.'; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest
```

Result:

```text
180 passed, 3 skipped, 1 warning in 22.68s
```

Manual desktop smoke:

```text
manual desktop smoke passed: app opened, session loaded, diagnostics/search/Ask Memory rendered, diarization=NOT IMPLEMENTED / ROADMAP
```

Skipped optional checks:

- Local LLM endpoint not reachable at `http://127.0.0.1:1234/v1`.
- Real local semantic embedding model not configured.

## Remaining Risks

- This pass validates local fallback/evidence-only behavior, not live Local LLM answer quality.
- Semantic/vector retrieval remains configuration-dependent and is not active with mock embeddings.
- The full-scale simulation test still rewrites generated report artifacts during execution; those outputs were restored after the run to avoid committing test side effects.
- Real meeting-room ASR quality and WER/CER remain unvalidated without a local fixture.

## Still Not Implemented

- Diarization / automatic speaker separation.
- Cloud APIs or cloud-backed AI providers.
- Production claims for live Local LLM reliability.
- Production claims for semantic retrieval unless local embeddings are configured and usable.
