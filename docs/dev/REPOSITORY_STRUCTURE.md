# Repository Structure and Ownership

This document is the authoritative map for repository layout, file lifecycle, and responsibility ownership. It describes the existing runtime boundaries; it does not redefine application behavior.

## Target structure

```text
Collective-MindGraph-2/
├── src/
│   ├── collective_mindgraph/             shared domain, memory, and infrastructure
│   └── collective_mindgraph_desktop/     production PySide6 desktop application
├── realtime_backend/
│   ├── app/                              production FastAPI/transcription backend
│   ├── scripts/                          backend-owned operational helpers
│   └── tests/                            backend unit and integration tests
├── tools/
│   └── transcript_annotation/            reusable annotation application and libraries
├── scripts/
│   ├── launch/                           developer and friend-alpha entry points
│   ├── benchmarks/                       comparative/report-producing benchmarks
│   ├── datasets/                         annotation experiment and export CLIs
│   ├── validation/                       runtime/provider validation
│   ├── setup/                            readiness and dependency bootstrap
│   └── packaging/                        build entry points
├── tests/                                cross-layer, desktop, shared-memory, and tool tests
├── docs/
│   ├── dev/                              maintained engineering documentation
│   ├── product/, demo/, alpha/, patent/  maintained audience-specific documentation
│   ├── reports/YYYY-MM-DD/                dated generated or measured evidence
│   └── archive/                           superseded plans, handoffs, and concepts
├── datasets/                             ignored local data; README tracked
├── models/                               ignored local model assets; README tracked
├── .github/                              repository-host configuration
├── .gitignore                            generated/local-data policy
├── AGENTS.md                             repository agent instructions
├── CollectiveMindGraph.spec              PyInstaller packaging configuration
├── pyproject.toml                        Python build, dependency, and pytest configuration
└── README.md                             project entry point
```

Stable production packages and tests remain in place because their ownership is already clear and moving them would add import and discovery risk without a runtime benefit.

## Classification map

| Path or item | Classification | Ownership |
| --- | --- | --- |
| `realtime_backend/app/` | `PRODUCTION_BACKEND`, `TRANSCRIPTION`, `EVALUATION`, `MEMORY` | FastAPI API, transcription pipeline, backend services, and backend runtime persistence. |
| `src/collective_mindgraph_desktop/` | `PRODUCTION_DESKTOP` | PySide6 UI, desktop orchestration, backend client, and desktop persistence integration. |
| `src/collective_mindgraph/` | `SHARED_DOMAIN`, `MEMORY` | Shared memory-graph types, interfaces, query services, and infrastructure used by the desktop layer. |
| `realtime_backend/app/evaluation/` | `EVALUATION` | Reference transcription metrics used by production-adjacent validation and scripts. |
| `tools/transcript_annotation/` | `ANNOTATION_TOOLING` | Reusable annotation dataset, experiment, export, pipeline, and UI implementation. |
| `scripts/launch/`, `scripts/setup/`, `scripts/packaging/` | `DEVELOPMENT_SCRIPT`, `PACKAGING` | Maintained operational entry points; see `scripts/README.md`. |
| `scripts/benchmarks/` | `BENCHMARK_SCRIPT` | Repository-wide comparative transcription benchmarks and shared harness. |
| `scripts/datasets/`, `scripts/validation/` | `DEVELOPMENT_SCRIPT` | Annotation workflow CLIs and runtime validation commands. |
| `realtime_backend/scripts/` | `DEVELOPMENT_SCRIPT` | Backend-local fixtures, readiness checks, seeding, and transcription helpers. |
| `realtime_backend/tests/` | `TEST` | Tests whose owner is the backend package and fixtures. |
| `tests/` | `TEST` | Cross-layer, desktop, shared-memory, benchmark, and annotation-tool tests. |
| `docs/dev/`, `docs/product/`, `docs/demo/`, `docs/alpha/`, `docs/patent/` | `CURRENT_DOCUMENTATION` | Maintained documentation grouped by audience. |
| `docs/archive/` | `HISTORICAL_DOCUMENTATION` | Superseded handoffs, plans, concepts, and retired documentation. |
| `docs/reports/` | `GENERATED_OUTPUT`, `HISTORICAL_DOCUMENTATION` | Dated benchmark and validation evidence; curated artifacts may be tracked. |
| `datasets/` | `DATASET`, `LOCAL_RUNTIME_DATA` | Ignored downloaded and annotation datasets; only the policy README is tracked. |
| `models/`, `wake_phrase_models/` | `MODEL_ASSET` | Ignored local model weights and caches; only the models policy README is tracked. |
| `recordings/`, `realtime_backend_data/`, `realtime_backend_temp/` and backend-local equivalents | `LOCAL_RUNTIME_DATA`, `GENERATED_OUTPUT` | Ignored recordings, transcripts, databases, uploads, and temporary audio. |
| `.gitignore`, `AGENTS.md`, `.github/`, `pyproject.toml` | `CONFIGURATION` | Repository, automation, build, dependency, and test configuration. |
| `CollectiveMindGraph.spec` | `PACKAGING` | Root-owned PyInstaller build specification. |
| `README.md` | `CURRENT_DOCUMENTATION` | Root project entry point; it links to canonical detailed documents. |
| ignored root `benchmark_results.json` | `OBSOLETE_OR_UNCLEAR`, `GENERATED_OUTPUT` | A legacy generic result filename with no single current producer or schema. It remains ignored for compatibility but is not a canonical output target. |
| ignored `video/` | `OBSOLETE_OR_UNCLEAR`, `LOCAL_RUNTIME_DATA` | A legacy local-media path with no active production owner found. It remains ignored to prevent accidental media commits. |

