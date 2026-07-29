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

- Stages 1 and 2 were squash-merged through
  [PR #15](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/15)
  and
  [PR #21](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/21);
  remote `main` is now
  `1762b93 refactor: establish workspace sync identities`.
- Active branch: `feat/e2ee-key-management`, created directly from that updated
  `origin/main`. It is stage 3 of the twelve-PR program documented in
  `docs/dev/PRODUCTION_V1_PROGRAM.md`.
- Stage 1 adds locked `uv` resolution, Windows/Linux Python 3.11-3.13 CI,
  Ruff format/lint, full-suite and golden-contract checks, strict-mypy debt
  ratcheting, branch-inclusive and changed-line coverage, Bandit, pip-audit,
  secret scanning, dependency review, CodeQL, CycloneDX SBOM, and Windows
  packaged-engine smoke.
- Current quality measurements are 77.72% branch-inclusive coverage and 298
  existing strict-mypy errors across the full production package. Stage 3
  changed-line coverage is 99%. CI rejects coverage below 75%, changed
  production lines below 90%, or any new/increased module/error-code type debt.
- The production module limit is now 400 lines with fifteen exact documented
  transition exceptions after stage 2 split canonical data exchange.
  Complexity is 12 with explicit existing exceptions.
- The isolated locked test environment exposed and fixed test-owned SQLite
  connection leakage and deterministic missing-path handling for the optional
  embedding adapter.
- The desktop-owned engine process now continuously drains a bounded
  diagnostic-output tail, preventing an unattended QProcess pipe from
  blocking and making startup failures observable across platforms. Source
  launch preserves the virtual-environment interpreter path on POSIX instead
  of resolving its symlink to an environment-less base Python.
- The first hosted run exposed environment-only CI issues: Ubuntu lacked the
  Qt/EGL runtime required for offscreen PySide6 imports, and repository
  dependency alerts were disabled. The workflow now installs the minimal
  Linux Qt runtime, and GitHub vulnerability alerts/dependency graph support
  are enabled instead of bypassing dependency review. Hosted actions use
  current Node 24-compatible releases; setup-uv is pinned to its verified
  8.1.0 commit.

## Encryption

- Stage 3 adds the end-to-end encryption contract described in
  `docs/dev/CRYPTO_THREAT_MODEL.md`. Content uses AES-256-GCM whose associated
  data length-prefixes workspace, object type, object UUID, revision, and key
  version, so ciphertext cannot be replayed onto another revision or version.
- Workspace keys are wrapped per recipient with ephemeral X25519 plus
  HKDF-SHA256; the derivation info doubles as envelope associated data.
  Recovery uses a checksummed 256-bit Crockford base32 code with scrypt.
- Device private keys never reach SQLite. They live in a `DeviceSecretStore`
  sealed by Windows DPAPI under the current user; other platforms fall back to
  an owner-only file store that reports `protected = False` honestly.
- `WorkspaceKeyService` owns initialization, unlock, enrollment, recovery,
  rotation, and revocation. Revoking a device revokes its envelopes and rotates
  the key; rotation protects future content only and never recalls plaintext a
  removed device already held.
- Primitive behaviour is pinned by RFC 7748, RFC 5869, and published AES-GCM
  specification vectors rather than by self-generated expectations.
- `tests/conftest.py` redirects `CMG_DATABASE_PATH`, `LOCALAPPDATA`, and POSIX
  `HOME` for the whole session. Without it, any test constructing
  `EngineSettings` without an explicit `database_path` reads and writes the
  developer's installed database.

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
- Stage 2 advances the schema to version 3. Existing local identifiers remain
  unchanged while workspaces and synchronized rows receive stable UUID
  identities, local/sync revisions, and updated-by-device metadata.
- The local schema includes transactional outbox/state/tombstone/conflict
  foundations plus device, key-envelope, comment, activity, and model-registry
  tables. A generated Local Workspace owns all pre-existing rows.
- Canonical export `format_version` is 5; v3/v4 and legacy graph imports remain
  accepted. User backups default to authenticated AES-256-GCM `.cmgbackup`
  archives derived from a user passphrase with scrypt.
- V5 import and migration activation validate UUID/revision metadata and reject
  synchronized rows whose workspace does not exist in the local database or
  import payload, preventing orphaned workspace data in ALTER-upgraded tables.
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

- Latest full automated run on stage 3: `361 passed, 4 skipped`; skips require
  real local models, audio fixtures, or hardware.
- Branch-inclusive coverage: 77.72%; stage-3 changed production lines: 99%.
  The single uncovered changed line is the POSIX permission call, which the
  Linux coverage job exercises instead.
- Gated Bandit (high severity, high confidence) is clean. The unfiltered scan
  reports two `B105` false positives for the `device-private-key` secret-name
  prefix and the `.secret` file extension.
- Ruff format/lint, complexity ratchet, 400-line architecture policy,
  strict-mypy ratchet, compileall, high-confidence/high-severity Bandit, and
  runtime dependency audit pass locally.
- Audit of core, development, build, transcription, and local-AI dependency
  extras reports no known vulnerabilities. Authenticated backup support is
  pinned to `cryptography>=48.0.1,<49` after dependency audit rejected the
  vulnerable 46.x resolution. The baseline explicitly requires
  `transformers>=5.5` and current Hugging Face Hub compatibility.
- The Windows package rebuild succeeds with the cryptography runtime included.
  This workstation now enforces an enterprise signing policy and blocks the
  newly rebuilt unsigned executable before launch; hosted Windows package
  smoke remains the authoritative stage-2 execution gate. Signed artifacts
  remain an external stage-11 input.
- The original 407-test characterization target remains mapped in
  `tests/legacy_test_replacements.json`.

## External Release Gates

- Code-signing certificate/HSM, OIDC registrations, EU PostgreSQL/S3/SMTP,
  two clean Windows profiles, independent security/cryptography review, and
  consented/licensed Turkish reference recordings must be supplied before
  public `1.0.0`.
- Release-candidate hardware/model/clean-machine validations may not skip.

## Next Likely Tasks

- Finish the stage-3 hosted quality matrix, review, and squash PR.
- After stage 3 merges, start `feat/sync-service-core` from the new `main`:
  the opaque PostgreSQL/S3 sync runtime, cursor push/pull, blob manifests,
  and the retention windows already fixed by the program document.
- Keep the sync server free of any ability to decrypt: it stores sealed bytes,
  routing metadata, and audit records only.
