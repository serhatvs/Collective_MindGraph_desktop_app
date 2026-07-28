# Codex Repository Memory

## Project

- Collective MindGraph is a Windows-first, local-first meeting-memory desktop
  application for one local user.
- Primary stack: Python 3.11+, PySide6, FastAPI, SQLite, Faster-Whisper, and
  optional local language/embedding providers.
- Code and technical identifiers are English. The desktop supports Turkish and
  English with immediate language switching.
- Claims stay evidence-bound: speaker separation is experimental, confidence
  estimates are not WER/CER, and model features require configured local
  adapters.

## Current State

- Active branch: `refactor/product-architecture-rework`, based on
  `refactor/engineering-cleanup` at `f5b9791`.
- Runtime code is consolidated under
  `src/collective_mindgraph/{domain,application,infrastructure,engine,desktop,tooling}`.
  Former backend, desktop, service, and tool package roots are removed without
  internal import shims.
- The localhost engine is the only processing and persistent-data owner. The
  PySide6 desktop communicates through typed HTTP/WebSocket clients.
- The desktop contains Home, Capture, Meetings, Memory, Knowledge, and Settings
  workspaces with Turkish/English catalogs and shared state/design components.
- All production modules are at or below 500 lines; the line-limit allowlist is
  empty.

## Architecture and Runtime

- `domain`: dependency-free entities, identifiers, enums, and invariants.
- `application`: feature use cases and resource ports.
- `infrastructure`: SQLite, migration, audio, transcription, local AI,
  preferences, and safety adapters.
- `engine`: composition root, runtime manager, background coordinator, FastAPI,
  settings, and CLI.
- `desktop`: PySide6 shell, QSettings preferences, typed engine client, live
  audio/WebSocket capture, i18n, and engine lifecycle.
- `tooling`: transcript annotation, experiment, evaluation, and export tools.
- `EngineRuntimeManager` validates and atomically swaps immutable adapter
  bundles. Running jobs retain their starting snapshot.
- `RecordingJobCoordinator` owns actual tasks, cancellation, retry lineage,
  restart recovery, progress, knowledge indexing, and raw-audio retention.

## Data and Compatibility

- Canonical database:
  `%LOCALAPPDATA%\CollectiveMindGraph\collective_mindgraph.sqlite3`.
- Schema version 2 stores recording retention and explicit job relationships.
- Migration discovers environment overrides, former repository-local engine
  data, executable-side data, and canonical transcript archives in a stable
  order.
- Every install/upgrade/import builds a sibling `.migrating` database. Existing
  canonical data is backed up, copied, supplemented, validated, and atomically
  replaced. Already-current/idempotent startup does not create redundant
  backups.
- Desktop corrections win conflicts; engine sources only supplement missing
  graph, job, and diagnostics data. Legacy sources are never deleted.
- Exports use `format_version: 4`; older canonical payloads and
  `v2_production_graph` imports remain supported.
- Established HTTP/WebSocket payloads remain compatibility adapters. Old
  internal Python imports are intentionally unsupported.

## Product Behavior

- Recording upload returns `202` with a real `ProcessingJob`; progress,
  cancellation, retry, restart failure recovery, and audio retention are
  persisted.
- Successful audio is deleted by default; failed/cancelled audio is retained
  for retry. Users can enable permanent retention.
- Live capture uses `QAudioSource` and typed `QWebSocket`, shows partial
  transcript/progress, and uploads a local spool file if finalization fails.
- New transcripts create meeting, segment, insight and person/entity knowledge
  nodes with evidence-backed `contains`, `derived_from`, `mentions`, and
  `assigned_to` relationships.
- Semantic-only search fails honestly when embeddings are unavailable; hybrid
  mode falls back with a warning. Enabling embeddings schedules reindexing.
- Memory answers validate known evidence IDs and sentence-level citations.
  Malformed or unsupported model output falls back to evidence-only answers.
- Review queues include pending and `needs_review`; transcript corrections
  preserve raw text and mark derived accepted content for re-review.

## Verification

- Latest full suite: `275 passed, 4 skipped`; skipped cases require optional
  real models/audio/hardware.
- The original 407-test characterization target is recorded in
  `tests/legacy_test_replacements.json`; every removed legacy test module has an
  explained canonical replacement.
- Ruff and the empty 500-line allowlist pass. Strict mypy covers domain and
  application.
- Ruff, strict domain/application mypy, compileall, architecture/line-limit,
  import timing, source-engine lifecycle, and the full automated suite pass.
- The Windows one-file executable was rebuilt without optional semantic-model
  packages and its embedded engine passed the isolated packaged-health smoke
  check. Build output remains ignored.
- Documentation, diff whitespace, ignored-artifact boundaries, and Git scope
  were reviewed for the single architecture-rework delivery commit.

## Durable Decisions

- Keep PySide6 and a separately managed loopback engine process.
- Keep the canonical language `Meeting`, `Recording`, `Transcript`,
  `TranscriptSegment`, `Insight`, `EvidenceReference`, `KnowledgeNode`,
  `KnowledgeEdge`, `ProcessingJob`, and `EngineHealth`.
- Review values remain pending/accepted/rejected; edit and re-review audit state
  is separate.
- Preserve raw/corrected transcript material separately.
- Keep wake phrase, unvalidated speaker separation, and expert ASR clearly
  experimental.
- Do not add graph canvas, multi-user sync, cloud services, or dark theme in
  this cutover.
- Never delete user models, datasets, recordings, databases, ignored legacy
  environments, or transcript archives.

## Next Likely Tasks

- Merge the completed architecture-rework commit when its review is accepted.
- Validate optional Turkish meeting-room fixtures and target hardware on a
  clean Windows machine.