The two `OBSOLETE_OR_UNCLEAR` paths are intentionally not moved or deleted because they may contain user-local data and no safe migration owner exists.

## Authoritative implementation owners

| Responsibility | Authoritative owner |
| --- | --- |
| ASR provider implementation and profile resolution | `realtime_backend/app/pipeline/asr.py` |
| Audio inspection, FFmpeg resolution, and normalization | `realtime_backend/app/utils/audio_process.py` |
| Voice activity detection | `realtime_backend/app/pipeline/vad.py` |
| Transcription pipeline orchestration | `realtime_backend/app/pipeline/orchestrator.py` |
| Selective retranscription | `realtime_backend/app/pipeline/selective_retranscription.py` |
| Transcript formatting | `realtime_backend/app/pipeline/transcript_formatter.py` |
| Transcription glossary resolution | `realtime_backend/app/pipeline/transcription_glossary.py` |
| Reference WER/CER and domain-term metrics | `realtime_backend/app/evaluation/transcription_metrics.py` |
| Annotation dataset schema and persistence | `tools/transcript_annotation/dataset.py` |
| Annotation experiment mechanics | `tools/transcript_annotation/experiments.py` |
| Repository-wide benchmark entry points | `scripts/benchmarks/` |
| API and WebSocket serialization models | `realtime_backend/app/models.py` |
| ASR provider/runtime diagnostics | `realtime_backend/app/pipeline/asr_runtime_config.py` |
| Desktop diagnostics presentation | `src/collective_mindgraph_desktop/ui/pages/diagnostics_page.py` |
| Desktop transcription API client and settings | `src/collective_mindgraph_desktop/transcription.py` |
| Desktop SQLite schema and default database path | `src/collective_mindgraph_desktop/database.py` |
| Backend transcript JSON persistence | `realtime_backend/app/services/conversation_store.py` |
| Shared memory-graph schema | `src/collective_mindgraph/core/memory_graph.py` |
| Desktop/shared graph persistence | `src/collective_mindgraph/infrastructure/database/graph_repository.py` |
| Backend runtime graph persistence | `realtime_backend/app/services/graph_repository.py` |
| Current architecture documentation | `docs/dev/ARCHITECTURE.md` |
| Repository layout and lifecycle policy | `docs/dev/REPOSITORY_STRUCTURE.md` |
| Historical reports | `docs/reports/` |
| Historical handoffs and plans | `docs/archive/handovers/` |

The shared and backend graph repositories have separate runtime consumers today. Their mirrored behavior is an architectural drift risk, but moving or merging them is outside a structure-only change and would alter stable imports.

## Tests

Pytest discovery remains configured in `pyproject.toml` for `tests` and `realtime_backend/tests`. Backend tests stay beside the backend. Root tests remain flat because they frequently exercise multiple layers and several import script modules directly; grouping them now would be primarily aesthetic and would create path churn. New narrowly owned backend tests should go under `realtime_backend/tests`; new cross-layer, desktop, shared-memory, or tool tests should go under `tests` until a separate test move has a demonstrated discovery benefit.

## Generated and local data

- Source desktop runs launched from the repository root use ignored `recordings/` and `transcription_settings.json`. The desktop SQLite database uses the platform application-data directory.
- The maintained backend Bash launcher runs from `realtime_backend/`, so its defaults are ignored `realtime_backend/realtime_backend_data/` and `realtime_backend/realtime_backend_temp/`. Root equivalents remain ignored for direct/manual backend launches.
- Frozen Windows builds use `%LOCALAPPDATA%\CollectiveMindGraph\` for the SQLite database, recordings, settings, and embedded backend data/temp directories.
- `datasets/**` and `models/**` are ignored except for their policy README files. Annotation reports and exports below a dataset remain local.
- `build/`, `dist/`, coverage files, caches, logs, local databases, fixture WAVs, and the legacy `benchmark_results.json` are ignored.
- Curated benchmark and validation Markdown under `docs/reports/YYYY-MM-DD/` is the only tracked report evidence. New runs should use a dated topic directory and should be committed only after privacy and claim review.

No runtime path changed during repository organization, so no mandatory migration exists. Do not move local data automatically. A developer may manually consolidate root backend data into the backend-local directories only after stopping all processes and confirming which directory is active; changing `CMG_RT_DATA_DIR` or `CMG_RT_TEMP_DIR` is an explicit configuration decision.

## Entry points and compatibility

Maintained root-level developer commands are documented in `README.md` and `scripts/README.md`. Script paths moved to purpose directories, and all tracked internal references were migrated. No duplicate compatibility wrappers remain at the former paths. Python package imports, API routes, WebSocket payloads, persistence paths/schemas, settings behavior, benchmark report formats, and pytest discovery are unchanged.
