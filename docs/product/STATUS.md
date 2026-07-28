# Collective MindGraph Product Status

## Implemented

- One canonical `collective_mindgraph` package with enforced layer boundaries
- Native PySide6 shell with Home, Capture, Meetings, Memory, Knowledge, and
  Settings workspaces
- Runtime-switchable Turkish and English catalogs
- Automatically managed localhost engine and typed desktop client
- Live and file transcription paths with existing HTTP/WebSocket compatibility
- Raw/corrected transcript separation and segment correction
- Reviewable insights with accepted, rejected, and pending decisions
- Evidence references, knowledge nodes and edges, filterable table exploration
- Keyword/hybrid memory search and evidence-only answers
- Optional local embeddings and local-language-model enrichment
- Real background jobs with staged progress, task cancellation, retry lineage,
  restart recovery, and configurable raw-audio retention
- Versioned export/import, including legacy graph payload import
- Backup-first, idempotent migration into one normalized SQLite database
- Loading, empty, offline, retry, and error states across workspaces
- Transcript annotation, benchmark, dataset, validation, and packaging tooling

## Validation boundary

The automated suite covers domain rules, persistence, migration, new and
compatibility APIs, WebSocket behavior, desktop rendering, transcription
adapters, memory/review workflows, imports, and tooling. Source-engine startup,
desktop-managed engine autostart/shutdown, and the packaged engine health
endpoint have also been smoke-tested on the current Windows development
machine.

The following claims are intentionally not made:

- validated speaker separation;
- measured accuracy for noisy, overlapping, far-field meeting rooms;
- semantic quality when only the mock embedding adapter is enabled;
- local-model availability when no endpoint/model is configured;
- a signed or installer-certified Windows release.

Confidence estimates are diagnostics, not reference-based WER/CER.

## Experimental controls

Wake phrase, unvalidated speaker separation, and expert ASR settings remain
available only under Labs or advanced settings and are labelled experimental.
There is no graph canvas or multi-user synchronization in this release.

## Data and privacy

The engine is the only persistent-data owner. It binds to localhost and uses
the canonical database at
`%LOCALAPPDATA%\CollectiveMindGraph\collective_mindgraph.sqlite3`.

Migration keeps legacy databases and transcript archives untouched. Import and
export payloads declare an explicit format version.

## Next validation work

- Run real Turkish meeting-room fixtures with human reference transcripts.
- Validate Silero and optional speaker separation on the target Windows
  hardware.
- Repeat the PyInstaller smoke test on a clean Windows machine before public
  distribution.
- Tighten type checking for infrastructure and desktop after the strict
  domain/application baseline.
