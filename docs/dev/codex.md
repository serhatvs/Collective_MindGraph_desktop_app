# Codex Repository Memory

## Project

- Collective MindGraph is a Windows-first, local-first meeting-memory desktop
  application built with Python 3.11+, PySide6, FastAPI, and SQLite.
- Production code lives under
  `src/collective_mindgraph/{domain,application,infrastructure,engine,desktop,tooling}`.
- The localhost engine is the only processing and persistent-data owner. The
  desktop uses typed HTTP/WebSocket clients.
- Code and technical identifiers are English. The desktop supports Turkish and
  English with immediate language switching.
- Claims remain evidence-bound. Confidence is not WER/CER; optional model and
  speaker features must report unavailable/experimental states honestly.

## Current State

- Remote `main` starts the public-production-v1 program at squash commit
  `f1e0305 refactor: complete product architecture rework`.
- Active branch: `chore/production-quality-baseline`, created directly from
  `origin/main`. It is stage 1 of the twelve-PR program documented in
  `docs/dev/PRODUCTION_V1_PROGRAM.md`.
- Draft delivery PR
  [#15](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/15)
  targets `main`; the stage will be squash-merged only after hosted gates and
  review are clean.
- Stage 1 adds locked `uv` resolution, Windows/Linux Python 3.11-3.13 CI,
  Ruff format/lint, full-suite and golden-contract checks, strict-mypy debt
  ratcheting, branch-inclusive and changed-line coverage, Bandit, pip-audit,
  secret scanning, dependency review, CodeQL, CycloneDX SBOM, and Windows
  packaged-engine smoke.
- Quality measurements: 75.36% branch-inclusive coverage, 79% statement
  coverage, and 304 existing strict-mypy errors across the full production
  package. CI rejects coverage below 75%, changed production lines below 90%,
  or any new/increased module/error-code type debt.
- The production module limit is now 400 lines with sixteen exact documented
  transition exceptions. Complexity is 12 with explicit existing exceptions.
- The isolated locked test environment exposed and fixed test-owned SQLite
  connection leakage and deterministic missing-path handling for the optional
  embedding adapter.
- The first hosted run exposed environment-only CI issues: Ubuntu lacked the
  Qt/EGL runtime required for offscreen PySide6 imports, and repository
  dependency alerts were disabled. The workflow now installs the minimal
  Linux Qt runtime, and GitHub vulnerability alerts/dependency graph support
  are enabled instead of bypassing dependency review. Hosted actions use
  current Node 24-compatible releases; setup-uv is pinned to its verified
  8.1.0 commit.

## Architecture and Runtime

- `domain`: dependency-free entities, identifiers, enums, and invariants.
- `application`: use cases and resource ports.
- `infrastructure`: SQLite/migration, audio/transcription, local AI, settings,
  and security adapters.
- `engine`: composition root, runtime manager, background coordinator, FastAPI,
  settings, and CLI.
- `desktop`: PySide6 shell, preferences, typed client, live capture, i18n, and
  engine lifecycle.
- `tooling`: transcript annotation, experiment, evaluation, and export tools.
- `EngineRuntimeManager` atomically swaps adapter bundles; queued/running jobs
  retain their enqueue-time snapshot.
- `RecordingJobCoordinator` owns task execution, cancellation, retry lineage,
  restart recovery, progress, indexing, and raw-audio retention.

## Data and Compatibility

- Canonical database:
  `%LOCALAPPDATA%\CollectiveMindGraph\collective_mindgraph.sqlite3`.
- Current schema version is 2 and export `format_version` is 4.
- Migration always uses backup plus sibling `.migrating` preparation,
  integrity/foreign-key/count/source-hash validation, and atomic activation.
  Legacy sources are never deleted.
- Desktop corrections win legacy conflicts. Engine sources only supplement
  missing graph, job, and diagnostics data.
- Legacy HTTP/WebSocket and `/api/v1` golden contracts remain compatibility
  boundaries throughout production v1.

## Product Behavior

- Current workspaces are Home, Capture, Meetings, Memory, Knowledge, and
  Settings.
- Recording upload creates real background jobs with progress, cancel, retry,
  restart recovery, and configurable raw-audio retention.
- Raw and corrected transcripts remain separate. Corrections preserve derived
  content and mark it for re-review.
- Knowledge and memory results remain evidence-backed. Semantic-only search
  fails honestly without embeddings; malformed/unsupported model answers fall
  back to evidence-only output.

## Public Production V1 Decisions

- Delivery is twelve separate squash PRs; every branch starts from the latest
  `main`, and `main` stays runnable/reversible.
- Local-only functionality remains complete with no account. Optional cloud
  sync is SaaS/self-host compatible and end-to-end encrypted; servers cannot
  read content.
- Identity is provider-independent OIDC. Roles are Owner, Admin, Editor,
  Reviewer, and Viewer.
- New device recovery uses a one-time recovery code or approved existing
  member/device. Removing a member rotates future keys but cannot revoke
  already downloaded plaintext.
- Desktop is the full client. Web is a small content-free administration
  surface. Collaboration is near-real-time sync, not live co-editing.
- Raw-audio sync is workspace opt-in and default off. Content-free telemetry is
  explicit opt-in and default off.
- Dark/system themes and a bounded native graph canvas are in scope.
- First SaaS region is EU; other residency is self-host. Billing/checkout is
  excluded, while quota and usage metering are required.
- Public distribution is proprietary, signed MSIX + App Installer. Models are
  downloaded only with approval from a signed catalog and live outside the
  application version.
- Retention defaults: deleted encrypted content 30 days, audit/tombstone
  metadata 90 days, encrypted backup/PITR data 35 days.

## Verification

- Latest automated run on stage 1: `297 passed, 4 skipped`; skips require real
  local models, audio fixtures, or hardware.
- Branch-inclusive coverage: 75.36%; changed production lines: 100%.
- Ruff format/lint, complexity ratchet, 400-line architecture policy,
  strict-mypy ratchet, compileall, high-confidence/high-severity Bandit, and
  runtime dependency audit pass locally.
- Audit of core, development, build, transcription, and local-AI dependency
  extras reports no known vulnerabilities. The baseline explicitly requires
  `transformers>=5.5` and current Hugging Face Hub compatibility.
- The original 407-test characterization target remains mapped in
  `tests/legacy_test_replacements.json`.

## External Release Gates

- Code-signing certificate/HSM, OIDC registrations, EU PostgreSQL/S3/SMTP,
  two clean Windows profiles, independent security/cryptography review, and
  consented/licensed Turkish reference recordings must be supplied before
  public `1.0.0`.
- Release-candidate hardware/model/clean-machine validations may not skip.

## Next Likely Tasks

- Review PR #15, address hosted-gate findings, squash-merge it, and verify
  remote `main`.
- Start `refactor/workspace-sync-identities` from the updated remote `main`.
- Introduce schema v3 workspace/global identities while preserving local
  integer IDs, backup-first migration, and every golden contract.
