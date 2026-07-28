# Release Notes — Product Architecture Rework

## Highlights

- Consolidated all runtime code under `collective_mindgraph`.
- Introduced pure domain types and feature-focused application use cases.
- Made the localhost engine the sole owner of processing and persistent data.
- Added normalized SQLite persistence with backup-first legacy migration.
- Added a versioned `/api/v1` product API while preserving established
  transcription and memory transport contracts.
- Rebuilt the PySide6 interface as six bilingual workspaces.
- Added typed engine-client mapping, unified state presentation, and shared
  design tokens.
- Added real recording tasks with cancellation, retry lineage, restart
  recovery, staged progress, managed audio retention, and live PCM WebSocket
  capture with spool fallback.
- Added atomic runtime adapter hot-swap, truthful health states, knowledge
  indexing/reindexing, paginated evidence APIs, and sentence-grounded memory
  answers.
- Moved transcript annotation, validation, benchmark, and launcher code to
  canonical imports and installed entry points.
- Added architecture, migration, API, product-loop, UI, and import-safety tests.
- Enabled Ruff complexity/naming/import checks and strict domain/application
  type checking.

## Compatibility

- Canonical database location and user settings are preserved.
- Legacy desktop, engine, and JSON transcript data are imported without
  deleting source files.
- Existing external HTTP/WebSocket payloads remain supported.
- Earlier `v2_production_graph` export payloads remain importable.
- Old internal Python package paths are intentionally not supported.

## Known validation limits

Speaker separation remains experimental. The Windows executable builds and its
embedded engine passes a local health smoke test. Real meeting-room WER/CER,
code signing, installer certification, and repetition on a clean Windows
machine remain separate validation tasks.
