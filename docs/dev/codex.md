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

- Stages 1 to 8 were squash-merged through PRs
  [#15](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/15),
  [#21](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/21),
  [#23](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/23),
  [#24](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/24),
  [#25](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/25),
  [#26](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/26),
  [#27](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/27),
  and
  [#28](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/28);
  remote `main` is now
  `832c106 feat: add the theme layer, contrast gate, and opt-in telemetry`.
- Active branch: `feat/knowledge-canvas-retrieval`, created directly from that
  updated `origin/main`. It is stage 9 of the twelve-PR program documented in
  `docs/dev/PRODUCTION_V1_PROGRAM.md`.
- Stage 1 adds locked `uv` resolution, Windows/Linux Python 3.11-3.13 CI,
  Ruff format/lint, full-suite and golden-contract checks, strict-mypy debt
  ratcheting, branch-inclusive and changed-line coverage, Bandit, pip-audit,
  secret scanning, dependency review, CodeQL, CycloneDX SBOM, and Windows
  packaged-engine smoke.
- Current quality measurements are 81.41% branch-inclusive coverage and 295
  existing strict-mypy errors across the full production package. Stage 9
  changed-line coverage is 98%. CI rejects coverage below 75%, changed
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

## Synchronization Service

- Stage 4 adds `collective_mindgraph.sync_server`, documented in
  `docs/dev/SYNC_SERVICE.md`. It is a separate deployable, and the architecture
  rules forbid it from importing desktop, engine, or local persistence code so
  that it cannot acquire the ability to read plaintext.
- Storage is SQLAlchemy 2.x Core over PostgreSQL (asyncpg) with Alembic. Tests
  run against SQLite by default; setting `CMG_SYNC_TEST_DATABASE_URL` points the
  same suite at PostgreSQL, which the dedicated CI job does after migrating.
- Push is optimistic and idempotent: batches cap at 500 operations and 4 MiB,
  a client-generated `operation_id` makes replays return the original outcome,
  and a stale `base_revision` becomes a reported conflict rather than an
  overwrite. A batch is one transaction; mixed outcomes are expected.
- Pull is ordered by a per-workspace cursor row claimed under a row lock, so the
  counter row is created with the workspace instead of racing on first push.
- WebSocket invalidations carry `{workspace_id, cursor}` only; clients always
  react by pulling through the authorized path.
- Raw-audio blobs are opt-in per workspace, chunked, resumable, and verified per
  chunk and again on reassembly against the client-declared digest.
- Identity is provider-independent OIDC. Tokens are verified against the
  provider JWKS, issuer, and audience, and only asymmetric algorithms are
  accepted, so `alg: none` and symmetric tokens are refused. The bootstrap
  token resolver survives for self-host first run and tests only; without OIDC
  the service warns at startup and admin sign-in returns 401.
- The desktop signs in through the system browser with PKCE S256 and a
  loopback redirect on a request-time port, per RFC 8252 and RFC 7636.
- `/admin` renders membership, device, quota, and audit metadata only. It
  completes its code flow server-side, uses signed HttpOnly session cookies,
  CSRF tokens, and per-identity rate limits, and ships no JavaScript, which
  allows a `default-src 'none'` policy instead of the planned vendored HTMX.
- Alembic revision scripts are omitted from coverage because Alembic loads them
  through `exec()`; `tests/test_sync_operations_cli.py` runs a real upgrade and
  downgrade instead, and CI repeats the migration on PostgreSQL.
- Coverage does not trace code executed inside the `TestClient` portal thread.
  Repository behaviour is therefore asserted by async tests on the test's own
  event loop, with the HTTP module covering the wire contract.

## Desktop Synchronization Client

- Stage 6 puts the sync agent inside the engine. The desktop reaches the cloud
  only through localhost `/api/v2/sync` and owns no cursor or queue.
- `SqliteOutboxStore` is a transactional outbox that survives restart.
  Enqueueing uses `INSERT OR IGNORE`, so a retry after a crash cannot duplicate
  work through either the operation id or the revision constraint.
- A pass pushes everything queued, then pulls one page. A rejected change opens
  a conflict instead of overwriting, and the rejected operation leaves the queue
  for the conflict inbox.
- Resolutions are local, remote, or merged. Local and merged re-queue on top of
  the revision the service reported; remote just closes the conflict.
- Transient failures back off and never drop queued work; a refusal such as a
  removed membership is surfaced with its reason instead of stalling silently.
  When an error is recorded the status reports `offline` even with work queued,
  because reporting `pushing` would imply progress that is not happening.
- `/api/v2/sync` added exactly four OpenAPI paths; no `/api/v1` path changed,
  and `tests/fixtures/golden/openapi_surface.json` records the difference.

## Collaboration

- Stage 7 adds comments, mentions, and workspace activity, stored locally in the
  schema-v3 tables and exposed through `/api/v2/collaboration`.
- Comments and activity are append-only, which is exactly why they never reach
  the conflict inbox: two devices writing at once both keep their record.
- Mentions are parsed from the body, deduplicated, and case folded. Each comment
  records one `comment.added` event plus one `member.mentioned` per distinct
  mention. A reply must name an existing parent.
- Everything here is local storage; local-only use still requires no account and
  a test asserts the surface works with nobody signed in.

## Theme and Telemetry

- `desktop/ui/theme.py` holds every colour the shell paints. `design_tokens.py`
  is gone; a test asserts the rendered stylesheet contains no hex outside the
  active palette, so a hardcoded colour cannot survive a theme switch.
- Light and dark palettes are checked against WCAG 2.2 AA on every declared
  pairing. This is a release gate, and a separate test proves the gate rejects
  an unreadable palette rather than passing vacuously. Two border colours failed
  the first measurement and were corrected from measured values.
- `resolve(ThemeMode.SYSTEM, ...)` reads the platform palette; explicit light or
  dark overrides it. `apply_theme` repaints at runtime.
- `desktop/telemetry.py` is off until the user decides. Enabling without a
  recorded decision raises, withdrawal is immediate, and redaction keeps only
  declared fields with declared types, dropping everything else rather than
  sanitising it.
- Still open from stage 8's original scope: virtualized list models, capture and
  review polish, and the PySide6 presentation deferred from stage 7.

## Security Gate Availability

- The repository is private and GitHub reports Advanced Security as not
  purchased. CodeQL cannot upload results and dependency review cannot read the
  dependency graph; both jobs probe for the capability and skip with an explicit
  notice instead of failing or falsely passing.
- Bandit is the enforcing Python security gate, and `pip-audit` over every
  locked extra is the enforcing dependency gate, while those two are degraded.
- Secret scanning no longer uses the gitleaks Action, which reports through the
  GitHub API and cannot on this plan. It runs the pinned released binary over
  the full history instead, so it works regardless of the plan.
- These gates passed for stages 3 to 7, so the entitlement lapsed rather than
  never existing. Restoring it is a release-gate prerequisite: a scanner that
  cannot run has not found nothing.

## Search and Retrieval

- Keyword search is FTS5 with BM25 ordering, replacing `LIKE` substring scans.
  The `/api/v1` page contract is unchanged: ordering stays as it was, and
  relevance ranking is exposed on `/api/v2/knowledge/search` instead.
- `unicode61 remove_diacritics 2` folds ü, ö, ç, ş, ğ but **not** Turkish `ı`
  and `İ`, which are separate letters rather than accented forms. Both the
  index and the query fold them to plain `i`; a test pins this because without
  it "farkli" never reaches "farklı".
- Every query token is quoted, so user punctuation cannot become FTS5 syntax,
  and a term-free query matches nothing rather than everything.
- The index is a mirror kept current by triggers and rebuildable from the
  table, so a corrupt index is repaired rather than migrated.
- Hybrid retrieval fuses by rank, not score. With embeddings absent it degrades
  to keyword-only. Ties break on identifier so ordering is reproducible.
- Subgraph expansion is breadth-first, bounded by depth and by a 500-node cap
  the caller cannot raise, and reports truncation instead of hiding it.
- Layout is a pure function of node identifiers and edges, so the same graph
  always draws identically and pinned nodes never move.
- Still open from stage 9's scope: the native `QGraphicsScene` canvas widget
  and the USearch ANN adapter.

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

- Latest full automated run on stage 9: `544 passed, 4 skipped`; skips require
  real local models, audio fixtures, or hardware.
- Branch-inclusive coverage: 81.41%; stage-9 changed production lines: 98%.
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

- Finish the stage-9 hosted quality matrix, review, and squash PR.
- Stages 10 to 12 depend on inputs this repository cannot supply. The model
  manager, packaging configuration, and load harness can all be built, but the
  WER/DER numbers need consented Turkish recordings, a signed MSIX needs a
  code-signing certificate, and the release gate needs EU infrastructure and an
  independent cryptography review. Those must not be reported as met until the
  inputs exist.
- Keep the sync server free of any ability to decrypt: it stores sealed bytes,
  routing metadata, and audit records only.
