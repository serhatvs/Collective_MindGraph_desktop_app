# Collective MindGraph Architecture

## Runtime shape

Collective MindGraph has one Python distribution and two local processes:

```text
PySide6 desktop
      |
      | typed HTTP/WebSocket client
      v
localhost FastAPI engine
      |
      +-- application use cases
      +-- transcription and local-AI adapters
      +-- canonical SQLite database
```

The desktop owns presentation, user interaction, audio capture, language
catalogs, and engine lifecycle. The engine owns processing, use-case
composition, settings exposed through the API, migration, and all persistent
data. The desktop never writes SQLite directly.

## Package boundaries

```text
src/collective_mindgraph/
  domain/          pure entities, identifiers, enums, and invariants
  application/     use cases and port protocols
  infrastructure/  SQLite, audio, ASR, VAD, embeddings, and local-model adapters
  engine/          composition root, FastAPI, settings, and process entry point
  desktop/         typed client, PySide6 shell, workspaces, and i18n
  tooling/         transcript annotation application
```

Dependency direction is enforced by tests:

```text
domain <- application <- infrastructure <- engine
                                  ^
                                  |
                               desktop
                         (through API contracts)
```

- `domain` imports no Qt, FastAPI, SQLite, or provider implementation.
- `application` imports no infrastructure, engine, or desktop implementation.
- `infrastructure` implements application ports and imports no engine or
  desktop code.
- `engine` composes concrete adapters and exposes transport contracts.
- `desktop` communicates with the engine through `EngineClient`.

## Canonical domain

The product vocabulary is `Meeting`, `Recording`, `Transcript`,
`TranscriptSegment`, `Insight`, `EvidenceReference`, `KnowledgeNode`,
`KnowledgeEdge`, `ProcessingJob`, and `EngineHealth`.

Lifecycle and review values are typed with `MeetingStatus`,
`ProcessingStatus`, `InsightKind`, and `ReviewDecision`. Raw transcript text is
immutable during correction; corrected text and review audit state are stored
separately.

## Core use cases

- Meeting create, list, update, and archive
- File/live recording transcription
- Transcript-segment correction
- Insight acceptance or rejection
- Keyword, semantic, and hybrid memory search
- Evidence-only and optional local-model answers
- Knowledge-node and relationship exploration
- Job listing, retry-safe status, and cancellation
- Versioned import and export

Transcription orchestration is exposed to the application through a processing
port. Concrete FFmpeg, ASR, VAD, speaker mapping, and local-model behavior lives
under `infrastructure`.

## Persistence and migration

`SqliteDatabase` is the canonical connection owner. The normalized schema
contains:

- `meetings`, `recordings`
- `transcripts`, `transcript_segments`
- `insights`, `evidence_references`
- `knowledge_nodes`, `knowledge_edges`, `embeddings`
- `processing_jobs`
- `schema_migrations`, `migration_sources`

`LegacyDataMigrator` detects legacy desktop SQLite data, engine graph/job data,
and JSON transcript archives. It:

1. creates a timestamped full backup when replacing a legacy canonical file;
2. builds a sibling `.migrating` database;
3. prioritizes desktop corrections and enriches them with engine diagnostics;
4. records source hashes for idempotency;
5. runs integrity and foreign-key checks;
6. atomically activates the validated database.

Failures leave the original canonical database in place. Legacy sources are not
deleted.

Exports use `format_version: 4`. Import retains compatibility with earlier
canonical payloads and the
`v2_production_graph` payload key as an external data-format contract; no old
Python package import path is retained.

## Engine API

`create_app()` is side-effect free. Directories, settings stores, databases,
models, and processing adapters are created only inside FastAPI lifespan.

The product API is rooted at `/api/v1` and covers dashboard, meetings,
recordings, transcripts, evidence, insights, memory, knowledge, jobs, settings,
health, import, and export. Recording upload returns a `202 ProcessingJob`;
actual tasks, cancellation, retry, restart recovery, progress, and retention
are engine-owned. Live PCM capture uses the meeting recording WebSocket.
List endpoints use opaque cursor pagination with a default limit of 50 and
maximum of 200. Product errors contain:

```json
{
  "code": "validation_error",
  "message": "The request could not be validated.",
  "details": {},
  "retryable": false
}
```

The established `/transcribe/file`, `/transcribe/stream`, `/transcript`,
`/summary`, `/quality`, `/query`, `/reason`, `/memory/ask`, `/jobs`, and
`/health` transport contracts remain available through adapters.

## Desktop

The PySide6 shell contains six workspaces: Home, Capture, Meetings, Memory,
Knowledge, and Settings. Shared design tokens and `StatePanel` provide
consistent loading, empty, offline, retry, and error states.

English and Turkish UTF-8 catalogs have identical keys. The OS locale selects
the initial language, English is the fallback, and `QSettings` persists an
explicit user choice. Language changes are applied immediately.

Wake phrase, unvalidated speaker separation, and expert ASR controls are
isolated under Labs or advanced settings. The Knowledge workspace deliberately
uses tables and evidence details rather than an unvalidated graph canvas.

## Safety boundaries

- Engine listeners are restricted to loopback addresses.
- Local-model URLs accept only HTTP(S) endpoints on localhost or local/private
  addresses.
- Conversation identifiers and filesystem paths are validated at boundaries.
- Uploads move into contained managed storage. Successful raw audio is deleted
  by default; failed/cancelled sources are retained for retry, and permanent
  retention is an explicit preference.
- No import or test discovery path creates databases, directories, models, or
  network connections.
