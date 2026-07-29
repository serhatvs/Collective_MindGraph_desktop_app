# Public Production V1 Program

Collective MindGraph will reach public `1.0.0` through twelve squash-merged
pull requests. Every branch starts from the then-current `main`; `main` must
remain runnable and reversible after each merge.

## Delivery sequence

| Stage | Branch | Outcome | Status |
| --- | --- | --- | --- |
| 1 | `chore/production-quality-baseline` | Locked dependencies, CI, quality/security ratchets, SBOM and package smoke | Merged in PR [#15](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/15) (`4ee7949`) |
| 2 | `refactor/workspace-sync-identities` | Schema v3, workspace/global identities, outbox and encrypted backup foundation | Merged in PR [#21](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/21) (`1762b93`) |
| 3 | `feat/e2ee-key-management` | Device/workspace keys, recovery and rotation | Merged in PR [#23](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/23) (`f067c37`) |
| 4 | `feat/sync-service-core` | Opaque PostgreSQL/S3 sync service and retention | Merged in PR [#24](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/24) (`a5172ec`) |
| 5 | `feat/oidc-rbac-admin` | OIDC PKCE, fixed roles and content-free web admin | Merged in PR [#25](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/25) (`4bc49d3`) |
| 6 | `feat/desktop-sync-client` | Engine-owned offline/near-real-time sync and conflicts | Merged in PR [#26](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/26) (`88939d6`) |
| 7 | `feat/collaboration-experience` | Workspace, activity, comments, mentions and recovery UX | Merged in PR [#27](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/27) (`119d916`) |
| 8 | `feat/desktop-product-polish` | Themes, contrast gate and opt-in telemetry | Merged in PR [#28](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/28) (`832c106`) |
| 9 | `feat/knowledge-canvas-retrieval` | FTS5, rank fusion, bounded subgraph and deterministic layout | Merged in PR [#29](https://github.com/serhatvs/Collective_MindGraph_desktop_app/pull/29) (`89966d4`) |
| 10 | `feat/audio-model-quality` | Signed model manager and evidence-based quality gates | In review |
| 11 | `build/signed-msix-release` | Signed MSIX/App Installer and deployable self-host stack | Planned |
| 12 | `release/production-v1-hardening` | Scale, clean-machine, restore, security and 1.0.0 gates | Planned |

## Non-negotiable boundaries

- Local-only use remains complete and requires no account.
- The desktop talks to the localhost engine; it never talks directly to cloud
  services.
- Sync servers receive only ciphertext plus bounded routing/audit metadata.
  Transcript, audio, evidence, knowledge content, and search indexes remain
  client-side.
- Legacy HTTP/WebSocket and `/api/v1` golden contracts remain compatible.
- Existing user data is upgraded only through backup, sibling staging,
  integrity/foreign-key/count validation, and atomic activation.
- Raw-audio sync and content-free telemetry are separately opt-in and default
  to off. Model downloads always require explicit approval.

## Delivered cryptography contract

Stage 3 fixes the encryption contract every later stage depends on. Details and
the independent-reviewer checklist live in `CRYPTO_THREAT_MODEL.md`.

- Content uses AES-256-GCM. Associated data binds workspace, object type,
  object UUID, revision, and key version with length-prefixed fields.
- Workspace keys are wrapped per recipient with ephemeral X25519 and
  HKDF-SHA256; the derivation info also authenticates the envelope.
- Recovery uses a 256-bit Crockford base32 code with a checksum and scrypt
  derivation. The code is displayed once and never persisted.
- Device private keys live in a `DeviceSecretStore` outside SQLite, sealed with
  Windows DPAPI under the current user account.
- Removing a device revokes its envelopes and rotates the key. Rotation
  protects future content only and cannot recall already decrypted content.
- Primitive behaviour is pinned by RFC 7748, RFC 5869, and published AES-GCM
  specification vectors.

## Delivered service contract

Stage 4 adds `collective_mindgraph.sync_server`, a separate deployable that the
architecture rules forbid from importing the desktop, the local engine, or local
persistence. Details live in `SYNC_SERVICE.md`.

- Push batches are capped at 500 operations and 4 MiB, applied in one
  transaction, and made idempotent by client-generated operation identifiers.
- Writes are optimistic: a stale `base_revision` becomes a reported conflict,
  never a silent overwrite, and a replayed conflict returns the same answer.
- Pull is ordered by a per-workspace cursor claimed under a row lock.
- WebSocket invalidations carry a workspace identifier and a cursor only.
- Raw-audio blobs stay opt-in per workspace, upload in resumable chunks, and are
  verified per chunk and again on reassembly against the declared digest.
- Retention is enforced by `mindgraph-admin purge`: content 30 days, audit and
  tombstone metadata 90 days, encrypted backup and PITR data 35 days.
- Identity is a documented bootstrap resolver until stage 5 introduces OIDC;
  roles are already enforced on every route.

## Delivered identity contract

Stage 5 makes identity provider-independent OIDC. Details live in
`SYNC_SERVICE.md`.

- The desktop signs in through the operating system's browser with
  Authorization Code, PKCE `S256`, and a loopback redirect on a port chosen at
  request time, as RFC 8252 and RFC 7636 require. The PKCE challenge is pinned
  by the RFC 7636 appendix vector.
- The service verifies every token against the provider's JWKS, issuer, and
  audience, accepting asymmetric algorithms only.
- The admin surface completes its code flow on the server, so no token reaches
  a page, and protects sessions with signed `HttpOnly` cookies, CSRF tokens,
  and per-identity rate limits.
- The admin renders plain server-side HTML with no JavaScript, which allows a
  `default-src 'none'` policy. This replaces the planned vendored HTMX layer;
  the surface needs no scripting and gains a strictly stronger policy.
- With OIDC unconfigured the service warns at startup and the admin sign-in
  returns 401 rather than falling back to something weaker.

## Delivered client contract

Stage 6 puts the sync agent inside the engine. The desktop reaches the cloud
only through localhost `/api/v2/sync`, and it never holds a cursor or an
outbox of its own.

- Local changes go to a transactional outbox that survives restart. Enqueueing
  is idempotent, so a retry after a crash cannot duplicate work.
- A pass pushes everything queued, then pulls one page. A rejected change
  becomes an open conflict rather than an overwrite, and the rejected operation
  leaves the queue for the conflict inbox.
- Resolutions are local, remote, or merged. Local and merged re-queue on top of
  the revision the service reported; remote simply closes the conflict.
- Transient failures back off and never drop queued work. A refusal, such as a
  removed membership, is surfaced with its reason instead of being retried into
  a silent stall.
- Active use polls every five seconds on top of invalidation hints; background
  work waits thirty; a backing-off workspace waits out its deadline.
- Adding `/api/v2/sync` extends the OpenAPI surface by exactly four paths. No
  `/api/v1` path changed, and the golden fixture records the difference.

## Delivered collaboration contract

Stage 7 adds the shared layer the desktop renders. Comments and activity are
append-only, which is why they never reach the conflict inbox: two devices
writing at once both keep their record.

- Mentions are parsed from the comment body itself, deduplicated, and case
  folded, so what a member sees matches what the author typed.
- Every comment records one `comment.added` event plus one `member.mentioned`
  event per distinct mention.
- Replies must name an existing parent; an orphan reply is refused rather than
  silently reparented.
- `/api/v2/collaboration` adds four paths and changes no `/api/v1` path.
- All of this is local storage. Local-only use still needs no account, and a
  test asserts the surface works with nobody signed in.

## Delivered theme and telemetry contract

Stage 8 delivers the theme layer and the privacy contract. The remaining
stage-8 items in the original plan — virtualized list models, the capture and
review polish, and the PySide6 presentation deferred from stage 7 — are not in
this stage and stay open.

- Every colour the shell paints comes from a palette. A test asserts the
  rendered stylesheet contains no hex outside the active palette, so a hardcoded
  colour cannot survive a theme switch.
- Light and dark palettes are checked against WCAG 2.2 AA on every declared
  pairing: 4.5:1 for normal text, 3:1 for large text and non-text. This is a
  release gate, and a separate test proves the gate rejects an unreadable
  palette rather than passing vacuously.
- Two border colours failed the first measurement and were corrected from
  measured values rather than adjusted by eye.
- Telemetry is off until the user decides, and enabling it without a recorded
  decision raises. Withdrawal takes effect immediately.
- Redaction keeps only declared fields with declared types and drops everything
  else, so an undeclared field cannot leak by being forgotten. A test asserts
  the declared list contains no content-bearing name.

## Delivered retrieval contract

Stage 9 delivers the engine side of the canvas and retrieval work. The native
`QGraphicsScene` view and the USearch ANN adapter are **not** in this stage and
stay open; everything the canvas needs from the engine is here.

- Keyword search moved from `LIKE` substring scans to FTS5 with BM25 ordering.
- `unicode61` folds ü, ö, ç, ş, and ğ, but Turkish dotless `ı` and dotted `İ`
  are letters rather than accented forms, so it leaves them alone. Both the
  index and the query fold them to plain `i`; without that, a search for
  "farkli" would never reach "farklı" in a Turkish-first product.
- Every query token is quoted, so punctuation a user typed cannot become FTS5
  syntax. A query with no searchable term matches nothing rather than
  everything.
- The index is a mirror, never a source of truth: triggers keep it current and
  it rebuilds from the table, so a corrupt index is repaired, not migrated.
- Hybrid retrieval fuses by rank, not score, so a keyword engine and a vector
  engine contribute comparably. With embeddings absent it degrades to keyword
  only rather than failing.
- Subgraph expansion is breadth-first and bounded twice, by depth and by a
  500-node cap the caller cannot raise. Truncation is reported, not hidden.
- Layout is a pure function of identifiers and edges, so the same graph always
  draws the same picture and a bug report is reproducible.

## Delivered model and evidence contract

Stage 10 delivers the signed model manager and the release-gate evaluator. It
does **not** and cannot deliver measured WER, DER, or retrieval numbers: those
need the consented Turkish corpus listed under external inputs.

- The catalogue is Ed25519 signed over a canonical encoding, so reformatting
  still verifies while changing any field does not. Unsigned catalogues,
  catalogues signed by an unknown key, and tampered entries are all refused.
- Model bytes must be fetched over HTTPS even though the digest is checked
  afterwards, and a digest is normalised on entry so an uppercase catalogue
  cannot fail verification for a file that was correct.
- Nothing downloads without consent recorded against that exact model version
  **and** its licence, because a new version may carry different terms.
- Downloads resume rather than restart, and a file whose digest or size does
  not match is deleted rather than kept. Versions live side by side outside the
  application version, so rollback is possible and a pin blocks removal.
- Every quality gate has three outcomes: met, not met, and **unevaluated**. A
  measurement taken from too small or unconsented a corpus stays unevaluated
  rather than counting, and anything not positively met blocks the release.
  With no evidence at all the report blocks with seven unevaluated gates, which
  is the honest answer.

## Release gates

- Windows 10 22H2 and Windows 11 install, update, repair, rollback, migration,
  OIDC, model download, engine lifecycle, and uninstall smoke must pass.
- Branch-inclusive coverage is at least 85%; changed production lines are at
  least 90%; domain, application, migration, sync, and cryptography are at
  least 95%.
- Real Turkish validation uses at least 30 consented/licensed meetings and 20
  hours with reference transcripts. Required targets are clean median WER
  `<=20%`, noisy/far-field WER `<=35%`, domain-term recall `>=85%`, retrieval
  Recall@10 `>=0.85`, citation precision `1.0`, and zero unsupported grounded
  claims.
- The EU service target is 100 concurrent users per workspace, 100,000
  meetings, one million knowledge items, 99.9% control-plane availability,
  RPO `<=15 minutes`, and RTO `<=4 hours`.
- Public release is blocked by any P0/P1 defect, high/critical dependency
  vulnerability, known data-loss path, unresolved security finding, or
  independent cryptography-review finding.

## Degraded security gates

This repository is private and GitHub reports that Advanced Security has not
been purchased, so two gates that previously ran cannot report:

- **CodeQL code scanning** cannot upload results. Bandit in the quality job is
  the enforcing Python security gate meanwhile.
- **Dependency review** cannot read the dependency graph. `pip-audit` over every
  locked extra is the enforcing dependency gate meanwhile.

Both jobs now detect the missing capability and skip with an explicit notice
rather than failing the build or reporting a pass they did not earn. Secret
scanning was moved off the API-dependent Action onto the released gitleaks
binary, so it keeps running on any plan.

Restoring Advanced Security, or moving the repository to public, is a
prerequisite for the `1.0.0` release gate that forbids unresolved security
findings: a scanner that cannot run has not found nothing.

External release inputs remain required: a code-signing certificate/HSM,
provider OIDC registrations, EU PostgreSQL/S3/SMTP infrastructure, two clean
Windows hardware profiles, licensed Turkish validation data, and an independent
security/cryptography reviewer.
